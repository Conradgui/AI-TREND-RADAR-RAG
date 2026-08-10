@echo off
chcp 65001 >nul
title AI Trend Radar RAG - 更新服务

if not exist ".env" (
  echo 尚未完成首次配置。请先双击 setup.bat。
  pause
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop 尚未运行。请启动 Docker Desktop 后重试。
  pause
  exit /b 1
)

echo 正在按当前项目代码更新服务镜像（Neo4j 与 RAG 数据卷会保留）...
docker compose up -d --build
if errorlevel 1 (
  echo 更新失败。请检查 Docker Desktop 状态和上方错误信息。
  pause
  exit /b 1
)

echo 更新已完成。请双击 start.bat 等待服务就绪并打开页面。
pause
