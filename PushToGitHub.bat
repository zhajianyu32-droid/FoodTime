@echo off
chcp 65001 >nul
REM ============================================================
REM FoodTime 推送到 GitHub
REM ------------------------------------------------------------
REM 背景：git for Windows 无法处理含中文的仓库路径（"校招"），
REM       因此这里把项目同步到纯 ASCII 路径的副本再推送。
REM
REM 用法：双击本文件，或在 PowerShell / CMD 中运行。
REM ============================================================

setlocal

set "SRC=C:\Users\zjy\Desktop\校招\FoodTime"
set "DST=C:\Users\zjy\Desktop\FoodTime-push"
set "MSG=%~1"

if "%MSG%"=="" set "MSG=update: 同步本地改动"

echo [1/4] 源目录 : %SRC%
echo [1/4] 副本   : %DST%
echo.

REM ---- 用 robocopy 同步（排除依赖、密钥、缓存）----
echo [2/4] 同步文件...
robocopy "%SRC%" "%DST%" /MIR ^
  /XD node_modules venv .venv dist __pycache__ .git .workbuddy logs .pytest_cache .vite ^
  /XF .env .env.local .env.production .env.test "*.db" "*.log" "*.pyc" "*.tsbuildinfo" ^
  /NFL /NDL /NJH /NJS /NP >nul

if %ERRORLEVEL% GEQ 8 (
  echo.
  echo ✗ 同步失败，robocopy 返回码 %ERRORLEVEL%
  pause
  exit /b 1
)

cd /d "%DST%"

echo [3/4] 提交...
git add -A
git commit -m "%MSG%"

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo ℹ 没有新的改动需要提交
  goto :push
)

:push
echo [4/4] 推送...
git push origin main

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo ✗ 推送失败。可能原因：
  echo   - 网络不通
  echo   - 未配置 GitHub 凭据
  pause
  exit /b 1
)

echo.
echo ✅ 已推送到 https://github.com/zhajianyu32-droid/FoodTime
echo.
pause
