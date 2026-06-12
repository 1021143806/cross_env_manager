# 7. 认证 API

### 7.1 登录
```
POST /api/login
```
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |
| admin_username | string | 否 | 管理员提权用户名 |
| admin_password | string | 否 | 管理员提权密码 |

**后门账号：** `admin / admin123456` 绕过 bms_user 验证，自动获得管理员权限。

**响应示例:**
```json
{
  "success": true,
  "message": "登录成功（管理员）",
  "username": "admin",
  "is_admin": true
}
```

### 7.2 注销
```
POST /api/logout
```
**响应示例:**
```json
{
  "success": true,
  "message": "已注销"
}
```

### 7.3 认证状态
```
GET /api/auth/status
```
**响应示例:**
```json
{
  "logged_in": true,
  "username": "admin",
  "is_admin": true,
  "login_time": "2026-06-12T10:00:00"
}
```

### 7.4 登录页面
```
GET /login
```
返回 `login.html`。
