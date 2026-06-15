---
#名称
name: my-skill
#指导说明
description: 该cross_env_manager项目相关指导操作

#指导说明Instructions
#示例用法Example Usage
---

# Instructions

在该文件夹内编写技能相关的代码和资源文件，技能的具体实现可以根据项目需求进行设计和开发。
以及需要查看日志时需要查看该 skill

## 重要: 生产环境安全策略

### 生产服务器访问限制
- **禁止 SSH 连接** 所有生产离线环境服务器（如 10.68.2.40 等）
- **仅允许以下操作**:
  1. **HTTP API 升级**: `POST /api/system/upgrade` 通过 5000 端口上传升级包
  2. **HTTP 查看日志**: 通过 `POST /addtask/query` 或 Postlook 服务页面查看
  3. **Web 页面管理**: 通过浏览器访问生产服务器 Web 界面进行操作
- **原因**: 生产环境为离线网络，SSH 端口未开放/不可达，且出于安全考虑禁止直连

### 升级操作流程
```
开发环境修改代码 → git commit
                → python scripts/build_upgrade.py --server http://生产IP:5000
                → 自动打包增量 → 上传 → 服务器自重启
```

### 日志查看方式
- 通过浏览器访问 `http://生产IP:5000` → 查询页面 / 调车看板
- 通过 Postlook 服务 `http://生产IP:5011` → 日志查询页面

### 本地测试
使用supervisorctl restart cross_env2_manager进行本地环境重启

## Example Usage

## 重要文件夹
- templates/ - 存放HTML模板文件
   - index.html - 主页面模板
   - components/ - 存放页面组件模板

- static/ - 存放静态资源文件（CSS、JS、图片等）
- deploy_iraypleos/ - 存放离线部署相关脚本和资源
- test/ - 存放测试脚本和测试资源

- skill/ - 存放需要用到的技能，需要同步阅读，在这里更新并整理，api文档也需要在这里更新汇总整理分类，允许创建文件夹，更新后需要同步修改

  - skill/log_viewer.md - 调车模块日志查看指导，当用户要求查询对应ip地址的服务器日志时查看该文档，查询日志时优先查询生产环境的日志，如果生产环境日志不完整或缺失，则排查原因，修正日志打印错误，补充日志内容。

- doc/ - 存放相关文档，对应模块有对应的文档，在这里更新并整理，api文档也需要在这里更新汇总整理分类，允许创建文件夹，更新后需要同步修改

## 离线部署相关

### 部署脚本位置
`deploy_iraypleos/deploy_iraypleos.sh` - 作为离线部署脚本,同时用于更新后续的部署测试验证。

### 重要更新（2026-04-17）
1. **完全离线支持**：所有外部Web依赖已下载到本地 `static/vendor/` 目录
2. **依赖包修复**：添加了缺失的 `importlib_metadata==8.7.1` 依赖包
3. **代码修复**：修复了 `back_wait_time` 数据处理错误（int对象没有strip方法）
4. **部署逻辑改进**：改进了mysql.connector检测逻辑，只检测未注释的导入

### 本地Web依赖说明
项目已将所有外部Web依赖下载到本地，支持完全离线运行：
- **Bootstrap 5.3.0**：主界面使用
- **Bootstrap 5.1.3**：查询页面使用  
- **Bootstrap Icons**：图标库
- **Animate.css**：动画效果
- **Sortable.js**：拖拽排序
- **Chart.js**：图表展示
- **Font Awesome**：图标字体

所有依赖文件位于 `static/vendor/` 目录，模板文件已更新为使用本地路径。

### 部署流程
1. 新增Python依赖时，需要同时更新离线依赖包（vendor_packages3.9目录）
2. 新增Web依赖时，需要下载到 `static/vendor/` 对应目录并更新模板文件
3. 在部署脚本中添加相应的安装步骤
4. 更新requirements.txt文件

### 配置文件验证
确认 `config/env.toml` 中内容为：
```
[database]
host = "47.98.244.173"
port = 53308
user = "root"
password = "Qq13235202993"
name = "wms"
charset = "utf8mb4"
```
时，可以进行数据库插入和编辑操作。同时这个数据也可以作为你的测试数据库，可以自由操作及创建表和数据，但请勿修改其他配置文件以确保数据安全和环境隔离。

