import importlib.util
import pathlib
import unittest
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import time

path = pathlib.Path(__file__).resolve().parents[1] / "local_bridge.py"
spec = importlib.util.spec_from_file_location("local_bridge", str(path))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

class ProtocolTests(unittest.TestCase):
    def test_exec_and_shell_pty_need_no_ssh_fields(self):
        self.assertEqual(bridge.validate_request({"op": "exec", "cmd": "whoami"})["op"], "exec")
        self.assertTrue(bridge.validate_request({"op": "pty", "shell": True, "cols": 80, "rows": 24})["shell"])

    def test_rejects_invalid_operations_and_dimensions(self):
        for request in [None, {}, {"op": "unknown"}, {"op": "pty", "cmd": "sh", "cols": 0, "rows": 24},
                        {"op": "pty", "cmd": "sh", "cols": 80, "rows": 999999}]:
            with self.assertRaises(ValueError):
                bridge.validate_request(request)

    def test_binary_input_is_validated_without_unicode_conversion(self):
        self.assertEqual(bridge.validate_request({"op": "input", "data": [0, 127, 255]})["data"], [0, 127, 255])
        for payload in [[-1], [256], ["a"], [True]]:
            with self.assertRaises(ValueError):
                bridge.validate_request({"op": "input", "data": payload})

    def test_upload_uses_a_bounded_size_header_instead_of_json_bytes(self):
        request = bridge.validate_request({"op": "upload", "cmd": "cat > target", "size": 512 * 1024 * 1024})
        self.assertEqual(request["size"], 512 * 1024 * 1024)
        for size in [-1, True, 512 * 1024 * 1024 + 1]:
            with self.assertRaises(ValueError):
                bridge.validate_request({"op": "upload", "cmd": "cat > target", "size": size})

@unittest.skipUnless(os.name == "posix", "Linux host integration")
class HostBridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="piermux-test-")
        self.socket_path = str(pathlib.Path(self.directory.name) / "bridge.sock")
        self.process = subprocess.Popen([sys.executable, str(path), "--socket", self.socket_path],
                                        env=dict(os.environ, PIERMUX_HOST_MARKER="host-only",
                                                 TMUX="/tmp/outer,123,0", TMUX_PANE="%123"))
        for _ in range(100):
            if os.path.exists(self.socket_path):
                break
            time.sleep(0.025)

    def tearDown(self):
        self.process.terminate()
        self.process.wait(timeout=5)
        self.directory.cleanup()

    def connect(self):
        connection = socket.socket(socket.AF_UNIX)
        connection.settimeout(5)
        connection.connect(self.socket_path)
        return connection

    def test_host_environment_exit_status_and_socket_permissions(self):
        self.assertEqual(stat.S_IMODE(os.stat(self.socket_path).st_mode), 0o600)
        for command, expected in [("printf '%s' \"$PIERMUX_HOST_MARKER\"", "host-only"),
                                  ("printf failure >&2; exit 7", None)]:
            with self.connect() as connection:
                bridge.send(connection, {"op": "exec", "cmd": command})
                response = json.loads(connection.makefile("rb").readline())
                if expected is None:
                    self.assertFalse(response["ok"])
                    self.assertIn("failure", response["error"])
                else:
                    self.assertEqual(response["stdout"], expected)

    def test_pty_binary_input_and_resize(self):
        with self.connect() as connection:
            reader = connection.makefile("rb")
            bridge.send(connection, {"op": "pty", "cols": 80, "rows": 24,
                        "cmd": "printf 'NESTING:%s:%s\\n' \"${TMUX-unset}\" \"${TMUX_PANE-unset}\"; printf '\\377'; read line; printf 'REPLY:%s\\n' \"$line\"; stty size"})
            self.assertTrue(json.loads(reader.readline())["ok"])
            bridge.send(connection, {"op": "resize", "cols": 100, "rows": 30})
            bridge.send(connection, {"op": "input", "data": list(b"BRIDGE_INPUT\n")})
            output = bytearray()
            while True:
                event = json.loads(reader.readline())
                if event.get("event") == "eof":
                    break
                output.extend(event.get("data", []))
            self.assertIn(255, output)
            self.assertIn(b"NESTING:unset:unset", output)
            self.assertIn(b"REPLY:BRIDGE_INPUT", output)
            self.assertIn(b"30 100", output)
            reader.close()

    def test_upload_streams_more_than_the_old_json_frame_limit(self):
        import shlex
        target = pathlib.Path(self.directory.name) / "uploaded.bin"
        size = 33 * 1024 * 1024
        with self.connect() as connection:
            reader = connection.makefile("rb")
            bridge.send(connection, {"op": "upload", "cmd": "cat > " + shlex.quote(str(target)), "size": size})
            self.assertTrue(json.loads(reader.readline())["ok"])
            chunk = bytes([255]) * 65536
            for _ in range(size // len(chunk)):
                connection.sendall(chunk)
            connection.shutdown(socket.SHUT_WR)
            self.assertTrue(json.loads(reader.readline())["ok"])
            reader.close()
        self.assertEqual(target.stat().st_size, size)
        with target.open("rb") as saved:
            self.assertEqual(saved.read(65536), chunk)
            saved.seek(-65536, 2)
            self.assertEqual(saved.read(), chunk)

if __name__ == "__main__":
    unittest.main()
