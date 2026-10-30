#!/usr/bin/env python3
"""Local-only, same-UID bridge between the GUI container and the host."""
import argparse
import json
import os
import signal
import socket
import socketserver
import struct
import subprocess
import sys
import threading

MAX_FRAME = 1024 * 1024
MAX_PTY_FRAME = 128 * 1024 * 1024
MAX_UPLOAD = 512 * 1024 * 1024
CHILDREN = set()
CHILD_LOCK = threading.Lock()

def validate_request(value):
    if not isinstance(value, dict) or value.get("op") not in ("ping", "exec", "upload", "pty", "input", "resize", "close"):
        raise ValueError("Invalid local operation")
    op = value["op"]
    if op in ("exec", "upload") or (op == "pty" and not value.get("shell")):
        if not isinstance(value.get("cmd"), str) or not value["cmd"].strip():
            raise ValueError("Missing command")
    if op in ("pty", "resize"):
        for key in ("cols", "rows"):
            if type(value.get(key)) is not int or not 1 <= value[key] <= 1000:
                raise ValueError("Invalid terminal dimensions")
    if op == "upload":
        if type(value.get("size")) is not int or not 0 <= value["size"] <= MAX_UPLOAD:
            raise ValueError("Invalid upload size (maximum 512 MiB)")
    if op == "input":
        data = value.get("data")
        if not isinstance(data, list) or any(type(b) is not int or not 0 <= b <= 255 for b in data):
            raise ValueError("Invalid binary data")
    return value

def send(connection, value):
    connection.sendall(json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii") + b"\n")

def stop_child(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGHUP)
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            process.wait()
    with CHILD_LOCK:
        CHILDREN.discard(process)

def exec_request(request):
    process = subprocess.Popen(
        ["/bin/sh", "-c", request["cmd"]],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True)
    with CHILD_LOCK:
        CHILDREN.add(process)
    try:
        data = bytes(request.get("data", []))
        stdout, stderr = process.communicate(data, timeout=120 if request["op"] == "upload" else 30)
        if process.returncode:
            return {"ok": False, "error": "Local command exited {}: {}".format(process.returncode, stderr.decode("utf-8", "replace"))}
        return {"ok": True, "stdout": stdout.decode("utf-8", "replace")}
    except subprocess.TimeoutExpired:
        stop_child(process)
        return {"ok": False, "error": "Local command timed out"}
    finally:
        with CHILD_LOCK:
            CHILDREN.discard(process)

def pty_request(connection, request):
    import errno
    import fcntl
    import pty
    import select
    import termios
    master, slave = pty.openpty()
    os.set_blocking(master, False)
    process = None
    try:
        def resize(value):
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", value["rows"], value["cols"], 0, 0))
        resize(request)
        command = request.get("cmd", "")
        if request.get("shell"):
            import shlex
            command = "exec {} -l".format(shlex.quote(os.environ.get("SHELL", "/bin/bash")))
        environment = dict(os.environ, TERM="xterm-256color")
        environment.pop("TMUX", None)
        environment.pop("TMUX_PANE", None)
        process = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--pty-child", command],
            stdin=slave, stdout=slave, stderr=slave, close_fds=True, start_new_session=True,
            env=environment)
        with CHILD_LOCK:
            CHILDREN.add(process)
        os.close(slave)
        slave = None
        send(connection, {"ok": True})
        pending = b""
        pending_input = bytearray()
        while True:
            ready, writable, _ = select.select([connection, master], [master] if pending_input else [], [], 1)
            if connection in ready:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                pending += chunk
                if len(pending) > MAX_PTY_FRAME:
                    raise ValueError("Local input frame is too large")
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    message = validate_request(json.loads(line.decode("utf-8")))
                    if message["op"] == "close":
                        return
                    if message["op"] == "resize":
                        resize(message)
                    elif message["op"] == "input":
                        pending_input.extend(message["data"])
                        if len(pending_input) > 16 * 1024 * 1024:
                            raise ValueError("Terminal input buffer is full")
                    else:
                        raise ValueError("Invalid PTY operation")
            if master in writable:
                try:
                    count = os.write(master, pending_input)
                    del pending_input[:count]
                except BlockingIOError:
                    pass
            if master in ready:
                try:
                    data = os.read(master, 4096)
                except OSError as error:
                    if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        continue
                    if error.errno == errno.EIO:
                        break
                    raise
                if not data:
                    break
                send(connection, {"event": "data", "data": list(data)})
            if process.poll() is not None and not ready:
                break
        send(connection, {"event": "eof"})
    finally:
        os.close(master)
        if slave is not None:
            os.close(slave)
        if process is not None:
            stop_child(process)


def upload_request(connection, request):
    process = subprocess.Popen(
        ["/bin/sh", "-c", request["cmd"]], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    with CHILD_LOCK:
        CHILDREN.add(process)
    try:
        connection.settimeout(120)
        send(connection, {"ok": True})
        remaining = request["size"]
        while remaining:
            chunk = connection.recv(min(65536, remaining))
            if not chunk:
                raise ValueError("Upload ended before all bytes arrived")
            process.stdin.write(chunk)
            remaining -= len(chunk)
        process.stdin.close()
        process.stdin = None
        stdout, stderr = process.communicate(timeout=30)
        if process.returncode:
            raise ValueError("Local upload failed: " + stderr.decode("utf-8", "replace"))
        send(connection, {"ok": True})
    finally:
        stop_child(process)
class Handler(socketserver.StreamRequestHandler):
    rbufsize = 0

    def handle(self):
        try:
            peer = self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            _, uid, _ = struct.unpack("3i", peer)
            if uid != os.getuid():
                raise PermissionError("Local bridge only accepts the same UID")
            self.connection.settimeout(10)
            line = self.rfile.readline(MAX_FRAME + 1)
            if not line.endswith(b"\n") or len(line) > MAX_FRAME:
                raise ValueError("Invalid local request frame")
            request = validate_request(json.loads(line.decode("utf-8")))
            self.connection.settimeout(None)
            if request["op"] == "ping":
                send(self.connection, {"ok": True})
            elif request["op"] == "exec":
                send(self.connection, exec_request(request))
            elif request["op"] == "upload":
                upload_request(self.connection, request)
            elif request["op"] == "pty":
                pty_request(self.connection, request)
            else:
                raise ValueError("Invalid initial operation")
        except (OSError, ValueError, KeyError) as error:
            try:
                send(self.connection, {"ok": False, "error": str(error)})
            except OSError:
                pass

class Server(socketserver.ThreadingMixIn, getattr(socketserver, "UnixStreamServer", socketserver.TCPServer)):
    daemon_threads = True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket")
    parser.add_argument("--pty-child")
    args = parser.parse_args()
    if args.pty_child is not None:
        import fcntl
        import termios
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        os.execv("/bin/sh", ["sh", "-c", args.pty_child])
    if not args.socket:
        parser.error("--socket is required")
    parent = os.path.dirname(os.path.abspath(args.socket))
    info = os.stat(parent)
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        parser.error("Socket directory must be owned by this user with mode 0700")
    os.umask(0o077)
    server = Server(args.socket, Handler)
    os.chmod(args.socket, 0o600)
    def terminate(_signum, _frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        with CHILD_LOCK:
            children = list(CHILDREN)
        for child in children:
            stop_child(child)
        try:
            os.unlink(args.socket)
        except FileNotFoundError:
            pass

if __name__ == "__main__":
    main()
