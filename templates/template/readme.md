# 模板管理

## 功能概述
管理跨环境任务模板（fy_cross_model_process）及子任务（fy_cross_model_process_detail）。

## 页面列表
| 页面 | 路由 | 说明 |
|------|------|------|
| 搜索模板 | POST /search | 首页搜索框，支持模糊搜索和纯数字ID精确查找 |
| 搜索结果 | GET /search | 展示匹配的模板列表 |
| 模板详情 | GET /template/<id> | 查看模板完整信息和子任务列表 |
| 编辑模板 | GET/POST /edit/<id> | 修改模板配置信息 |
| 复制模板 | GET/POST /copy/<id> | 基于现有模板创建新模板，自动生成ID后缀 |
| 编辑子任务 | POST /edit_detail/<id> | 修改子任务详细信息 |
| 添加子任务 | POST /api/template/<id>/details/add | 添加新子任务 |
| 删除子任务 | DELETE /api/template/<id>/details/<id>/delete | 删除子任务 |
| 子任务排序 | POST /api/template/<id>/details/reorder | 拖拽调整子任务顺序 |
