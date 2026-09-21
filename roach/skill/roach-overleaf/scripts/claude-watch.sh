#!/bin/bash
set -uo pipefail
poll=${1:-30}
seen=""; fails=0; last_beat=$(date +%s)

while true; do
    if git fetch -q 2>/dev/null; then
        fails=0
        hits=$(git grep -n -I '@claude' '@{u}' -- '*.tex' 2>/dev/null | cut -d: -f2-)
        keys=$(echo "$hits" | sed -E 's/^([^:]*):[0-9]+:/\1:/')
        while IFS= read -r hit; do
            [[ -z $hit ]] && continue
            key=$(echo "$hit" | sed -E 's/^([^:]*):[0-9]+:/\1:/')
            grep -qxF -- "$key" <<<"$seen" || echo "NEW ${hit:0:400}"
        done <<<"$hits"
        seen=$keys
    else
        fails=$((fails + 1))
        (( fails % 10 == 0 )) && echo "$(date +%T) git fetch failed $fails times in a row"
    fi
    now=$(date +%s)
    if (( now - last_beat >= 900 )); then
        echo "$(date +%T) watching, $(grep -c . <<<"$seen") open @claude comments"
        last_beat=$now
    fi
    sleep "$poll"
done
