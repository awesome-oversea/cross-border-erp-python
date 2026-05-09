$ErrorActionPreference = 'Stop'
$encoding = [System.Text.Encoding]::UTF8

$v10File = Get-ChildItem 'd:\Project\erp' -Filter '*V10.md' | Select-Object -First 1
$v9File = Get-ChildItem 'd:\Project\erp' -Filter '*V9.md' | Select-Object -First 1
$v11File = 'd:\Project\erp\跨境电商ERP系统详细设计说明书V11.md'

$v10 = Get-Content $v10File.FullName -Encoding UTF8
$v9 = Get-Content $v9File.FullName -Encoding UTF8

Write-Host "V10 lines: $($v10.Count)"
Write-Host "V9 lines: $($v9.Count)"

# Strategy: Use V10 as base, then merge V9-unique content
# We'll build V11 by processing V10 and inserting V9-unique sections

# Step 1: Start with V10 header updated to V11
$v11 = [System.Collections.ArrayList]::new()

# Update version info in header
foreach ($line in $v10) {
    $modified = $line
    if ($line -match '^\> \*\*版本\*\*：V10\.0') {
        $modified = $line -replace 'V10\.0', 'V11.0'
    }
    elseif ($line -match 'V10版本交叉验证优化说明') {
        $modified = $line -replace 'V10', 'V11'
    }
    elseif ($line -match 'V10统一原则') {
        $modified = $line -replace 'V10', 'V11'
    }
    elseif ($line -match 'V10定位') {
        $modified = $line -replace 'V10', 'V11'
    }
    elseif ($line -match 'ERP V10') {
        $modified = $line -replace 'ERP V10', 'ERP V11'
    }
    elseif ($line -match 'V10基础版本') {
        $modified = $line -replace 'V10基础版本', 'V10基础版本（V11合并V9+V10）'
    }
    elseif ($line -match 'V10.*当前详细设计主口径') {
        $modified = $line -replace 'V10', 'V11'
    }
    elseif ($line -match 'PMS V10') {
        $modified = $line -replace 'PMS V10', 'PMS V10'
    }
    elseif ($line -match 'V10建议池') {
        $modified = $line -replace 'V10', 'V11'
    }
    elseif ($line -match 'V10权限') {
        $modified = $line -replace 'V10', 'V11'
    }
    elseif ($line -match 'V10统一API路径') {
        $modified = $line -replace 'V10', 'V11'
    }
    elseif ($line -match 'V10 ERP-PMS') {
        $modified = $line -replace 'V10', 'V11'
    }
    [void]$v11.Add($modified)
}

Write-Host "Base V11 from V10: $($v11.Count) lines"

# Step 2: Find the insertion points in V11 for V9-unique content
# We need to insert V9-unique sections:
# 1. After 1.4.4 (Connector pattern), insert V9's 1.4.5 (分阶段演进原则) and 1.4.6 (ERP与PMS职责边界原则)
# 2. After 2.14 (SYS), insert V9's 2.15 (AI能力分布与职责边界)
# 3. After V10's 9.5.8 (异常处理), insert V9's 9.10.8 (建议执行事件回流)
# 4. After 9.5 (集成接口规范), insert V9's 9.5 (建议执行状态机), 9.6 (PMS写入规范), 9.7 (数据主权矩阵), 9.8 (14域交互矩阵), 9.9 (PMS数据接入方式矩阵)
# 5. Update appendix to include V9's content

# Let's find line numbers in V11 for insertions
$idx144_end = -1
$idx214_end = -1
$idx958_end = -1
$idx95_start = -1
$idx10_start = -1
$idxAppendix_start = -1

for ($i = 0; $i -lt $v11.Count; $i++) {
    $line = $v11[$i]
    # Find end of 1.4.4 (Connector pattern) - next ### or ## after 1.4.4
    if ($line -match '^#### 1\.4\.4 连接器模式') {
        # Find next #### or ### after this
        for ($j = $i + 1; $j -lt $v11.Count; $j++) {
            if ($v11[$j] -match '^#{2,4} 1\.[45]') {
                $idx144_end = $j
                break
            }
        }
    }
    # Find end of 2.14 (SYS domain) - next ## after 2.14
    if ($line -match '^### 2\.14 系统设置域') {
        for ($j = $i + 1; $j -lt $v11.Count; $j++) {
            if ($v11[$j] -match '^## [23]') {
                $idx214_end = $j
                break
            }
        }
    }
    # Find 9.5 集成接口规范 start
    if ($line -match '^### 9\.5 集成接口规范') {
        $idx95_start = $i
    }
    # Find end of 9.5.8 (异常处理) - next ## or ### after 9.5.8
    if ($line -match '^#### 9\.5\.8 异常处理与重试') {
        for ($j = $i + 1; $j -lt $v11.Count; $j++) {
            if ($v11[$j] -match '^## 10' -or $v11[$j] -match '^### 9\.[67]') {
                $idx958_end = $j
                break
            }
        }
    }
    # Find ## 10. 部署与运维
    if ($line -match '^## 10\. 部署与运维') {
        $idx10_start = $i
    }
    # Find appendix start
    if ($line -match '^# 附录A') {
        $idxAppendix_start = $i
    }
}

