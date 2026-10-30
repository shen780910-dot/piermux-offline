#!/usr/bin/env bash
set -euo pipefail
export LIBGL_ALWAYS_SOFTWARE=1
export WEBKIT_DISABLE_DMABUF_RENDERER=1
/opt/piermux/piermux >/tmp/gui.log 2>&1 &
app_pid=$!
cleanup() {
  cat /tmp/gui.log || true
  kill -KILL "$app_pid" 2>/dev/null || true
}
trap cleanup EXIT
for attempt in $(seq 1 60); do
  if ! kill -0 "$app_pid" 2>/dev/null; then
    echo "Piermux exited before its window opened" >&2
    exit 1
  fi
  if timeout 5 xwininfo -root -tree > /tmp/windows.txt && grep -qi piermux /tmp/windows.txt; then
    cat /tmp/windows.txt
    echo "Piermux GUI window detected"
    exit 0
  fi
  echo "Waiting for GUI window: $attempt/60"
  sleep 1
done
echo "No Piermux window detected" >&2
exit 1
