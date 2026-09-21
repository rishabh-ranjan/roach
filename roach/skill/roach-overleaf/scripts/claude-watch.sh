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
        new=""
        while IFS= read -r hit; do
            [[ -z $hit ]] && continue
            key=$(echo "$hit" | sed -E 's/^([^:]*):[0-9]+:/\1:/')
            grep -qxF -- "$key" "$seen_file" || new+="NEW ${hit:0:400}"$'\n'
        done <<<"$hits"
        echo "$hits" | sed -E 's/^([^:]*):[0-9]+:/\1:/' > "$seen_file"
        if [[ -n $new ]]; then
            printf '%s' "$new"
            echo "FIRST start this watcher again (Bash, run_in_background: bash $0), THEN address the comments."
            exit 0
        fi
    else
        fails=$((fails + 1))
        if (( fails >= 20 )); then
            echo "git fetch failed $fails times in a row."
            echo "FIRST start this watcher again (Bash, run_in_background: bash $0), THEN tell the human."
            exit 1
        fi
    fi
    sleep "$poll"
done
