#!/usr/bin/env bash
# Poll the 20 GEFS35 kernels; download each output when it completes; print one line per terminal state; exit when all done.
cd "$(dirname "$0")/../.."
declare -A ACC=([a1]="rohitajitbharadwaj:2000 2001 2002 2003 2004" [a3]="rohithphegde:2005 2006 2007 2008 2009"
                [a4]="saketmeda:2010 2011 2012 2013 2014" [a2]="ssachithananthan:2015 2016 2017 2018 2019")
declare -A DONE
while true; do
  left=0
  for a in a1 a2 a3 a4; do
    u=${ACC[$a]%%:*}; ys=${ACC[$a]#*:}
    for y in $ys; do
      [ -n "${DONE[$y]}" ] && continue
      st=$(~/bin/kg $a kernels status $u/sih26074-gefs35-$y 2>&1 | grep -o 'Status\.[A-Z]*' | sed 's/Status\.//')
      case $st in
        COMPLETE)
          mkdir -p ckpts/gefs/$y
          ~/bin/kg $a kernels output $u/sih26074-gefs35-$y -p ckpts/gefs/$y >/dev/null 2>&1
          log=$(python -c "import json;d=json.load(open('ckpts/gefs/$y/gefs/log_$y.json'));print(f\"ok {d['ok']}/{d['inits']} bad {len(d['bad'])} {d['min']:.0f} min\")" 2>&1 | tail -1)
          echo "$(date +%H:%M) $y COMPLETE $log"; DONE[$y]=1 ;;
        ERROR|CANCEL*)
          echo "$(date +%H:%M) $y $st"; DONE[$y]=1 ;;
        *) left=$((left+1)) ;;
      esac
    done
  done
  [ $left -eq 0 ] && { echo "ALL TERMINAL"; break; }
  sleep 60
done
