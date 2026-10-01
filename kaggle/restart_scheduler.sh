#!/usr/bin/env bash
# Restart the scheduler only while it is sleeping (never mid-cycle).
H=/c/Users/rohit/sih26074-v3/kaggle/scheduler_heartbeat.json
until python -c "import json,time,sys; h=json.load(open('$H')); sys.exit(0 if h['phase']=='sleeping' and h['until']-time.time()>20 else 1)" 2>/dev/null; do sleep 3; done
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*scheduler.py*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }; Start-Process powershell -ArgumentList '-NoExit','-Command','cd C:\Users\rohit\sih26074-v3; python kaggle\scheduler.py'"
echo "restarted while sleeping"
