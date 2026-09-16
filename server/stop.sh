#!/bin/bash

pkill -f "uvicorn app.main:app" && echo "服务已停止" || echo "未找到运行中的进程"
