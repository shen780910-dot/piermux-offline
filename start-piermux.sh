#!/usr/bin/env bash
set -euo pipefail
bundle_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v singularity >/dev/null 2>&1; then
  echo "找不到 singularity，請確認 /bin/singularity 可執行。" >&2
  exit 1
fi
if [[ "$(uname -m)" != x86_64 ]]; then
  echo "此套件只支援 x86_64。" >&2
  exit 1
fi
if [[ -z "${DISPLAY:-}" ]]; then
  echo "沒有 DISPLAY；請從 Linux 桌面終端機啟動。" >&2
  exit 1
fi
if [[ ! -x "$bundle_dir/rootfs/opt/piermux/piermux" ]]; then
  echo "缺少 rootfs/opt/piermux/piermux，請重新完整解壓套件。" >&2
  exit 1
fi
if ! command -v tmux >/dev/null 2>&1; then
  echo "主機找不到 tmux，請先載入你平常使用 tmux 的環境。" >&2
  exit 1
fi
if command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
elif [[ -x /usr/libexec/platform-python ]]; then
  python_bin=/usr/libexec/platform-python
else
  echo "主機找不到 Python 3 或 Rocky Linux 的 platform-python。" >&2
  exit 1
fi
bridge_dir="$(mktemp -d /tmp/piermux-local.XXXXXXXX)"
bridge_pid=""
cleanup() {
  if [[ -n "$bridge_pid" ]]; then
    kill "$bridge_pid" 2>/dev/null || true
    wait "$bridge_pid" 2>/dev/null || true
  fi
  rm -f -- "$bridge_dir/bridge.sock" "$bridge_dir/bridge.log"
  rmdir -- "$bridge_dir" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"$python_bin" "$bundle_dir/local_bridge.py" --socket "$bridge_dir/bridge.sock" >"$bridge_dir/bridge.log" 2>&1 &
bridge_pid=$!
for attempt in $(seq 1 100); do
  [[ -S "$bridge_dir/bridge.sock" ]] && break
  kill -0 "$bridge_pid" 2>/dev/null || break
  sleep 0.05
done
if [[ ! -S "$bridge_dir/bridge.sock" ]]; then
  cat "$bridge_dir/bridge.log" >&2
  echo "本機連線未能啟動。" >&2
  exit 1
fi
binds=(--bind "$bridge_dir:$bridge_dir")
if [[ -d /tmp/.X11-unix ]]; then
  binds+=(--bind /tmp/.X11-unix:/tmp/.X11-unix)
fi
if [[ -n "${XAUTHORITY:-}" && -f "$XAUTHORITY" ]]; then
  binds+=(--bind "$XAUTHORITY:$XAUTHORITY:ro")
fi
if [[ -n "${XDG_RUNTIME_DIR:-}" && -d "$XDG_RUNTIME_DIR" ]]; then
  binds+=(--bind "$XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR")
fi
export PIERMUX_LOCAL_SOCKET="$bridge_dir/bridge.sock"
export SINGULARITYENV_PIERMUX_LOCAL_SOCKET="$PIERMUX_LOCAL_SOCKET"
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export WEBKIT_DISABLE_DMABUF_RENDERER="${WEBKIT_DISABLE_DMABUF_RENDERER:-1}"
if [[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
  singularity exec "${binds[@]}" "$bundle_dir/rootfs" /opt/piermux/piermux "$@"
else
  singularity exec "${binds[@]}" "$bundle_dir/rootfs" dbus-run-session -- /opt/piermux/piermux "$@"
fi
