# 配置文件使用说明

## 概述
跨环境任务模板管理系统现在支持灵活的配置文件管理，包括TOML格式配置文件和命令行参数。

## 配置文件格式

### 默认配置文件
系统默认使用 `config/env.toml` 作为配置文件。该文件支持两种格式：

1. **TOML格式**（标准）：
```toml
[database]
host = "localhost"
port = 3306
user = "root"
password = ""
name = "agv_cross_env_test"
charset = "utf8mb4"

[flask]
secret_key = "cross_env_manager_secret_key_2026"
debug = false
host = "0.0.0.0"
port = 5000
```

2. **.env格式**（兼容旧版）：
```env
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=agv_cross_env_test
DB_CHARSET=utf8mb4

# Flask配置
FLASK_SECRET_KEY=cross_env_manager_secret_key_2026
FLASK_DEBUG=false
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

## 配置加载优先级

系统按以下优先级加载配置（高优先级覆盖低优先级）：

1. **命令行参数**（最高优先级）
2. **环境变量**（`CONFIG_PATH`, `DB_HOST`, `FLASK_PORT`等）
3. **配置文件**（默认 `config/env.toml`）
4. **默认值**（最低优先级）

## 命令行参数

应用支持以下命令行参数：

```bash
# 基本用法（使用默认配置文件）
python app.py

# 指定配置文件
python app.py --config config/env.toml
python app.py -c config/custom.toml

# 指定主机和端口
python app.py --host 127.0.0.1 --port 8080
python app.py -p 8080

# 启用调试模式
python app.py --debug
python app.py -d

# 组合使用
python app.py --config config/production.toml --port 8000 --debug
```

### 参数说明
- `--config`, `-c`：指定配置文件路径（支持.toml或.env格式）
- `--host`：指定Flask服务主机地址
- `--port`, `-p`：指定Flask服务端口
- `--debug`, `-d`：启用调试模式

## 环境变量

可以通过环境变量覆盖配置：

```bash
# 指定配置文件路径
export CONFIG_PATH=/path/to/config.toml

# 直接设置数据库配置
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=secret

# 设置Flask配置
export FLASK_HOST=0.0.0.0
export FLASK_PORT=5000
export FLASK_DEBUG=true
```

## 部署示例

### 开发环境
```bash
# 使用默认配置
python app.py --debug

# 或使用环境变量
export FLASK_DEBUG=true
python app.py
```

### 生产环境
```bash
# 使用生产配置文件
python app.py --config config/production.toml --port 8000

# 或使用环境变量
export CONFIG_PATH=config/production.toml
export FLASK_PORT=8000
python app.py
```

### Supervisor配置示例
```ini
[program:cross_env_manager]
command=python /path/to/app.py --config /path/to/config/production.toml --port 8000
directory=/path/to/project
autostart=true
autorestart=true
user=www-data
environment=PYTHONPATH="/path/to/project"
```

## 配置文件示例

### 开发环境配置（config/development.toml）
```toml
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=dev_user
DB_PASSWORD=dev_password
DB_NAME=agv_cross_env_dev
DB_CHARSET=utf8mb4

# Flask配置
FLASK_SECRET_KEY=development_secret_key
FLASK_DEBUG=true
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# 应用配置
APP_NAME=跨环境任务模板管理系统（开发版）
LOG_LEVEL=DEBUG
```

### 生产环境配置（config/production.toml）
```toml
# 数据库配置
DB_HOST=production-db.example.com
DB_PORT=3306
DB_USER=prod_user
DB_PASSWORD=strong_password_here
DB_NAME=agv_cross_env_prod
DB_CHARSET=utf8mb4

# Flask配置
FLASK_SECRET_KEY=production_secret_key_change_this
FLASK_DEBUG=false
FLASK_HOST=0.0.0.0
FLASK_PORT=8000

# 应用配置
APP_NAME=跨环境任务模板管理系统
LOG_LEVEL=INFO
MAX_CONTENT_LENGTH=16777216  # 16MB
```

## 故障排除

### 1. 配置文件未找到
```
错误：无法加载TOML配置文件 config/custom.toml
```
**解决方案**：确保配置文件路径正确，或使用绝对路径。

### 2. 配置项未生效
**检查顺序**：
1. 检查命令行参数是否正确
2. 检查环境变量是否设置
3. 检查配置文件格式是否正确
4. 查看启动日志确认使用的配置

### 3. TOML解析错误
```
错误：TOML解析失败
```
**解决方案**：确保TOML文件格式正确，或使用.env格式。

## 注意事项

1. **敏感信息**：生产环境的密码等敏感信息不应直接写在配置文件中，建议使用环境变量或密钥管理服务。
2. **配置文件权限**：确保配置文件权限适当，避免敏感信息泄露。
3. **版本控制**：建议将配置文件模板（如`config/template.toml`）加入版本控制，但不包含实际敏感信息的配置文件。
4. **备份**：定期备份生产环境配置文件。