**重要**：该地址数据库为测试用数据库，其他配置文件则不允许操作，以确保数据安全和环境隔离。

此电脑可连接上生产环境数据库，允许读取生产环境的数据库内容，并拷贝表结构和部分数据至测试环境数据库，但不允许修改生产环境数据库内容。
以下为生产环境数据库的连接信息，仅作为参考，测试时优先从生产环境中获取表结构和部分数据至测试数据库后进行测试。
```
[database]
host = "10.68.2.32"
port = 3306
user = "wms"
password = "CCshenda889"
name = "wms"
charset = "utf8mb4"
```

### 测试验证

在确认可以进行操作后，执行离线部署脚本进行测试：
```bash
cd /main/app/toolsForPersonal/projects/agv_system/app/cross_env_manager
./deploy_iraypleos/deploy_iraypleos.sh
```

验证数据库操作相关功能是否正常工作：
1. 搜索功能
2. 模板详情查看
3. 编辑功能
4. 复制模版功能
5. 添加子任务
6. 删除子任务

检查日志：/main/app/log/cross_env_manager.log
确认没有错误日志输出。

### 1.3项目功能整合

项目已成功整合1.3项目的AGV任务查询功能，新增了以下功能模块：

#### 新增功能
1. **任务单号查询** - 根据任务订单ID查询详细信息
2. **跨环境任务模板查询** - 查询当前执行中的任务
3. **跨环境任务模板详情** - 查看模板配置和子任务
4. **跨环境任务详情** - 查询所有子任务信息

#### 访问路径
- 主页导航: 点击"任务查询系统"按钮
- 直接访问: `/task_query`

#### 测试验证
整合后的功能已通过基本测试，可以正常访问和显示界面。

### 测试报告
详细的测试报告见：`test/DEPLOYMENT_TEST_REPORT.md`

### 新增功能测试 (2026-04-16)

#### 新增功能清单
1. **健康检查接口** - `/actuator/health` (返回固定值1000，用于服务器监控)
2. **AGV任务下发页面** - `/addtask` (集成原有addTask功能)
3. **配置管理系统** - `/config` (独立配置管理界面)
4. **配置管理API** - 支持配置的获取、保存、备份管理
5. **帮助文档功能** - `/addtask/help` (在线帮助文档)

#### 测试验证
所有新增功能已通过Flask测试客户端验证：
- ✓ 健康检查接口正常工作
- ✓ 主页面包含任务下发导航链接
- ✓ addtask页面正常显示
- ✓ 配置管理页面功能完整
- ✓ 配置管理API接口正常
- ✓ 帮助文档功能正常

#### 测试脚本
新增综合测试脚本：`test/test_new_features.py`
```bash
# 运行测试
cd /main/app/toolsForPersonal/projects/agv_system/app/cross_env_manager
python3 test/test_new_features.py http://127.0.0.1:5000
```

#### 测试文件夹管理
test文件夹已从.gitignore中移除，包含以下测试脚本：
- `test_new_features.py` - 新增功能综合测试
- `test_web_access.py` - Web访问测试
- `test_production_task_query.py` - 生产环境任务查询测试
- 其他功能测试脚本

#### 配置管理功能
- 支持可视化编辑和源文件编辑双模式
- 自动备份和版本管理
- 备份文件存储在`static/js/backups/`目录
- 配置文件和备份文件已添加到.gitignore

#### 健康检查接口
- 地址：`/actuator/health`
- 输入：无
- 返回：`1000` (纯文本)
- 用途：服务器监控系统健康检查


#### 新增功能

3. **交互功能**
   - 一键复制代码
   - 暗黑模式兼容
   - 实时内容同步

4. **暗黑模式支持**
   - 亮色/暗黑主题自动切换
   - 本地存储主题偏好

#### 测试脚本
使用方法，找到对应的测试脚本使用以下命令执行
```bash
cd /main/app/toolsForPersonal/projects/agv_system/app/cross_env_manager
venv/bin/python3 test/???.py
```

