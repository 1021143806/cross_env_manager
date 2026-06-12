# 5. 交接点配置 API (Join QR Node)

## 5.1 页面

### 5.1.1 配对列表
```
GET /pair/list
```

### 5.1.2 新增配对
```
GET /pair/add
```
双栏表单，自动判断 type=0（跨服务器）/ type=1（同服务器）。

### 5.1.3 编辑配对
```
GET /pair/edit/<qr_content>
```

## 5.2 API

### 5.2.1 获取配对列表（JSON）
```
GET /api/pair/list
```
按 `qr_content` 分组，自动判断 type。

### 5.2.2 新增配对
```
POST /api/pair/add
```
2 条 INSERT（对侧配对记录）+ 基准服务器副本（若新增的服务器不含 10.68.2.32）。

### 5.2.3 编辑配对
```
POST /api/pair/edit
```
先删后加：DELETE WHERE qr_content=%s → 重新 INSERT。

### 5.2.4 删除配对
```
DELETE /api/pair/delete/<qr_content>
```

### 5.2.5 获取服务器列表
```
GET /api/pair/servers
```

### 5.2.6 模板对接检查
```
GET /api/template/<id>/join_qr_check
```
逐个检查每个子任务服务器的 `join_qr_node_info` 配置状态。
