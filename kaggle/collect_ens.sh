#!/usr/bin/env bash
# PS 26086 out-of-fold diffusion ensembles: download each kernel's output when it completes; exit when all terminal.
cd "$(dirname "$0")/.."
J="a1:rohitajitbharadwaj:ens-a1a a1:rohitajitbharadwaj:ens-a1b a2:ssachithananthan:ens-a2a a2:ssachithananthan:ens-a2b a3:rohithphegde:ens-a3"
declare -A DONE
while true; do
  left=0
  for x in $J; do
    a=${x%%:*}; r=${x#*:}; u=${r%%:*}; k=${r#*:}
    [ -n "${DONE[$k]}" ] && continue
    if [ -f ckpts/ens/$k/out/job_status.json ]; then DONE[$k]=1; continue; fi
    st=$(~/bin/kg $a kernels status $u/sih26074-v3-$k 2>&1 | grep -o 'Status\.[A-Z]*' | sed 's/Status\.//')
    case $st in
      COMPLETE)
        mkdir -p ckpts/ens/$k
        ~/bin/kg $a kernels output $u/sih26074-v3-$k -p ckpts/ens/$k >/dev/null 2>&1
        echo "$(date +%H:%M) $k COMPLETE $(cat ckpts/ens/$k/out/job_status.json 2>/dev/null) files: $(find ckpts/ens/$k -name 'ens_*.npz' | xargs -n1 basename | tr '\n' ' ')"
        DONE[$k]=1 ;;
      ERROR|CANCEL*) echo "$(date +%H:%M) $k $st"; DONE[$k]=1 ;;
      *) left=$((left+1)) ;;
    esac
  done
  [ $left -eq 0 ] && { echo "ALL TERMINAL"; break; }
  sleep 90
done