### 部署验证
部署后应验证以下功能：
1. 健康检查接口返回1000
2. 主页面导航栏显示任务下发链接
3. addtask页面功能正常
4. 配置管理系统可访问
5. 帮助文档正常加载
6. 配置管理API接口正常


### 其他
语法高亮已删除

### 重要更新（2026-04-27）

#### 1. 统一查询页面字段显示修复
- 修复了 `templates/query/unified_home.html` 中数据显示不全的问题
- 根因：远程API（/crossTask/query, /crossTask/detail）返回驼峰命名（deviceNum, taskPath, templateCode），前端getField()缺少这些字段名
- 修复：renderSubTaskCard() 添加 deviceNum/taskPath 候选字段；renderResult() 主任务总览添加 templateCode/taskPath 等后备字段名
- 新增显示字段：变更状态(changeStatus)、更新时间(updateTime)

#### 2. 跨环境任务重发功能
- **后端API**: `POST /api/task/resend` (app.py)
- **后端逻辑**: `modules/query/task_query_extended.py` → `resend_cross_task()` + `_generate_new_sub_order_id()`
- **前端按钮**: unified_home.html 子任务卡片操作按钮区，根据状态显示不同按钮
  - status=3(已取消) → 橙色"重发"按钮
  - status=7(失败) → 红色"重发"按钮
  - status=4/6/9(异常) → 红色"强制重发"按钮（大模板改为5，子模板改为5，sub_order_id+1）
  - status=5(重发中) → 灰色禁用"重发中..." + 红色"异常完成"按钮（仅将子模板状态改为3）
- **前端函数**: `window.resendTask(subOrderId, orderId, taskSeq)` 和 `window.forceCompleteTask(subOrderId, orderId, taskSeq)`
- **重发流程**: 前置任务检查(task_seq-1是否执行中) → 检查大模板状态 → 检查子模板状态 → 生成新sub_order_id(子ID+1) → 修改数据库
- **支持状态**: 大模板3/5/6/7/9, 子模板3/4/6/7/9
- **成功后3秒自动刷新查询**

#### 3. API接口文档
- 创建了 `doc/API.md`，覆盖所有56个路由
- 分9大类：页面路由、模板管理API、任务查询API、任务重发API、统计API、Join QR Node API、配置管理API、认证API、系统API
- 包含请求参数、响应示例、状态码说明、数据库表说明

#### 4. 设计文档
- `plans/resend_logic_detail.md` - 重发逻辑详细设计（含合并后的统一流程）
- `plans/cross_env_retry_frontend_plan.md` - 重发功能前端方案设计
- `plans/query_display_fix_plan.md` - 查询页面修复计划
- `plans/chart_design_plan.md` - 大模板状态分布图表设计方案

#### 5. 大模板状态分布图表（2026-04-27）
- **后端API**: `GET /api/stats/main_task_status` (app.py)，查询当天 fy_cross_task 按 task_status 分组统计
- **前端**: unified_home.html 左侧新增饼图卡片（Chart.js）+ 统计面板
- **刷新时机**: 页面加载时、查询任务后、手动刷新按钮
- **防抖**: 1秒内只能触发一次，频繁点击弹窗警告
- **交互**: 饼图悬停显示状态名/数量/百分比，点击图例切换显示/隐藏，异常率红色高亮

### 重要更新（2026-06-10）

#### 模板搜索页面重构（方案二：AdminLTE 表格+详情面板）

**改动了什么：**
- `/search` 路由改为 GET-only，渲染 `template/search.html`（前端渲染）
- 新增 `GET /api/search` 分页搜索 API（支持 q/page/per_page/server/status/sort_by/sort_order）
- 新增 `GET /api/template/<id>` 获取单个模板 JSON
- 新增 `template_service.search_paginated()` 服务方法

**新页面布局：**
- 顶部搜索栏 + 快捷标签（HJBY / back / 空车回流 / 换电 / A1楼栋）
- 筛选行：服务器下拉 / 状态下拉 / 排序下拉 / 结果计数
- 主区域左 65% 表格（可排序）+ 右 35% 详情面板（点击行加载）
- 底部分页 + 每页条数切换