Write-Host "idx144_end (after 1.4.4): $idx144_end"
Write-Host "idx214_end (after 2.14): $idx214_end"
Write-Host "idx95_start (9.5 start): $idx95_start"
Write-Host "idx958_end (after 9.5.8): $idx958_end"
Write-Host "idx10_start (chapter 10): $idx10_start"
Write-Host "idxAppendix_start: $idxAppendix_start"

# Step 3: Extract V9-unique sections
# Extract V9 1.4.5 and 1.4.6
$v9_145_start = -1
$v9_145_end = -1
$v9_146_start = -1
$v9_146_end = -1
for ($i = 0; $i -lt $v9.Count; $i++) {
    if ($v9[$i] -match '^#### 1\.4\.5 分阶段演进原则') { $v9_145_start = $i }
    if ($v9[$i] -match '^#### 1\.4\.6 ERP与PMS职责边界原则') { $v9_146_start = $i }
    if ($v9_145_start -ge 0 -and $v9_145_end -lt 0 -and $i -gt $v9_145_start -and $v9[$i] -match '^#### 1\.4\.6') { $v9_145_end = $i }
    if ($v9_146_start -ge 0 -and $v9_146_end -lt 0 -and $i -gt $v9_146_start -and $v9[$i] -match '^### 1\.5') { $v9_146_end = $i }
}
Write-Host "V9 1.4.5: $v9_145_start - $v9_145_end"
Write-Host "V9 1.4.6: $v9_146_start - $v9_146_end"

# Extract V9 2.15 AI能力分布与职责边界
$v9_215_start = -1
$v9_215_end = -1
for ($i = 0; $i -lt $v9.Count; $i++) {
    if ($v9[$i] -match '^### 2\.15 AI能力分布与职责边界') { $v9_215_start = $i }
    if ($v9_215_start -ge 0 -and $v9_215_end -lt 0 -and $i -gt $v9_215_start -and $v9[$i] -match '^## 3') { $v9_215_end = $i }
}
Write-Host "V9 2.15: $v9_215_start - $v9_215_end"

# Extract V9 9.5 建议执行状态机
$v9_95_start = -1
$v9_95_end = -1
for ($i = 0; $i -lt $v9.Count; $i++) {
    if ($v9[$i] -match '^### 9\.5 建议执行状态机') { $v9_95_start = $i }
    if ($v9_95_start -ge 0 -and $v9_95_end -lt 0 -and $i -gt $v9_95_start -and $v9[$i] -match '^### 9\.6') { $v9_95_end = $i }
}
Write-Host "V9 9.5: $v9_95_start - $v9_95_end"

# Extract V9 9.6 PMS写入规范
$v9_96_start = -1
$v9_96_end = -1
for ($i = 0; $i -lt $v9.Count; $i++) {
    if ($v9[$i] -match '^### 9\.6 PMS写入规范') { $v9_96_start = $i }
    if ($v9_96_start -ge 0 -and $v9_96_end -lt 0 -and $i -gt $v9_96_start -and $v9[$i] -match '^### 9\.7') { $v9_96_end = $i }
}
Write-Host "V9 9.6: $v9_96_start - $v9_96_end"

# Extract V9 9.7 数据主权矩阵
$v9_97_start = -1
$v9_97_end = -1
for ($i = 0; $i -lt $v9.Count; $i++) {
    if ($v9[$i] -match '^### 9\.7 数据主权矩阵') { $v9_97_start = $i }
    if ($v9_97_start -ge 0 -and $v9_97_end -lt 0 -and $i -gt $v9_97_start -and $v9[$i] -match '^### 9\.8') { $v9_97_end = $i }
}
Write-Host "V9 9.7: $v9_97_start - $v9_97_end"

# Extract V9 9.8 PMS-ERP 14域交互矩阵
$v9_98_start = -1
$v9_98_end = -1
for ($i = 0; $i -lt $v9.Count; $i++) {
    if ($v9[$i] -match '^### 9\.8 PMS-ERP 14域交互矩阵') { $v9_98_start = $i }
    if ($v9_98_start -ge 0 -and $v9_98_end -lt 0 -and $i -gt $v9_98_start -and $v9[$i] -match '^### 9\.9') { $v9_98_end = $i }
}
Write-Host "V9 9.8: $v9_98_start - $v9_98_end"

