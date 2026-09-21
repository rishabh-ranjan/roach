#!/bin/bash
set -uo pipefail
poll=${1:-30}
git_dir=$(git rev-parse --absolute-git-dir) || exit 1
seen_file=$git_dir/claude-watch.seen
exec 9>"$git_dir/claude-watch.lock"
flock -n 9 || { echo "a watcher is already running for this clone"; exit 0; }
touch "$seen_file"
fails=0

while true; do
    if git fetch -q 2>/dev/null; then
        fails=0
        hits=$(git grep -n -I -i '@claude' '@{u}' -- '*.tex' 2>/dev/null | cut -d: -f2-)
        keys=$(echo "$hits" | sed -E 's/^([^:]*):[0-9]+:/\1:/')
        new=""
        while IFS= read -r hit; do
            [[ -z $hit ]] && continue
            key=$(echo "$hit" | sed -E 's/^([^:]*):[0-9]+:/\1:/')
            grep -qxF -- "$key" "$seen_file" || new+="NEW ${hit:0:400}"$'\n'
        done <<<"$hits"
        echo "$keys" > "$seen_file"
        [[ -n $new ]] && { printf '%s' "$new"; exit 0; }
    else
        fails=$((fails + 1))
        (( fails >= 20 )) && { echo "git fetch failed $fails times in a row: watcher giving up"; exit 1; }
    fi
    sleep "$poll"
done