**首页链接更新：**
- 服务器列表项 `search_term=IP` → `server=IP`
- 已启用模板统计卡 `filter=enable` → `status=1`

**清除文件：** `search_results.html` 不再被引用（保留未删）
**API 文档：** `doc/API.md` 已同步更新

- 2026-06-15: **跨环境任务浏览 (v2.4.7)** 完成。
  - 新增页面 `/query/cross-tasks`：直接查询 `fy_cross_task` 表，支持 11 个筛选参数（orderId/任务状态/设备号/货架号/来源系统/时间范围/模式流程/流程名称/错误描述/设备编码/任务路径）
  - 筛选下拉框支持气泡多选：下拉选择后显示为蓝色气泡，点 × 清除，支持多选（后端 IN 查询）
  - 下拉选项含数量统计（如"MES (8182)"），按数量降序排列，页面加载时从 `/api/query/cross_task_filters` 获取（5分钟缓存）
  - 每页条数可调（20/40/50/100/200，默认40），最多显示 2 页
  - 真实总数展示（如"共 8159 条 — 当前显示 80 条"）
  - 任务状态统一标签映射（-1=容量管控、8=任务完成、3=任务异常结束 等）
  - 查询耗时显示（如 ⏱ 87ms）
  - 页面打开自动查询默认数据，筛选条件变化自动重新查询（文本输入 500ms 防抖）
  - 每行"查看"按钮 → 跳转统一查询 `/query?orderId=xxx` 深度查询
  - 新增路由：页面 `GET /query/cross-tasks`、数据 `POST /api/query/cross_tasks`、筛选选项 `GET /api/query/cross_task_filters`（task_routes.py）
  - 侧边栏「查询」模块新增"跨环境任务浏览"入口
  - 任务查询模块版本 `TASK_VERSION` 2.3.1 → 2.4.1
  - 增量升级包部署至 10.68.2.40

### ds说
- 2025-04-28: **Phase 1 架构优化完成**。引入 DBUtils 连接池（modules/database/connection.py 重构），新增 dao/ 层（BaseDAO + TemplateDAO + DetailDAO），新增 middleware/ 层（统一异常处理 AppError/NotFoundError/AuthError/ValidationError），app.py 启动时自动初始化连接池并注册异常处理器。新增依赖 DBUtils==3.1.2。
- 2026-04-28: **Phase 2 架构优化完成**。创建 routes/ 蓝图层，将 app.py 中50+路由按功能拆分为8个蓝图文件。蓝图在 app.py 启动时自动注册，57条路由全部验证通过。
- 2026-04-28: **Phase 3 架构优化完成**。创建 services/ 业务逻辑层：AuthService（认证）、StatsService（统计）、TemplateService（模板CRUD+搜索+复制）、ConfigService（配置管理+备份）。修改 auth_routes/stats_routes/config_routes/template_routes 四个蓝图调用 Service 层，路由只负责请求解析和响应渲染。
- 2026-04-28: **Phase 4 缓存层完成**。引入 Flask-Caching 内存缓存（middleware/cache.py），对 stats_service 的3个高频查询方法（overview/distribution/templates_by_server）添加 @cache.cached 装饰器（TTL=5分钟）。写操作（编辑/复制/删除模板）时自动清除缓存。新增依赖 Flask-Caching==2.3.1 + cachelib==0.13.0，已同步更新 requirements.txt 和 vendor_packages3.9。详细方案见 plans/cross_env_manager_architecture_optimization.md。
- 2026-04-27: 跨环境任务重发功能已完成前后端实现。重发逻辑中前置任务检查放在最前面（不通过则不执行任何修改），逻辑1和逻辑2已合并为统一流程。sub_order_id递增规则为解析{orderId}_{taskSeq}_{subId}后subId+1。API文档已整理到doc/API.md。
- 2026-04-27: 查询页面字段显示问题已修复，根因是前端getField()查找的字段名与远程API返回的驼峰命名不匹配。修复方案是添加候选字段名而非修改API，保持向后兼容。
- 2026-04-27: fy_cross_model_process_detail 表新增 need_third_trigger 字段（默认0，1=存在第三方触发）。已在 app.py 的4处 SQL（edit_detail、copy_template、API新增子任务、批量更新子任务）和 edit_template.html、template_detail.html 的编辑/新增子任务模态框中添加该字段的编辑支持。前端使用复选框控件，勾选=1，不勾选=0。
- 2026-05-09: **版本号规则**：每个模块有独立的内部版本号，修改哪个模块就递增哪个模块的版本号（末尾数字+1）。各模块版本号定义：
  - `app.py`: `APP_VERSION` — 全局版本，页面底部展示 `CEM v{APP_VERSION}`
  - `routes/dispatch_routes.py`: `DISPATCH_VERSION` — 调车模块版本，`[SelfHeal v{DISPATCH_VERSION}]` 日志
  - `routes/task_routes.py`: `TASK_VERSION` — 任务查询模块版本，查询日志 `version` 字段
  - 其他模块按需添加 `__version__` 或 `{MODULE}_VERSION`
