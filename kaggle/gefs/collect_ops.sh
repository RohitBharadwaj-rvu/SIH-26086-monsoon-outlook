#!/usr/bin/env bash
# Operational GEFS 2021-2023 kernels (account a1): download each output when it completes; exit when all terminal.
cd "$(dirname "$0")/../.."
declare -A DONE
while true; do
  left=0
  for y in 2021 2022 2023; do
    [ -n "${DONE[$y]}" ] && continue
    st=$(~/bin/kg a1 kernels status rohitajitbharadwaj/sih26074-gefs35-$y 2>&1 | grep -o 'Status\.[A-Z]*' | sed 's/Status\.//')
    case $st in
      COMPLETE)
        mkdir -p ckpts/gefs/$y
        ~/bin/kg a1 kernels output rohitajitbharadwaj/sih26074-gefs35-$y -p ckpts/gefs/$y >/dev/null 2>&1
        log=$(python -c "import json;d=json.load(open('ckpts/gefs/$y/gefs/log_$y.json'));print(f\"ok {d['ok']}/{d['inits']} bad {len(d['bad'])} {d['min']:.0f} min\")" 2>&1 | tail -1)
        echo "$(date +%H:%M) $y COMPLETE $log"; DONE[$y]=1 ;;
      ERROR|CANCEL*) echo "$(date +%H:%M) $y $st"; DONE[$y]=1 ;;
      *) left=$((left+1)) ;;
    esac
  done
  [ $left -eq 0 ] && { echo "ALL TERMINAL"; break; }
  sleep 60
done
