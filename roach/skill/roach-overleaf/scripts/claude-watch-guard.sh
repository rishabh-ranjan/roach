#!/bin/bash
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
input=$(cat)
git_dir=$(git rev-parse --absolute-git-dir 2>/dev/null) || exit 0
exec 9>"$git_dir/claude-watch.lock"
flock -n 9 || exit 0
flock -u 9
msg='The @claude comment watcher is not running. Start it now with Bash run_in_background: bash .claude/skills/roach-overleaf/scripts/claude-watch.sh'
if [[ $(jq -r '.stop_hook_active // false' <<<"$input") == true ]]; then
    jq -n --arg m "$msg" '{systemMessage: $m}'
else
    jq -n --arg m "$msg" '{decision: "block", reason: $m}'
fi
