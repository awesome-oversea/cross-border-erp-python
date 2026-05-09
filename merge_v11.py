import re
import os

v10_path = None
v9_path = None
for f in os.listdir(r'd:\Project\erp'):
    if f.endswith('V10.md'):
        v10_path = os.path.join(r'd:\Project\erp', f)
    elif f.endswith('V9.md'):
        v9_path = os.path.join(r'd:\Project\erp', f)

print(f"V10: {v10_path}")
print(f"V9: {v9_path}")

with open(v10_path, 'r', encoding='utf-8') as f:
    v10 = f.readlines()

with open(v9_path, 'r', encoding='utf-8') as f:
    v9 = f.readlines()

print(f"V10 lines: {len(v10)}")
print(f"V9 lines: {len(v9)}")

# Step 1: Use V10 as base, update version references
v11 = []
for line in v10:
    l = line
    if l.startswith('> **版本**：V10.0'):
        l = l.replace('V10.0', 'V11.0')
    elif 'V10版本交叉验证优化说明' in l:
        l = l.replace('V10', 'V11')
    elif 'V10统一原则' in l:
        l = l.replace('V10', 'V11')
    elif 'V10定位' in l:
        l = l.replace('V10', 'V11')
    elif 'ERP V10' in l and 'V10基础' not in l:
        l = l.replace('ERP V10', 'ERP V11')
    elif 'V10基础版本' in l:
        l = l.replace('V10基础版本', 'V10基础版本（V11合并V9+V10）')
    elif 'V10' in l and '当前详细设计主口径' in l:
        l = l.replace('V10', 'V11')
    elif 'V10建议池' in l:
        l = l.replace('V10', 'V11')
    elif 'V10权限' in l and 'V10权限、事件' in l:
        l = l.replace('V10', 'V11')
    elif 'V10统一API路径' in l:
        l = l.replace('V10', 'V11')
    elif 'V10 ERP-PMS' in l:
        l = l.replace('V10', 'V11')
    v11.append(l)

print(f"Base V11 from V10: {len(v11)} lines")

# Step 2: Find section boundaries in V9
def find_section_start(lines, pattern):
    for i, line in enumerate(lines):
        if re.search(pattern, line):
            return i
    return -1

def find_section_end(lines, start, next_pattern):
    for i in range(start + 1, len(lines)):
        if re.search(next_pattern, lines[i]):
            return i
    return len(lines)

# V9 sections to extract
v9_145_start = find_section_start(v9, r'^#### 1\.4\.5 分阶段演进原则')
v9_145_end = find_section_end(v9, v9_145_start, r'^#### 1\.4\.6')
v9_146_start = find_section_start(v9, r'^#### 1\.4\.6 ERP与PMS职责边界原则')
v9_146_end = find_section_end(v9, v9_146_start, r'^### 1\.5')
v9_215_start = find_section_start(v9, r'^### 2\.15 AI能力分布与职责边界')
v9_215_end = find_section_end(v9, v9_215_start, r'^## 3')
v9_95_start = find_section_start(v9, r'^### 9\.5 建议执行状态机')
v9_95_end = find_section_end(v9, v9_95_start, r'^### 9\.6')
v9_96_start = find_section_start(v9, r'^### 9\.6 PMS写入规范')
v9_96_end = find_section_end(v9, v9_96_start, r'^### 9\.7')
v9_97_start = find_section_start(v9, r'^### 9\.7 数据主权矩阵')
v9_97_end = find_section_end(v9, v9_97_start, r'^### 9\.8')
v9_98_start = find_section_start(v9, r'^### 9\.8 PMS-ERP 14域交互矩阵')
v9_98_end = find_section_end(v9, v9_98_start, r'^### 9\.9')
v9_99_start = find_section_start(v9, r'^### 9\.9 PMS数据接入方式矩阵')
v9_99_end = find_section_end(v9, v9_99_start, r'^### 9\.10')
v9_9108_start = find_section_start(v9, r'^#### 9\.10\.8 建议执行事件回流')
v9_9108_end = find_section_end(v9, v9_9108_start, r'^#### 9\.10\.9')

print(f"V9 1.4.5: {v9_145_start}-{v9_145_end}")
print(f"V9 1.4.6: {v9_146_start}-{v9_146_end}")
print(f"V9 2.15: {v9_215_start}-{v9_215_end}")
print(f"V9 9.5: {v9_95_start}-{v9_95_end}")
print(f"V9 9.6: {v9_96_start}-{v9_96_end}")
print(f"V9 9.7: {v9_97_start}-{v9_97_end}")
print(f"V9 9.8: {v9_98_start}-{v9_98_end}")
print(f"V9 9.9: {v9_99_start}-{v9_99_end}")
print(f"V9 9.10.8: {v9_9108_start}-{v9_9108_end}")

