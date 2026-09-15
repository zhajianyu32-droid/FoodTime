# ============================================================
# 美味出租屋 - 环境切换脚本
# 用法:
#   .\switch_env.ps1 test        # 切换到测试环境
#   .\switch_env.ps1 production  # 切换到正式环境
#   .\switch_env.ps1 status      # 查看当前环境
# ============================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("test", "production", "status")]
    [string]$Action = "status"
)

$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $backendDir "backend\.env"
$envTest = Join-Path $backendDir "backend\.env.test"
$envProd = Join-Path $backendDir "backend\.env.production"

function Get-CurrentEnv {
    if (Test-Path $envFile) {
        $content = Get-Content $envFile
        $envLine = $content | Where-Object { $_ -match "^APP_ENV=" } | Select-Object -First 1
        if ($envLine) {
            return $envLine.Split("=")[1].Trim()
        }
    }
    return "unknown"
}

$current = Get-CurrentEnv

if ($Action -eq "status") {
    Write-Host ""
    Write-Host "===== 美味出租屋 环境状态 =====" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  当前环境: " -NoNewline
    if ($current -eq "production") {
        Write-Host "PRODUCTION (正式)" -ForegroundColor Green
    } elseif ($current -eq "test") {
        Write-Host "TEST (测试)" -ForegroundColor Yellow
    } else {
        Write-Host $current -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "  配置文件: $envFile"
    Write-Host ""
    Write-Host "  可用操作:" -ForegroundColor DarkGray
    Write-Host "    .\switch_env.ps1 test        -> 切换到测试环境 (Gourmet_House_test)"
    Write-Host "    .\switch_env.ps1 production  -> 切换到正式环境 (Gourmet_House)"
    Write-Host "    .\switch_env.ps1 status       -> 查看当前状态"
    Write-Host ""
    return
}

if ($Action -eq "test") {
    if ($current -eq "test") {
        Write-Host "已经是测试环境，无需切换" -ForegroundColor Yellow
        return
    }
    if (Test-Path $envTest) {
        Copy-Item $envTest $envFile -Force
        Write-Host ""
        Write-Host "===== 已切换到测试环境 =====" -ForegroundColor Yellow
        Write-Host "  数据库: Gourmet_House_test"
        Write-Host "  DEBUG:  true"
        Write-Host ""
        Write-Host "  请重启后端服务使配置生效:" -ForegroundColor DarkGray
        Write-Host "    cd backend" -ForegroundColor DarkGray
        Write-Host "    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload" -ForegroundColor DarkGray
        Write-Host ""
    } else {
        Write-Host "找不到 .env.test 文件" -ForegroundColor Red
    }
    return
}

if ($Action -eq "production") {
    if ($current -eq "production") {
        Write-Host "已经是正式环境，无需切换" -ForegroundColor Green
        return
    }
    if (Test-Path $envProd) {
        Write-Host ""
        Write-Host "!!! 警告 !!!" -ForegroundColor Red
        Write-Host "  即将切换到正式环境 (PRODUCTION)"
        Write-Host "  数据库: Gourmet_House (真实数据)"
        Write-Host "  DEBUG:  false"
        Write-Host ""
        $confirm = Read-Host "确认切换? (yes/no)"
        if ($confirm -ne "yes") {
            Write-Host "已取消" -ForegroundColor Yellow
            return
        }
        Copy-Item $envProd $envFile -Force
        Write-Host ""
        Write-Host "===== 已切换到正式环境 =====" -ForegroundColor Green
        Write-Host "  数据库: Gourmet_House"
        Write-Host "  DEBUG:  false"
        Write-Host ""
        Write-Host "  请重启后端服务使配置生效:" -ForegroundColor DarkGray
        Write-Host "    cd backend" -ForegroundColor DarkGray
        Write-Host "    python -m uvicorn main:app --host 0.0.0.0 --port 8000" -ForegroundColor DarkGray
        Write-Host ""
    } else {
        Write-Host "找不到 .env.production 文件" -ForegroundColor Red
    }
    return
}
