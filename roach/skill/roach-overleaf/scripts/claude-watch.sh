#!/bin/bash
set -uo pipefail
poll=${1:-60}
git_dir=$(git rev-parse --absolute-git-dir) || exit 1
seen_file=$git_dir/claude-watch.seen
lock_file=$git_dir/claude-watch.lock
prev_file=$git_dir/claude-watch.prev
beat_file=$git_dir/claude-watch.beat
touch "$seen_file"

self_sum=$(sha1sum "$0" | cut -d' ' -f1)
beat() { printf '%s %s %s\n' "$(date +%s)" "$$" "$self_sum" >"$beat_file"; }

# A watcher that is wedged, or running a script that has since been replaced, is
# worse than none: it holds the lock while hearing nothing. Take over from one.
# The pid holding the lock, for a holder too old to leave a heartbeat.
lock_holder() {
    local fd
    for fd in /proc/[0-9]*/fd/*; do
        if [[ $(readlink -f "$fd" 2>/dev/null) == "$lock_file" ]]; then
            fd=${fd#/proc/}
            echo "${fd%%/*}"
            return
        fi
    done
}

exec 9>"$lock_file"
if ! flock -n 9; then
    when= holder= sum=
    [[ -r $beat_file ]] && read -r when holder sum <"$beat_file"
    [[ -z ${holder:-} ]] && holder=$(lock_holder)
    age=$(( $(date +%s) - ${when:-0} ))
    if [[ -n ${holder:-} ]] && kill -0 "$holder" 2>/dev/null; then
        if (( age <= 3 * poll )) && [[ ${sum:-} == "$self_sum" ]]; then
            echo "another claude-watch (pid $holder) is polling this repo on this same script, last poll ${age}s ago; not starting a second one."
            exit 0
        fi
        if [[ -z ${sum:-} ]]; then
            echo "taking over from claude-watch pid $holder: it leaves no heartbeat, so it predates this script."
        elif [[ ${sum:-} != "$self_sum" ]]; then
            echo "taking over from claude-watch pid $holder: it is running a script that has since changed."
        else
            echo "taking over from claude-watch pid $holder: its last poll was ${age}s ago, past $((3 * poll))s."
        fi
        # SIGCONT too: a stopped holder would never act on the TERM, and it
        # keeps the lock until it actually exits.
        kill "$holder" 2>/dev/null
        kill -CONT "$holder" 2>/dev/null
        for _ in 1 2 3 4 5; do
            kill -0 "$holder" 2>/dev/null || break
            sleep 1
        done
        kill -0 "$holder" 2>/dev/null && kill -9 "$holder" 2>/dev/null
    fi
    if ! flock -w 15 9; then
        echo "could not take the claude-watch lock."
        echo "FIRST start this watcher again (Bash, run_in_background: bash $0 $poll), THEN tell the human."
        exit 1
    fi
fi
beat

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
for m in re.finditer(r"@claude", s, re.I):
    i = m.end()
    while i < len(s) and s[i] == " ":
        i += 1
    if i < len(s) and s[i] == "{":
        # @claude{...}: the comment is the balanced group.
        i += 1
        start, depth = i, 1
        while i < len(s) and depth:
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
            i += 1
        if depth:
            continue
        end = i - 1
    else:
        # \rishabh{@claude ...}: the comment runs to the end of the macro.
        start, depth = i, 0
        while i < len(s):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                if not depth:
                    break
                depth -= 1
            i += 1
        else:
            continue
        end = i
    body = " ".join(s[start:end].split())
    if body:
        print(f"{f}\t{s.count(chr(10), 0, m.start()) + 1}\t{body}")
' "$f"
    done
}

# Who wrote the line the comment sits on, so the reply can address them.
blame_author() {
    git blame -L "$2,$2" --porcelain '@{u}' -- "$1" 2>/dev/null |
        sed -n 's/^author //p' | head -1
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

    # Pick up a new version of this script rather than keep running the old one.
    if [[ $(sha1sum "$0" | cut -d' ' -f1) != "$self_sum" ]]; then
        echo "this watcher script changed on disk; the running copy is out of date."
        echo "FIRST start this watcher again (Bash, run_in_background: bash $0 $poll), THEN carry on."
        exit 0
    fi
    beat

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
        while IFS=$'\t' read -r file line body; do
            [[ -z ${file:-} ]] && continue
            # Keyed on file and text, not line: a paragraph added above a
            # comment must not make it look new.
            grep -qxF -- "$file"$'\t'"$body" "$seen_file" && continue
            new+="NEW $file:$line by $(blame_author "$file" "$line"): $body"$'\n'
        done <<<"$cur"
        if [[ -n $new ]]; then
            cut -f1,3- <<<"$cur" >"$seen_file"
            printf '%s' "$new"
            echo "FIRST start this watcher again (Bash, run_in_background: bash $0 $poll), THEN address the comments."
            exit 0
        fi
    fi
    printf '%s' "$cur" >"$prev_file"
    sleep "$poll"
done
