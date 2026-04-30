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



## Example Usage

## 重要文件夹
- templates/ - 存放HTML模板文件
   - index.html - 主页面模板
   - components/ - 存放页面组件模板

- static/ - 存放静态资源文件（CSS、JS、图片等）
- deploy_iraypleos/ - 存放离线部署相关脚本和资源
- test/ - 存放测试脚本和测试资源

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

### ds说
- 2026-04-28: **Phase 1 架构优化完成**。引入 DBUtils 连接池（modules/database/connection.py 重构），新增 dao/ 层（BaseDAO + TemplateDAO + DetailDAO），新增 middleware/ 层（统一异常处理 AppError/NotFoundError/AuthError/ValidationError），app.py 启动时自动初始化连接池并注册异常处理器。新增依赖 DBUtils==3.1.2。
- 2026-04-28: **Phase 2 架构优化完成**。创建 routes/ 蓝图层，将 app.py 中50+路由按功能拆分为8个蓝图文件。蓝图在 app.py 启动时自动注册，57条路由全部验证通过。
- 2026-04-28: **Phase 3 架构优化完成**。创建 services/ 业务逻辑层：AuthService（认证）、StatsService（统计）、TemplateService（模板CRUD+搜索+复制）、ConfigService（配置管理+备份）。修改 auth_routes/stats_routes/config_routes/template_routes 四个蓝图调用 Service 层，路由只负责请求解析和响应渲染。
- 2026-04-28: **Phase 4 缓存层完成**。引入 Flask-Caching 内存缓存（middleware/cache.py），对 stats_service 的3个高频查询方法（overview/distribution/templates_by_server）添加 @cache.cached 装饰器（TTL=5分钟）。写操作（编辑/复制/删除模板）时自动清除缓存。新增依赖 Flask-Caching==2.3.1 + cachelib==0.13.0，已同步更新 requirements.txt 和 vendor_packages3.9。详细方案见 plans/cross_env_manager_architecture_optimization.md。
- 2026-04-27: 跨环境任务重发功能已完成前后端实现。重发逻辑中前置任务检查放在最前面（不通过则不执行任何修改），逻辑1和逻辑2已合并为统一流程。sub_order_id递增规则为解析{orderId}_{taskSeq}_{subId}后subId+1。API文档已整理到doc/API.md。
- 2026-04-27: 查询页面字段显示问题已修复，根因是前端getField()查找的字段名与远程API返回的驼峰命名不匹配。修复方案是添加候选字段名而非修改API，保持向后兼容。
- 2026-04-27: fy_cross_model_process_detail 表新增 need_third_trigger 字段（默认0，1=存在第三方触发）。已在 app.py 的4处 SQL（edit_detail、copy_template、API新增子任务、批量更新子任务）和 edit_template.html、template_detail.html 的编辑/新增子任务模态框中添加该字段的编辑支持。前端使用复选框控件，勾选=1，不勾选=0。