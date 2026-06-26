@echo off
chcp 65001 >nul
title AI Trend Radar RAG - 一键启动

echo.
echo ==========================================
echo   AI Trend Radar RAG - 一键启动
echo ==========================================
echo.

REM 步骤1: 检查Python环境
echo [INFO] 步骤 1/6: 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 未安装，请先安装 Python 3.11+
    echo [INFO] 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [SUCCESS] Python 已安装

REM 步骤2: 检查并创建虚拟环境
echo [INFO] 步骤 2/6: 检查Python虚拟环境...
if not exist ".venv" (
    echo [WARNING] 虚拟环境不存在，正在创建...
    python -m venv .venv
    echo [SUCCESS] 虚拟环境已创建
)
call .venv\Scripts\activate.bat
echo [SUCCESS] 虚拟环境已激活

REM 步骤3: 检查并安装Python依赖
echo [INFO] 步骤 3/6: 检查Python依赖...
if not exist ".venv\.deps_installed" (
    echo [WARNING] 正在安装Python依赖（首次运行需要几分钟）...
    pip install -q -r rag\requirements.txt
    echo. > .venv\.deps_installed
    echo [SUCCESS] Python依赖已安装
) else (
    echo [SUCCESS] Python依赖已安装
)

REM 步骤4: 检查并启动Neo4j
echo [INFO] 步骤 4/6: 检查Neo4j数据库...
docker ps 2>nul | findstr "ai-trend-radar-rag-claude" >nul
if errorlevel 1 (
    echo [WARNING] Neo4j未运行，正在启动...
    docker-compose up -d neo4j
    echo [SUCCESS] Neo4j已启动
    echo [INFO] 等待Neo4j就绪（约10秒）...
    timeout /t 10 /nobreak >nul
) else (
    echo [SUCCESS] Neo4j已运行
)

REM 步骤5: 同步最新数据
echo [INFO] 步骤 5/6: 同步最新数据...
if exist "scripts\sync-from-github.sh" (
    bash scripts\sync-from-github.sh
) else (
    echo [WARNING] 跳过数据同步（脚本不存在）
)

REM 步骤6: 启动RAG服务器
echo [INFO] 步骤 6/6: 启动RAG服务器...
echo [INFO] 正在启动服务器（端口 8001）...

REM 启动服务器（后台运行）
start /b python -m rag.server > rag-server.log 2>&1

REM 等待服务器启动
echo [INFO] 等待服务器就绪...
set /a counter=0
:wait_loop
timeout /t 1 /nobreak >nul
curl -s http://localhost:8001/health >nul 2>&1
if not errorlevel 1 (
    echo [SUCCESS] RAG服务器已启动
    goto :server_ready
)
set /a counter+=1
if %counter% lss 30 goto :wait_loop

echo [ERROR] RAG服务器启动失败，请检查日志: rag-server.log
pause
exit /b 1

:server_ready

REM 打开浏览器
echo [INFO] 正在打开浏览器...
start http://localhost:8001

echo.
echo ==========================================
echo   AI Trend Radar RAG 已启动！
echo ==========================================
echo.
echo 访问地址: http://localhost:8001
echo 服务器日志: rag-server.log
echo.
echo 功能说明：
echo   - 📊 仪表盘：查看AI趋势报告
echo   - 🤖 Agent：智能问答（点击右上角AGENT按钮）
echo   - ⚙️  系统状态：查看系统信息（点击右上角SYSTEM按钮）
echo   - 📋 Briefs：查看研究制品（点击右上角BRIEFS按钮）
echo.
echo 按任意键停止服务器...
pause >nul

REM 停止服务器
taskkill /f /im python.exe >nul 2>&1
echo [INFO] 服务器已停止
