@echo off
chcp 65001 >nul
title AI Trend Radar RAG

if not exist ".env" (
  echo 尚未完成首次配置。请先双击 setup.bat。
  pause
  exit /b 1
)

docker info >nul 2>&1
if not errorlevel 1 goto docker_ready

if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo 正在等待 Docker Desktop 就绪...
set /a docker_counter=0
:wait_for_docker
docker info >nul 2>&1
if not errorlevel 1 goto docker_ready
timeout /t 1 /nobreak >nul
set /a docker_counter+=1
if %docker_counter% lss 120 goto wait_for_docker
echo Docker Desktop 未能在 120 秒内就绪。请确认它已安装并完成启动。
pause
exit /b 1

:docker_ready

set RAG_PORT=8001
for /f "tokens=1,* delims==" %%A in ('findstr /b /c:"RAG_PORT=" .env') do set RAG_PORT=%%B

docker compose images -q app | findstr . >nul
if errorlevel 1 goto first_build

echo 正在恢复 AI Trend Radar RAG 服务（复用已有镜像与数据）...
docker compose up -d --no-build
set compose_exit=%ERRORLEVEL%
goto compose_started

:first_build
echo 首次启动：正在构建 AI Trend Radar RAG 镜像（不会删除已有数据卷）...
docker compose up -d --build
set compose_exit=%ERRORLEVEL%

:compose_started
if not "%compose_exit%"=="0" (
  echo 启动失败。请检查 Docker Desktop 状态和上方错误信息。
  pause
  exit /b 1
)

echo 等待服务就绪（首次索引会在后台补全）...
set /a counter=0
:wait_for_health
curl -fsS http://127.0.0.1:%RAG_PORT%/health >nul 2>&1
if not errorlevel 1 goto service_ready
timeout /t 1 /nobreak >nul
set /a counter+=1
if %counter% lss 180 goto wait_for_health

echo 服务暂未在 180 秒内就绪。请查看：docker compose logs -f app
pause
exit /b 1

:service_ready
echo 服务已就绪：http://127.0.0.1:%RAG_PORT%
echo 首次运行时，最新日报会优先进入索引；历史语料继续在后台补全，可在 System 面板查看进度。
start http://127.0.0.1:%RAG_PORT%
