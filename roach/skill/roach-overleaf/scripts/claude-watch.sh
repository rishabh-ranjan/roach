#!/bin/bash
# Watch an Overleaf clone for @claude comments and exit as soon as one settles.
#
# Pacing: a cheap ls-remote probe asks whether anything changed at all, and only
# a change costs a real fetch. While someone is typing, probes go fast; after a
# quiet stretch they slow down. A token bucket caps the hour, because exceeding
# Overleaf's git rate limit breaks pull and push for the authors too.
set -uo pipefail

FAST=${CLAUDE_WATCH_FAST:-4}      # seconds between probes right after any change
MID=${CLAUDE_WATCH_MID:-12}       # seconds between probes for the rest of the live window
SLOW=${CLAUDE_WATCH_SLOW:-45}     # seconds between probes once it has gone quiet
HOT=${CLAUDE_WATCH_HOT:-60}       # a change keeps the project "hot" this long
LIVE=${CLAUDE_WATCH_LIVE:-240}    # and "live" this long
SETTLE=${CLAUDE_WATCH_SETTLE:-6}  # a comment must hold this long before it fires
BUDGET=${CLAUDE_WATCH_BUDGET:-150} # most requests to Overleaf per rolling hour

git_dir=$(git rev-parse --absolute-git-dir) || exit 1
seen_file=$git_dir/claude-watch.seen
lock_file=$git_dir/claude-watch.lock
beat_file=$git_dir/claude-watch.beat
rate_file=$git_dir/claude-watch.rate
touch "$seen_file"

upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null) || {
    echo "no upstream branch to watch."
    exit 1
}
remote=${upstream%%/*}
branch=${upstream#*/}

self_sum=$(sha1sum "$0" | cut -d' ' -f1)
beat() { printf '%s %s %s\n' "$(date +%s)" "$$" "$self_sum" >"$beat_file"; }

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

# A watcher that is wedged, or running a script that has since been replaced, is
# worse than none: it holds the lock while hearing nothing. Take over from one.
exec 9>"$lock_file"
for attempt in 1 2 3; do
    flock -n 9 && break
    when= holder= sum=
    [[ -r $beat_file ]] && read -r when holder sum <"$beat_file"
    [[ -z ${holder:-} ]] || kill -0 "$holder" 2>/dev/null || holder=
    [[ -z ${holder:-} ]] && holder=$(lock_holder)
    if [[ -z ${holder:-} ]]; then
        flock -w 10 9 && break
        continue
    fi
    age=$(( $(date +%s) - ${when:-0} ))
    if (( age <= 3 * SLOW )) && [[ ${sum:-} == "$self_sum" ]]; then
        echo "another claude-watch (pid $holder) is polling this repo on this same script, last poll ${age}s ago; not starting a second one."
        exit 0
    fi
    if [[ -z ${sum:-} ]]; then
        echo "taking over from claude-watch pid $holder: it leaves no heartbeat, so it predates this script."
    elif [[ ${sum:-} != "$self_sum" ]]; then
        echo "taking over from claude-watch pid $holder: it is running a script that has since changed."
    else
        echo "taking over from claude-watch pid $holder: its last poll was ${age}s ago, past $((3 * SLOW))s."
    fi
    # SIGCONT too: a stopped holder would never act on the TERM, and it keeps
    # the lock until it actually exits.
    kill "$holder" 2>/dev/null
    kill -CONT "$holder" 2>/dev/null
    for _ in 1 2 3 4 5; do
        kill -0 "$holder" 2>/dev/null || break
        sleep 1
    done
    kill -0 "$holder" 2>/dev/null && kill -9 "$holder" 2>/dev/null
    : >"$beat_file"
done
if ! flock -n 9 && ! flock -w 5 9; then
    echo "could not take the claude-watch lock; something is still holding it."
    echo "FIRST start this watcher again (Bash, run_in_background: bash $0), THEN tell the human."
    exit 1
fi
beat

# Requests in the trailing hour, one timestamp per line.
spend() { date +%s >>"$rate_file"; }
spent() {
    local cutoff=$(( $(date +%s) - 3600 ))
    [[ -s $rate_file ]] || { echo 0; return; }
    awk -v c="$cutoff" '$1 >= c' "$rate_file" >"$rate_file.new" && mv "$rate_file.new" "$rate_file"
    wc -l <"$rate_file"
}

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

now=$(date +%s)
head_sha=$(git rev-parse '@{u}')
cur=$(extract)
changed_at=$now      # when the comment text last changed
live_at=$now         # when the project last changed; a start counts, since
                     # the watcher is started when the authors are about to edit
backoff=0

while true; do
    beat
    if [[ $(sha1sum "$0" | cut -d' ' -f1) != "$self_sum" ]]; then
        echo "this watcher script changed on disk; the running copy is out of date."
        echo "FIRST start this watcher again (Bash, run_in_background: bash $0), THEN carry on."
        exit 0
    fi

    now=$(date +%s)
    if (( now - changed_at >= SETTLE )); then
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
            echo "Your clone is already fetched: merge with 'git merge --ff-only @{u}', not 'git pull', which would spend another request."
            echo "FIRST start this watcher again (Bash, run_in_background: bash $0), THEN address the comments."
            exit 0
        fi
    fi

    if (( backoff )); then
        sleep "$backoff"
    elif (( $(spent) >= BUDGET )); then
        sleep "$SLOW"
    elif (( now - live_at < HOT )); then
        sleep "$FAST"
    elif (( now - live_at < LIVE )); then
        sleep "$MID"
    else
        sleep "$SLOW"
    fi

    spend
    probe=$(git ls-remote "$remote" "refs/heads/$branch" 2>&1)
    if grep -qi 'rate-limit\|no git access' <<<"$probe"; then
        backoff=$(( backoff ? backoff * 2 : SLOW ))
        (( backoff > 900 )) && backoff=900
        continue
    fi
    backoff=0
    sha=${probe%%$'\t'*}
    [[ -z $sha || $sha == "$head_sha" ]] && continue

    live_at=$(date +%s)
    spend
    git fetch -q "$remote" "$branch" 2>/dev/null || continue
    head_sha=$(git rev-parse '@{u}')
    fresh=$(extract)
    if [[ $fresh != "$cur" ]]; then
        cur=$fresh
        changed_at=$(date +%s)
    fi
done
