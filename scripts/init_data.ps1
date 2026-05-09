<#
  P9-007 初始化数据准备脚本
  用途：创建初始字典、权限、租户、渠道、仓库等基础数据
  所有路径已锁定 D 盘，C 盘零写入
#>

param(
    [string]$API_BASE = "http://localhost:8000",
    [string]$TENANT_ID = "tenant-default",
    [string]$ADMIN_USER = "admin"
)

Write-Host "=== 初始化数据准备 ===" -ForegroundColor Cyan
Write-Host "API: $API_BASE" -ForegroundColor Yellow

$headers = @{
    "X-Tenant-ID" = $TENANT_ID
    "X-Actor-ID" = $ADMIN_USER
    "X-Actor-Type" = "user"
    "Content-Type" = "application/json"
}

$successCount = 0
$failCount = 0

function Invoke-Api {
    param([string]$Method, [string]$Path, [object]$Body = $null)
    try {
        if ($Body) {
            $jsonBody = $Body | ConvertTo-Json -Depth 10
            $resp = Invoke-RestMethod -Uri "$API_BASE$Path" -Method $Method -Headers $headers -Body $jsonBody -ErrorAction Stop
        } else {
            $resp = Invoke-RestMethod -Uri "$API_BASE$Path" -Method $Method -Headers $headers -ErrorAction Stop
        }
        $script:successCount++
        return $resp
    } catch {
        $script:failCount++
        Write-Host "  [FAIL] $Method $Path : $_" -ForegroundColor Red
        return $null
    }
}

# 1. 初始化字典
Write-Host "[1/6] 初始化数据字典..." -ForegroundColor Yellow
Write-Host "[1/8] Init dictionaries..." -ForegroundColor Yellow
Invoke-Api -Method "POST" -Path "/api/sys/dicts/init-defaults"

# 2. 初始化系统参数
Write-Host "[2/6] 初始化系统参数..." -ForegroundColor Yellow
Write-Host "[2/8] Init system params..." -ForegroundColor Yellow
Invoke-Api -Method "POST" -Path "/api/sys/params/init-defaults"

# 3. 初始化单据编号规则
Write-Host "[3/6] 初始化单据编号规则..." -ForegroundColor Yellow
Write-Host "[3/8] Init document number rules..." -ForegroundColor Yellow
Invoke-Api -Method "POST" -Path "/api/sys/doc-number-rules/init-defaults"

# 4. 初始化事件目录
Write-Host "[4/6] 初始化事件目录..." -ForegroundColor Yellow
Write-Host "[4/8] Init event catalog..." -ForegroundColor Yellow
Invoke-Api -Method "POST" -Path "/api/sys/event-catalog/init-defaults"

# 5. 初始化导入模板
Write-Host "[5/6] 初始化导入模板..." -ForegroundColor Yellow
Write-Host "[5/8] Init import templates..." -ForegroundColor Yellow
Invoke-Api -Method "POST" -Path "/api/sys/imports/templates/init-defaults"

# 6. 初始化主数据治理规则
Write-Host "[6/6] 初始化主数据治理规则..." -ForegroundColor Yellow
Invoke-Api -Method "POST" -Path "/api/sys/master-data-governance/init-defaults"

# 7. initialize content review default rules
Write-Host "[7/8] Init content review default rules..." -ForegroundColor Yellow
Invoke-Api -Method "POST" -Path "/api/sys/api/v1/content-review/rules/init-defaults"

# 8. initialize forex alert default rules
Write-Host "[8/8] Init forex alert default rules..." -ForegroundColor Yellow
Invoke-Api -Method "POST" -Path "/api/fms/api/v1/forex/alert-rules/init-defaults"

Write-Host ""
Write-Host "=== 初始化完成 ===" -ForegroundColor Cyan
Write-Host "成功: $successCount  失败: $failCount" -ForegroundColor $(if($failCount -eq 0){"Green"}else{"Yellow"})

if ($failCount -gt 0) {
    Write-Host "注意：部分初始化失败，请检查API服务是否正常运行" -ForegroundColor Yellow
}