# Step 3: Find insertion points in V11
# After 1.4.4 连接器模式
idx_144 = find_section_start(v11, r'^#### 1\.4\.4 连接器模式')
idx_after_144 = find_section_end(v11, idx_144, r'^### 1\.5|^#### 1\.4\.5|^#### 1\.4\.6|^## 1\.6')
print(f"After 1.4.4: insert at {idx_after_144}")

# After 2.14 系统设置域
idx_214 = find_section_start(v11, r'^### 2\.14 系统设置域')
idx_after_214 = find_section_end(v11, idx_214, r'^## 3')
print(f"After 2.14: insert at {idx_after_214}")

# After 9.5.8 异常处理与重试
idx_958 = find_section_start(v11, r'^#### 9\.5\.8 异常处理与重试')
idx_after_958 = find_section_end(v11, idx_958, r'^## 10|^### 9\.[67]')
print(f"After 9.5.8: insert at {idx_after_958}")

# Find 9.6 and 9.7 in V11 (V10's sections)
idx_96 = find_section_start(v11, r'^### 9\.6 V11建议池')
idx_97 = find_section_start(v11, r'^### 9\.7 V11权限')
print(f"9.6 in V11: {idx_96}")
print(f"9.7 in V11: {idx_97}")

# Find end of 9.7 or chapter 9
idx_ch10 = find_section_start(v11, r'^## 10\. 部署与运维')
print(f"Chapter 10: {idx_ch10}")

# Step 4: Build final V11 with insertions
# We need to carefully merge. The strategy:
# - Insert V9's 1.4.5 and 1.4.6 after V10's 1.4.4
# - Insert V9's 2.15 after V10's 2.14
# - After V10's 9.5.8, insert V9's 9.10.8 (renumbered to 9.5.9)
# - After V10's 9.7, insert V9's 9.5/9.6/9.7/9.8/9.9 (renumbered to 9.8/9.9/9.10/9.11/9.12)
# - Update TOC

result = []
i = 0
while i < len(v11):
    line = v11[i]

    # Insert V9 1.4.5 and 1.4.6 after 1.4.4 section ends
    if i == idx_after_144:
        if v9_145_start >= 0:
            result.append('\n')
            for j in range(v9_145_start, v9_145_end):
                result.append(v9[j])
        if v9_146_start >= 0:
            for j in range(v9_146_start, v9_146_end):
                result.append(v9[j])
        result.append('\n')

    # Insert V9 2.15 after 2.14 section ends
    if i == idx_after_214:
        if v9_215_start >= 0:
            result.append('\n')
            for j in range(v9_215_start, v9_215_end):
                result.append(v9[j])
            result.append('\n')

    # After 9.5.8, insert V9's 9.10.8 (建议执行事件回流) renumbered as 9.5.9
    if i == idx_after_958:
        result.append(line)
        if v9_9108_start >= 0:
            result.append('\n')
            for j in range(v9_9108_start, v9_9108_end):
                l = v9[j].replace('9.10.8', '9.5.9')
                result.append(l)
            result.append('\n')
        i += 1
        continue

    # After V10's 9.7 section (or before chapter 10 if 9.6/9.7 don't have content),
    # insert V9's unique PMS integration sections
    # Check if we're at the line before chapter 10
    if i == idx_ch10 - 1 and idx_96 < 0 and idx_97 < 0:
        # V10 doesn't have 9.6/9.7 content sections, just TOC entries
        # Insert V9 sections before chapter 10
        pass

    result.append(line)
    i += 1

# Now handle the V9 PMS integration sections (9.5-9.9 from V9)
# These need to go after V10's 9.7 (which may just be TOC entries)
# Let's find where to insert them - before chapter 10

# Find chapter 10 in result
idx_ch10_result = -1
for i, line in enumerate(result):
    if re.search(r'^## 10\. 部署与运维', line):
        idx_ch10_result = i
        break

print(f"Chapter 10 in result: {idx_ch10_result}")

# Insert V9's PMS sections before chapter 10
# Renumber: V9's 9.5->9.8, 9.6->9.9, 9.7->9.10, 9.8->9.11, 9.9->9.12
v9_pms_sections = []
if v9_95_start >= 0:
    for j in range(v9_95_start, v9_95_end):
        l = v9[j].replace('### 9.5 建议执行状态机', '### 9.8 建议执行状态机')
        v9_pms_sections.append(l)
    v9_pms_sections.append('\n')
