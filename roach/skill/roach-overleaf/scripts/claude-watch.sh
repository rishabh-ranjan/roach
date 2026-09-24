#!/bin/bash
# Watch an Overleaf clone for @claude comments and exit as soon as one settles.
#
# Pacing: one cheap ls-remote probe every couple of seconds asks whether
# anything changed; only a change costs a real fetch. There is no slow tier,
# because the watcher runs only while nobody is acting on a comment: it exits
# on the first report and is started again after that work is pushed. A token
# bucket still caps the hour, because exceeding Overleaf's git rate limit
# breaks pull and push for the authors too.
#
# A comment fires the moment it is well-formed, without waiting for the author
# to stop typing. If they keep going, the text changes and it fires again; the
# work done on the earlier text is checked against the current one before it is
# pushed. Latency is what matters here, not doing the work exactly once.
set -uo pipefail

PROBE=${CLAUDE_WATCH_PROBE:-2}    # seconds between probes
EASE=${CLAUDE_WATCH_EASE:-8}      # seconds between probes once the budget is spent
SETTLE=${CLAUDE_WATCH_SETTLE:-0}  # extra seconds a comment must hold still first
BUDGET=${CLAUDE_WATCH_BUDGET:-1500} # most requests to Overleaf per rolling hour

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
    if (( age <= 6 * PROBE + 10 )) && [[ ${sum:-} == "$self_sum" ]]; then
        echo "another claude-watch (pid $holder) is polling this repo on this same script, last poll ${age}s ago; not starting a second one."
        exit 0
    fi
    if [[ -z ${sum:-} ]]; then
        echo "taking over from claude-watch pid $holder: it leaves no heartbeat, so it predates this script."
    elif [[ ${sum:-} != "$self_sum" ]]; then
        echo "taking over from claude-watch pid $holder: it is running a script that has since changed."
    else
        echo "taking over from claude-watch pid $holder: its last poll was ${age}s ago, past $((6 * PROBE + 10))s."
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

# Report anything new and stop; the exit is what wakes Claude.
report_if_new() {
    (( $(date +%s) - changed_at < SETTLE )) && return
    local new="" file line body
    new=""
    while IFS=$'\t' read -r file line body; do
        [[ -z ${file:-} ]] && continue
        # Keyed on file and text, not line: a paragraph added above a comment
        # must not make it look new.
        grep -qxF -- "$file"$'\t'"$body" "$seen_file" && continue
        new+="NEW $file:$line by $(blame_author "$file" "$line"): $body"$'\n'
    done <<<"$cur"
    [[ -z $new ]] && return
    cut -f1,3- <<<"$cur" >"$seen_file"
    printf '%s' "$new"
    echo "Your clone is already fetched: merge with 'git merge --ff-only @{u}', not 'git pull', which would spend another request."
    echo "This fired the moment the comment was well-formed, so the author may still be typing: before you push, check the comment still reads as above."
    echo "Nothing is watching now. Address the comments, push, and start this watcher again (Bash, run_in_background: bash $0) before your turn ends."
    exit 0
}

head_sha=$(git rev-parse '@{u}')
cur=$(extract)
changed_at=$(date +%s)   # when the comment text last changed
backoff=0

while true; do
    beat
    report_if_new
    if [[ $(sha1sum "$0" | cut -d' ' -f1) != "$self_sum" ]]; then
        echo "this watcher script changed on disk; the running copy is out of date."
        echo "FIRST start this watcher again (Bash, run_in_background: bash $0), THEN carry on."
        exit 0
    fi

    if (( backoff )); then
        sleep "$backoff"
    elif (( $(spent) >= BUDGET )); then
        sleep "$EASE"
    else
        sleep "$PROBE"
    fi

    spend
    probe=$(git ls-remote "$remote" "refs/heads/$branch" 2>&1)
    if grep -qi 'rate-limit\|no git access' <<<"$probe"; then
        backoff=$(( backoff ? backoff * 2 : EASE ))
        (( backoff > 900 )) && backoff=900
        continue
    fi
    backoff=0
    sha=${probe%%$'\t'*}
    [[ -z $sha || $sha == "$head_sha" ]] && continue

    spend
    git fetch -q "$remote" "$branch" 2>/dev/null || continue
    head_sha=$(git rev-parse '@{u}')
    fresh=$(extract)
    if [[ $fresh != "$cur" ]]; then
        cur=$fresh
        changed_at=$(date +%s)
        report_if_new
    fi
done