- 2026-05-13: **取消空车任务修复 (v2.1.7)**：根因是 `get_cross_task_info` 中 SQL 用错字段——`WHERE order_id LIKE CONCAT(%s, '_%%')` 试图在 `order_id`（主订单号）上做模糊匹配，但子任务 ID 存在 `sub_order_id` 字段中。修复为 `WHERE order_id = %s` 精确匹配（所有子任务共享同一主 order_id）。`api_cancel_empty_tasks` 恢复使用 `_get_task_server_info` 查询子任务 `sub_order_id` 和 `service_url` 后调用 ICS 取消接口。前端 `dashboard.html` 去掉 `.slice(0, 30)` 截断，完整显示订单号。
- 2026-05-13: **取消空车任务修复 (v2.1.8)**：修复 server_ip 获取逻辑——`_get_task_server_info` 原来用大模板 `model_process_code` 查 `fy_cross_model_process_detail.template_code`，但该表存的是子模板 code，导致匹配不到而 fallback 到默认 `10.68.2.32`。改为用第一个子任务的 `template_code`（从 `fy_cross_task_detail` 获取）查询 `task_servicec`。同时修复详情按钮无反应问题——`onclick` 中嵌入 JSON 字符串因特殊字符破坏 HTML 属性，改为 `data-ri-idx` + 全局数组 `window._cancelDetailData` + 事件委托方式。
- 2026-05-13: **解死锁机制 (v2.1.9)**：在 `calculate_area_balance` 互斥检查中增加自动解死锁——当来任务=0、回空车已下发导致 `can_dispatch=False` 时，自动调用 `_get_task_server_info` + `_cancel_empty_task` 取消阻塞的反方向空车任务，并清理本地 JSON。取消成功后重新检查是否还有阻塞，若已解除则允许下发。
- 2026-05-14: **全局空车任务数量限制 (v2.1.10)**：新增 `GLOBAL_EMPTY_TASK_LIMIT`（默认4）和 `_get_empty_task_limit()` 函数。区域配置 `empty_task_limit`：-1=使用全局、0=不限制、>0=自定义。`calculate_area_balance` 中检查当前方向空车模板 JSON 中 status=6 任务数，超出上限则限制 `dispatch_count`。`_execute_dispatch` 中 dispatch_count=0 时跳过下发。前端 config.html 全局设置新增"全局空车任务上限"，区域配置新增"空车任务上限"。
- 2026-05-22: **定制表编辑模块 (v1.0.0)**：新增跨服务器、跨数据库的通用表编辑功能。采用方案C（混合式）：配置驱动 + 可覆盖自定义模板。新增文件：`config/custom_tables.toml`（服务器和表配置）、`modules/custom_table/`（config_loader + table_service）、`routes/custom_table_routes.py`（蓝图，9个数据路由 + 6个配置管理路由）、`templates/custom_table/`（index.html + editor.html）。入口：首页卡片 + 导航栏。**index.html 为可视化配置管理页**（三 Tab：可视化编辑服务器和表配置 / 源文件 TOML 编辑 / 备份恢复），参考调车模块 config.html 风格。**editor.html 为三模式数据编辑器**（可视化编辑：左侧分组导航 + 右侧记录卡片表单 / 表格编辑：分组折叠 + 双击内联编辑 / 源数据：JSON 批量编辑）。支持 dirty tracking 批量保存。当前配置 2 个服务器：10.68.2.17（生产）+ 47.98.244.173（测试）。详细设计见 `plans/custom_table_editor_design.md`。
- 2026-06-02: **任务下发模块 (addtask) 重大升级**：涉及 `app.py`、`templates/addTask/addtask.html`、`templates/components/addtask_form.html`、`templates/components/addtask_query.html` 四个文件。
  - **区域下拉框**：按楼栋前缀 `A1~A4` 自动分组为 optgroup，按今日使用次数降序排列。新增 `getBuildingColor()` 使用黄金角哈希自动分配 HSL 色相，无需硬编码 CSS。`refreshCountDisplay()` 只更新文本不重建 DOM。
  - **任务模板下拉框**：按空车/非空车分组，显示使用次数计数。组标签含任务总数。
  - **每日使用统计**：`recordAreaUsage(area)` + `recordTaskUsageCount(area, taskName)` 双维度 localStorage 记录，每天自动重置。
  - **后端代理 API** `POST /addtask/query`：Flask 统一代理 ICS 请求（`urllib + json`），浏览器不再暴露 `10.68.2.32:8315`。支持 shelfNum/orderId/deviceNum 三种入参，自动查询主任务 + 子任务详情。
  - **右侧查询面板**：新增第三种查询模式「按设备号查询」；查询历史 localStorage（最近5条，点击一键重查）；子任务 API 空数据时重试3次（间隔1秒）。
  - **任务详情卡片**：主任务显示 `modelProcessCode` 链接 → `/search`；子任务模板名显示为链接；OrderId/货架号/子任务ID 支持 3 层复制（Clipboard API → `execCommand` → `window.prompt`，兼容 HTTP 环境）；新增「查看完整详情」按钮 → `/query?orderId=xxx`。
  - **响应报文**：格式化为 `<pre>` 代码块，成功/失败分色显示，带一键复制。
  - **自动搜索**：下发成功后 1.5 秒自动搜索（`autoQueryAfterSubmit`），执行前检查用户是否切换模式或修改输入，`queryTasks(true)` 传 `force` 参数绕过防抖锁。
  - **页脚**：动态显示 `config._version`。
   - **表单保留**：提交后 `refreshCountDisplay()` 仅更新文本，不丢失已选区。
