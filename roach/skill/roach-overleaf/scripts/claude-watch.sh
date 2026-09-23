#!/bin/bash
set -uo pipefail
poll=${1:-60}
git_dir=$(git rev-parse --absolute-git-dir) || exit 1
seen_file=$git_dir/claude-watch.seen
lock_file=$git_dir/claude-watch.lock
prev_file=$git_dir/claude-watch.prev
touch "$seen_file"

exec 9>"$lock_file"
if ! flock -n 9; then
    echo "another claude-watch is already polling this repo; not starting a second one."
    exit 0
fi

: >"$prev_file"
backoff=$poll
stable=0
# Number of consecutive unchanged polls before a comment is reported.
quiet=${CLAUDE_WATCH_QUIET:-2}

extract() {
    git ls-tree -r --name-only '@{u}' | grep -i '\.tex$' | while IFS= read -r f; do
        git show "@{u}:$f" 2>/dev/null | python3 -c '
import re, sys
f = sys.argv[1]
s = sys.stdin.read()
for m in re.finditer(r"@claude\{", s, re.I):
    i = m.end()
    depth = 1
    while i < len(s) and depth:
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
        i += 1
    if depth:
        continue
    body = " ".join(s[m.end():i - 1].split())
    print(f"{f}:{s.count(chr(10), 0, m.start()) + 1}\t{body}")
' "$f"
    done
}

while true; do
    err=$(git fetch -q 2>&1)
    if [[ -n $err ]] && grep -qi 'rate-limit\|no git access' <<<"$err"; then
        backoff=$((backoff * 2))
        (( backoff > 900 )) && backoff=900
        sleep "$backoff"
        continue
    fi
    if [[ -n $err ]] && ! git rev-parse -q --verify '@{u}' >/dev/null; then
        echo "cannot reach the upstream branch: $err"
        echo "FIRST start this watcher again (Bash, run_in_background: bash $0 $poll), THEN tell the human."
        exit 1
    fi
    backoff=$poll

    cur=$(extract)
    # Report a comment only once it has been byte-identical for $quiet polls in a
    # row, so a comment still being typed in the web editor never fires half-written.
    if [[ $cur == "$(cat "$prev_file")" ]]; then
        stable=$((stable + 1))
    else
        stable=0
    fi
    if (( stable >= quiet )); then
        new=""
        while IFS= read -r hit; do
            [[ -z $hit ]] && continue
            grep -qxF -- "$hit" "$seen_file" || new+="NEW $hit"$'\n'
        done <<<"$cur"
        if [[ -n $new ]]; then
            printf '%s' "$cur" >"$seen_file"
            printf '%s' "$new"
            echo "FIRST start this watcher again (Bash, run_in_background: bash $0 $poll), THEN address the comments."
            exit 0
        fi
    fi
    printf '%s' "$cur" >"$prev_file"
    sleep "$poll"
done
