# 9. 定制表编辑 API

> 配置驱动，支持跨服务器、跨数据库的通用表编辑功能。
> 配置文件: `config/custom_tables.toml`

## 9.1 页面

### 9.1.1 定制表首页
```
GET /custom_table
```
返回服务器卡片选择页。

### 9.1.2 表编辑器页面
```
GET /custom_table/{server_key}/{table_name}
```
返回指定服务器和表的编辑器页面（三模式：可视化 / 表格 / JSON）。

## 9.2 API

### 9.2.1 查询表数据
```
GET /api/custom_table/{server_key}/{table_name}/rows
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 25 |
| search | string | 否 | 搜索关键词 |
| search_field | string | 否 | 指定搜索字段 |
| order_by | string | 否 | 排序字段 |
| order_dir | string | 否 | asc/desc |
| group_by | string | 否 | 分组字段 |

### 9.2.2 新增行
```
POST /api/custom_table/{server_key}/{table_name}/row
```

### 9.2.3 更新行
```
PUT /api/custom_table/{server_key}/{table_name}/row/{pk_value}
```

### 9.2.4 删除行
```
DELETE /api/custom_table/{server_key}/{table_name}/row/{pk_value}
```

### 9.2.5 批量更新
```
PUT /api/custom_table/{server_key}/{table_name}/batch_update
```

### 9.2.6 导出 CSV
```
GET /api/custom_table/{server_key}/{table_name}/export?search=xxx
```

### 9.2.7 获取分组值
```
GET /api/custom_table/{server_key}/{table_name}/groups?field=target_shop
```

### 9.2.8 配置管理
```
GET  /api/custom_tables/config          # 获取配置
POST /api/custom_tables/config          # 保存配置
GET  /api/custom_tables/config/raw      # 获取原始 TOML
POST /api/custom_tables/config/raw      # 保存原始 TOML
GET  /api/custom_tables/config/backups  # 备份列表
POST /api/custom_tables/config/backup   # 创建备份
```