- 2026-06-02: **设备同步功能 (Device Sync)** 完成。基于原 `/python快捷处理sql脚本/` 三个脚本整合进 Web UI。Service 层 `services/device_sync_service.py` 封装三大同步逻辑（型号/设备主表/设备扩展表），连接管理通过 pymysql 直连多 IP（共享 `config/env.toml` 凭据）。路由挂 `template_bp`（5个API端点），SSE 流式推送实时日志。页面 `templates/template/device_sync.html` 卡片式布局：服务器选择+测试连接 → 同步配置(三开关) → 预览+执行 → SSE 实时日志流。入口：首页「设备同步」按钮→`/template/device-sync`。关键 SQL：SELECT agv_model/agv_robot/agv_robot_ext → INSERT IGNORE 到目标库。服务器 IP 从 `fy_cross_model_process_detail.task_servicec` 解析，目标区域从 `bms_area WHERE LEVEL=1` 获取。
- 2026-06-03: **交接点配置管理 (Join QR Node)** 完成。管理 `join_qr_node_info` 表配对配置，以 `qr_content` 为配对单位（一个地码值对应对侧2条记录）。Service 层 `services/join_qr_service.py` 实现配对列表（按 qr_content 分组自动判断 type=0跨服务器/1同服务器）、配对新增（双栏表单→2条 INSERT + 基准服务器副本）、配对编辑（先删后加）、模板交接点检查。路由 `routes/join_qr_routes.py`（6页面+2API）。页面 `templates/join_qr_nodes/list.html`（筛选+配对展示）+ `edit.html`（双栏表单自动 type）。基准服务器 `10.68.2.32`：当新增配对的服务器不含 2.32 时自动创建基准副本。模板详情操作面板新增「交接点配置」自动检查：GET `/api/template/<id>/join_qr_check` 逐个检查每个子任务服务器的 `join_qr_node_info` 配置状态。入口：首页「交接点」→`/pair/list`。关键 SQL：INSERT INTO join_qr_node_info (area_id,type,qr_content,environment_ip,enable) VALUES；DELETE WHERE qr_content=%s；SELECT COUNT(*) WHERE environment_ip=%s AND area_id=%s。
- 2026-06-12: **升级管理模块** 完成。
  - 新增 `services/upgrade_service.py`（备份、解压覆盖、回滚、记录管理、自动清理 MAX_BACKUPS=10、延时重启）
  - 新增 `routes/system_upgrade_routes.py`（`GET /system/upgrade` 页面 + `POST /api/system/upgrade` 上传升级 API + 记录/回滚 API）
  - 新增 `templates/system/upgrade.html`（版本信息 + 拖拽上传 + 升级记录表 + 一键回滚）
  - 侧边栏系统管理组新增「升级管理」，后端路径匹配 `/system/upgrade` 归属 system 模块
  - 升级包支持 `version.json`（ZIP 内带 changes 列表）或 `remark` 表单参数记录升级说明
  - 升级记录表展示 release_title + release_notes 列表
  - 真实升级测试通过（3.1M ZIP + 2730 文件 + 自动重启 + 记录持久化）
