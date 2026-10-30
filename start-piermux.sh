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
binds=()
if [[ -d /tmp/.X11-unix ]]; then
  binds+=(--bind /tmp/.X11-unix:/tmp/.X11-unix)
fi
if [[ -n "${XAUTHORITY:-}" && -f "$XAUTHORITY" ]]; then
  binds+=(--bind "$XAUTHORITY:$XAUTHORITY:ro")
fi
if [[ -n "${XDG_RUNTIME_DIR:-}" && -d "$XDG_RUNTIME_DIR" ]]; then
  binds+=(--bind "$XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR")
fi
# Software rendering is preferable for remote X11/VNC desktops.
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export WEBKIT_DISABLE_DMABUF_RENDERER="${WEBKIT_DISABLE_DMABUF_RENDERER:-1}"
if [[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
  exec singularity exec "${binds[@]}" "$bundle_dir/rootfs" /opt/piermux/piermux "$@"
else
  exec singularity exec "${binds[@]}" "$bundle_dir/rootfs" dbus-run-session -- /opt/piermux/piermux "$@"
fi