if v9_96_start >= 0:
    for j in range(v9_96_start, v9_96_end):
        l = v9[j].replace('### 9.6 PMS写入规范', '### 9.9 PMS写入规范')
        v9_pms_sections.append(l)
    v9_pms_sections.append('\n')
if v9_97_start >= 0:
    for j in range(v9_97_start, v9_97_end):
        l = v9[j].replace('### 9.7 数据主权矩阵', '### 9.10 数据主权矩阵')
        v9_pms_sections.append(l)
    v9_pms_sections.append('\n')
if v9_98_start >= 0:
    for j in range(v9_98_start, v9_98_end):
        l = v9[j].replace('### 9.8 PMS-ERP 14域交互矩阵', '### 9.11 PMS-ERP 14域交互矩阵')
        v9_pms_sections.append(l)
    v9_pms_sections.append('\n')
if v9_99_start >= 0:
    for j in range(v9_99_start, v9_99_end):
        l = v9[j].replace('### 9.9 PMS数据接入方式矩阵', '### 9.12 PMS数据接入方式矩阵')
        v9_pms_sections.append(l)
    v9_pms_sections.append('\n')

if idx_ch10_result >= 0 and v9_pms_sections:
    # Find the --- separator before chapter 10
    insert_pos = idx_ch10_result
    for k in range(idx_ch10_result - 1, max(0, idx_ch10_result - 5), -1):
        if result[k].strip() == '---':
            insert_pos = k
            break
    print(f"Inserting V9 PMS sections at position {insert_pos}")
    result = result[:insert_pos] + ['\n'] + v9_pms_sections + result[insert_pos:]

# Step 5: Update TOC to reflect new sections
# Find TOC section and update it
toc_start = -1
toc_end = -1
for i, line in enumerate(result):
    if line.strip() == '## 目录':
        toc_start = i
    elif toc_start >= 0 and toc_end < 0 and line.strip().startswith('---') and i > toc_start + 5:
        toc_end = i
        break

print(f"TOC: {toc_start}-{toc_end}")