- 2026-06-12: **Doc & Skill 目录整理**。
  - `doc/API.md`（单文件 820 行）→ `doc/api/` 按模块拆分 9 个独立文件
  - `doc/task_template_relation.md` → `doc/architecture/数据库关系.md`
  - `doc/华睿相关开发要求.md` → `doc/dev/华睿要求.md`
  - 新增 `doc/architecture/整体架构.md`（三层架构图 + 模块依赖 + 数据流 + 启动流程）
  - 新增 `doc/dev/定制表开发要求.md`（CRUD 约束规则）
  - 新增 `doc/modules/` 5 个模块介绍文件（dispatch/addtask/query/config/upgrade）
  - 新增 `doc/README.md` 文档目录索引
  - `skill/` 重命名：`skill_xxx.md` → `xxx.md`，新增 `upgrade.md`
- 2026-06-12: **增量升级包支持** 完成。
  - `GET /api/system/version-info` 返回版本号 + git commit hash
  - `do_upgrade()` 支持增量包：读取 `version.json.from_version` 校验版本一致性，`files_changed.D` 清理废弃文件
  - `scripts/build_upgrade.py` 构建工具：查询服务器版本 → `git diff` 找基线 → 仅打包变更文件 → 生成 `upgrade_vX_to_vY.zip`（62KB vs 3.1MB 全量）
  - 增量包 `version.json` 结构：`from_version`/`to_version`/`from_commit`/`to_commit`/`type: incremental`/`files_changed: {A,M,D}`
  - 全量包向后兼容（无 `from_version` 字段时跳过校验）
- 2026-06-12: **辊筒任务模块 (v1.7.0)** 完成。`dispatch_config.json` 新增 `_features.enable_roller_task` 全局开关 + 任务级 `roller_task/roller_point/roller_point_label` 字段。前端 `addtask.js` 增加辊筒分组 `⏏️ 辊筒任务`、已下发缓存管理（localStorage + 15秒轮询 + 状态8自动释放 + capacity 满容阻止）、orderId 前缀 `RLLR_`。后端 `app.py` 新增 `_query_roller_task()` 函数，`/addtask/query` 按前缀 `RLLR_` → `:7000`（非跨环境）、`CEM_` → `:8315`（跨环境失败回退到辊筒 API）。`services/config_service.py` 的 `save_config()` 自动补全 `_features` 字段确保不缺失。`/config-editor` 跳转到 `/addtask/config-view`。区域列表双击重命名。配置编辑器 `ensureConfigCompatibility` 自动补全 `_features`。