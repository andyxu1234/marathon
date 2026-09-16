#!/bin/bash

cd /usr/andy/marathon/server || exit 1
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 > /tmp/worldcup-server.log 2>&1 &
echo "服务已启动, PID: $!"