# Extract V9 9.9 PMS数据接入方式矩阵
$v9_99_start = -1
$v9_99_end = -1
for ($i = 0; $i -lt $v9.Count; $i++) {
    if ($v9[$i] -match '^### 9\.9 PMS数据接入方式矩阵') { $v9_99_start = $i }
    if ($v9_99_start -ge 0 -and $v9_99_end -lt 0 -and $i -gt $v9_99_start -and $v9[$i] -match '^### 9\.10') { $v9_99_end = $i }
}
Write-Host "V9 9.9: $v9_99_start - $v9_99_end"

# Extract V9 9.10.8 建议执行事件回流
$v9_9108_start = -1
$v9_9108_end = -1
for ($i = 0; $i -lt $v9.Count; $i++) {
    if ($v9[$i] -match '^#### 9\.10\.8 建议执行事件回流') { $v9_9108_start = $i }
    if ($v9_9108_start -ge 0 -and $v9_9108_end -lt 0 -and $i -gt $v9_9108_start -and $v9[$i] -match '^#### 9\.10\.9') { $v9_9108_end = $i }
}
Write-Host "V9 9.10.8: $v9_9108_start - $v9_9108_end"

# Step 4: Build V11 with insertions
# We need to insert in reverse order to preserve line numbers

# First, let's build a new array with all insertions
$result = [System.Collections.ArrayList]::new()

# Process V11 line by line, inserting V9 content at appropriate points
$inserted = @{}

for ($i = 0; $i -lt $v11.Count; $i++) {
    # Insert V9 1.4.5 and 1.4.6 after 1.4.4
    if ($i -eq $idx144_end -and -not $inserted['1.4.5']) {
        Write-Host "Inserting V9 1.4.5 and 1.4.6 at line $i"
        if ($v9_145_start -ge 0 -and $v9_145_end -ge 0) {
            for ($j = $v9_145_start; $j -lt $v9_145_end; $j++) {
                [void]$result.Add($v9[$j])
            }
        }
        if ($v9_146_start -ge 0 -and $v9_146_end -ge 0) {
            for ($j = $v9_146_start; $j -lt $v9_146_end; $j++) {
                [void]$result.Add($v9[$j])
            }
        }
        [void]$result.Add('')
        $inserted['1.4.5'] = $true
    }

    # Insert V9 2.15 AI能力分布与职责边界 after 2.14
    if ($i -eq $idx214_end -and -not $inserted['2.15']) {
        Write-Host "Inserting V9 2.15 at line $i"
        if ($v9_215_start -ge 0 -and $v9_215_end -ge 0) {
            for ($j = $v9_215_start; $j -lt $v9_215_end; $j++) {
                [void]$result.Add($v9[$j])
            }
        }
        [void]$result.Add('')
        $inserted['2.15'] = $true
    }

    # After 9.5.8 (异常处理), insert V9 9.10.8 (建议执行事件回流)
    if ($i -eq $idx958_end -and -not $inserted['9.10.8']) {
        # First add the current line
        [void]$result.Add($v11[$i])
        Write-Host "Inserting V9 9.10.8 at line $i"
        if ($v9_9108_start -ge 0 -and $v9_9108_end -ge 0) {
            [void]$result.Add('')
            for ($j = $v9_9108_start; $j -lt $v9_9108_end; $j++) {
                # Renumber 9.10.8 -> 9.5.9
                $l = $v9[$j] -replace '9\.10\.8', '9.5.9'
                [void]$result.Add($l)
            }
        }
        $inserted['9.10.8'] = $true
        continue
    }

    # After V10's 9.7 (V10权限、事件、数据主权与反馈矩阵), insert V9's 9.5/9.6/9.7/9.8/9.9
    # We need to find the end of 9.7 in V11
    # V10's 9.6 and 9.7 are listed in the TOC but let's check where they actually are
    # Actually, V10's 9.6 and 9.7 seem to be just TOC entries, not actual content sections
    # Let me check...

    [void]$result.Add($v11[$i])
}

Write-Host "Result after first pass: $($result.Count) lines"

# Now let's check if V10 actually has 9.6 and 9.7 content sections
$has_96_content = $false
$has_97_content = $false
for ($i = 0; $i -lt $result.Count; $i++) {
    if ($result[$i] -match '^### 9\.6 V11建议池') { $has_96_content = $true }
    if ($result[$i] -match '^### 9\.7 V11权限') { $has_97_content = $true }
}
Write-Host "Has 9.6 content: $has_96_content"
Write-Host "Has 9.7 content: $has_97_content"

# Save intermediate result
$result | Set-Content $v11File -Encoding UTF8
Write-Host "V11 saved: $($result.Count) lines"
