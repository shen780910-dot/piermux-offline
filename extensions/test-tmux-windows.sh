#!/usr/bin/env bash
set -euo pipefail
work_dir="$(mktemp -d)"
socket="piermux-test-$$"
tmux_ci() { "${TMUX_TEST_BIN:-tmux}" -L "$socket" "$@"; }
cleanup() { tmux_ci kill-server 2>/dev/null || true; rm -rf -- "$work_dir"; }
trap cleanup EXIT
mkdir -p "$work_dir/agent-1" "$work_dir/agent-2"
tmux_ci new-session -d -s project-a -n agent-1 -c "$work_dir/agent-1" "sh -c 'printf agent-one; sleep 120'"
second_id="$(tmux_ci new-window -d -P -F '#{window_id}' -t '=project-a:' -n agent-2 -c "$work_dir/agent-2" "sh -c 'printf agent-two; sleep 120'")"
tmux_ci new-session -d -s project-alpha "sleep 120"
tmux_ci select-window -t "=project-a:$second_id"
for attempt in $(seq 1 20); do
  if tmux_ci capture-pane -t '=project-a:' -p | grep -q agent-two; then break; fi
  sleep 0.1
done
tmux_ci capture-pane -t '=project-a:' -p | grep -q agent-two
test "$(tmux_ci display-message -p -t '=project-a:' '#{pane_current_path}')" = "$work_dir/agent-2"
test "$(tmux_ci display-message -p -t '=project-a:' '#{window_id}')" = "$second_id"
tmux_ci rename-session -t '=project-a' renamed-project
if tmux_ci list-windows -t '=project-a:' >/dev/null 2>&1; then
  echo "Exact session lookup incorrectly matched project-alpha" >&2
  exit 1
fi
echo "tmux integration: selection, active capture, upload directory and exact session lookup passed"
