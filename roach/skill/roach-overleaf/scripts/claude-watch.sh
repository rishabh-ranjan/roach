#!/bin/bash
set -uo pipefail
poll=${1:-30}
seen_file=$(git rev-parse --absolute-git-dir)/claude-watch.seen || exit 1
touch "$seen_file"
fails=0

while true; do
    if git fetch -q 2>/dev/null; then
        fails=0
        hits=$(git grep -n -I -i '@claude' '@{u}' -- '*.tex' 2>/dev/null | cut -d: -f2-)
        while IFS= read -r hit; do
            [[ -z $hit ]] && continue
            key=$(echo "$hit" | sed -E 's/^([^:]*):[0-9]+:/\1:/')
            grep -qxF -- "$key" "$seen_file" || echo "NEW ${hit:0:400}"
        done <<<"$hits"
        echo "$hits" | sed -E 's/^([^:]*):[0-9]+:/\1:/' > "$seen_file"
    else
        fails=$((fails + 1))
        (( fails % 10 == 0 )) && echo "$(date +%T) git fetch failed $fails times in a row"
    fi
    sleep "$poll"
done