if toc_start >= 0:
    # Build new TOC
    new_toc = [
        '## 目录\n',
        '\n',
        '1. **ERP系统概述**\n',
        '   1.1 系统定位\n',
        '   1.2 系统边界\n',
        '   1.3 核心业务流程\n',
        '   1.4 架构原则\n',
        '   1.5 技术架构总览\n',
        '   1.6 V11版本交叉验证优化说明\n',
        '2. **业务领域模型设计**\n',
        '   2.1 工作台域 (DASHBOARD) ★ [AI看板]\n',
        '   2.2 组织权限域 (IAM)\n',
        '   2.3 产品开发域 (PDM) ★ [AI选品]\n',
        '   2.4 销售运营域 (SOM)\n',
        '   2.5 广告管理域 (ADS) ★ [AI优化]\n',
        '   2.6 订单域 (OMS) ★ [AI风控]\n',
        '   2.7 供应链域 (SCM) ★ [AI补货]\n',
        '   2.8 仓储域 (WMS) ★ [AI预测]\n',
        '   2.9 FBA/海外仓域 (FBA)\n',
        '   2.10 物流域 (TMS)\n',
        '   2.11 客服售后域 (CRM) ★ [AI情感]\n',
        '   2.12 财务域 (FMS) ★ [AI成本归集]\n',
        '   2.13 商业智能域 (BI) ★ [KPI]\n',
        '   2.14 系统设置域 (SYS)\n',
        '   2.15 AI能力分布与职责边界\n',
        '3. **数据库详细设计**\n',
        '   3.1 DASHBOARD数据库\n',
        '   3.2 IAM数据库\n',
        '   3.3 PDM数据库\n',
        '   3.4 SOM数据库\n',
        '   3.5 ADS数据库\n',
        '   3.6 OMS数据库\n',
        '   3.7 SCM数据库\n',
        '   3.8 WMS数据库\n',
        '   3.9 FBA数据库\n',
        '   3.10 TMS数据库\n',
        '   3.11 CRM数据库\n',
        '   3.12 FMS数据库\n',
        '   3.13 BI数据库\n',
        '   3.14 SYS数据库\n',
        '4. **API接口详细设计**\n',
        '   4.1 工作台接口\n',
        '   4.2 组织权限接口\n',
        '   4.3 PDM接口\n',
        '   4.4 SOM接口\n',
        '   4.5 ADS接口\n',
        '   4.6 OMS接口\n',
        '   4.7 SCM接口\n',
        '   4.8 WMS接口\n',
        '   4.9 FBA接口\n',
        '   4.10 TMS接口\n',
        '   4.11 CRM接口\n',
        '   4.12 FMS接口\n',
        '   4.13 BI接口\n',
        '   4.14 SYS接口\n',
        '   4.15 PMS集成接口\n',
        '   4.16 V11统一API路径与集成安全规范\n',
        '5. **业务中台设计**\n',
        '   5.1 内容审核中心\n',
        '   5.2 货币汇率中心\n',
        '   5.3 国内外支付聚合中心\n',
        '   5.4 订单策略中心\n',
        '   5.5 物流策略中心\n',
        '   5.6 计费策略中心\n',
        '   5.7 客户数据平台 (CDP)\n',
        '   5.8 发票税务中台\n',
        '   5.9 合规风控中台\n',
        '   5.10 选品分析中台\n',
        '   5.11 广告优化中台\n',
        '   5.12 成本归集引擎\n',
        '   5.13 利润核算引擎\n',
        '   5.14 进销存凭证引擎\n',
        '6. **技术能力中台设计**\n',
        '   6.1 消息通知中心\n',
        '   6.2 文件处理中心\n',
        '   6.3 工作流引擎\n',
        '   6.4 任务调度中心\n',
        '   6.5 权限管理中心\n',
        '   6.6 日志审计中心\n',
        '   6.7 API网关\n',
        '   6.8 多语言翻译中心\n',
        '   6.9 数据脱敏中心\n',
        '   6.10 API管理平台\n',
        '   6.11 连接器管理平台\n',
        '7. **连接器设计**\n',
        '   7.1 连接器架构\n',
        '   7.2 平台连接器\n',
        '   7.3 物流连接器\n',
        '   7.4 支付连接器\n',
        '   7.5 仓储连接器\n',
        '   7.6 采购连接器\n',
        '   7.7 智能服务连接器\n',
        '8. **CDC数据同步设计**\n',
        '   8.1 CDC架构\n',
        '   8.2 各域CDC配置\n',
        '   8.3 数据格式规范\n',
        '9. **与PMS集成设计**\n',
        '   9.1 集成架构\n',
        '   9.2 数据输入（AI感知）\n',
        '   9.3 数据输出（AI驱动）\n',
        '   9.4 闭环反馈设计\n',
        '   9.5 集成接口规范\n',
        '   9.6 V11建议池、草稿单据与审批执行闭环\n',
        '   9.7 V11权限、事件、数据主权与反馈矩阵\n',
        '   9.8 建议执行状态机\n',
        '   9.9 PMS写入规范\n',
        '   9.10 数据主权矩阵\n',
        '   9.11 PMS-ERP 14域交互矩阵\n',
        '   9.12 PMS数据接入方式矩阵\n',
        '10. **部署与运维**\n',
        '    10.1 部署架构\n',
        '    10.2 高可用配置\n',
        '    10.3 监控告警\n',
        '    10.4 灾备方案\n',
        '\n',
        '---\n',
        '\n',
    ]
    if toc_end >= 0:
        result = result[:toc_start] + new_toc + result[toc_end+1:]

# Step 6: Update the version适用说明 table
# Find and update it
for i, line in enumerate(result):
    if 'V10（本文档）' in line or '**V10**' in line and '当前' in line:
        result[i] = line.replace('V10', 'V11')
    elif 'V9' in line and '当前主设计口径' in line:
        result[i] = line.replace('V9（本文档）', 'V9').replace('当前主设计口径', '历史参考（已合并至V11）')

# Step 7: Update the footer
for i, line in enumerate(result):
    if 'V7.0' in line and '详细设计说明书' in line:
        result[i] = line.replace('V7.0', 'V11.0')

# Step 8: Update 9.5 sub-section that references 9.10 in V9
# The V10's 9.5 section header has sub-references
for i, line in enumerate(result):
    if '9.6 V11建议池' in line and line.strip().startswith('9.6'):
        result[i] = line.replace('9.6 V11建议池', '9.6 V11建议池')
    if '9.7 V11权限' in line and line.strip().startswith('9.7'):
        result[i] = line.replace('9.7 V11权限', '9.7 V11权限')

# Write result
v11_path = r'd:\Project\erp\跨境电商ERP系统详细设计说明书V11.md'
with open(v11_path, 'w', encoding='utf-8') as f:
    f.writelines(result)

print(f"V11 saved: {len(result)} lines")
print("Done!")
