# 设备注册平台 IP 修改工具 (SSH 直连版)

通过 SSH 登录 AGV，直接调用 ROS 服务修改 DVRIP 配置中的注册平台地址。

## 适用场景

- RCS HTTP API 不可用或不稳定
- 需要跳过调度层，直连车端修改
- 批量对多台 AGV 执行相同变更

## 工作原理

```mermaid
flowchart LR
    A[set_dvrip.py] -->|SSH + rosservice| B[platform_access_node]
    B -->|getConfig/setConfig| C[DVRIP 配置]
    C -->|修改| D[RegisterServer.Address]

    style A fill:#4a90d9,color:#fff
    style C fill:#e6a817,color:#fff
    style B fill:#50b86c,color:#fff
```

1. SSH 登录 AGV（用户 `dahua`）
2. `rosservice call /platform/getConfig "name: 'DVRIP'"` → 获取当前配置（YAML 格式，可能跨多行）
3. `yaml.safe_load` 解析 YAML，提取 `config` 字段（JSON 文本），再 `json.loads` 转为 Python dict
4. 修改 `RegisterServer.Servers[0].Address` 为目标 IP
5. 紧凑 JSON 序列化（`separators=(",", ":")`），通过 `rosservice call` ANSI-C quoting 写回
6. 服务端返回 `result: 0` 即表示成功

## DVRIP 配置结构

```json
{
  "MCASTAddress": "239.255.42.42",
  "MCASTEnable": false,
  "MCASTPort": 36666,
  "MaxConnections": 10,
  "RegisterServer": {
    "DeviceID": "CB43750BAK00010",
    "Enable": true,
    "Servers": [
      { "Address": "10.68.2.27", "Port": 3002 }   // ← 修改此项
    ]
  },
  "RegisterServerEx": { ... },
  "RegisterServerVehicle": { ... },
  "TCPPort": 37777,
  "UDPPort": 37778
}
```

## 依赖

```bash
pip install paramiko pyyaml
```

| 依赖 | 用途 |
|------|------|
| `paramiko` | SSH 远程执行命令 |
| `pyyaml` | 解析 rosservice 输出的 YAML 格式（含多行续接） |

## 使用方式

### 单设备修改

```bash
python scripts/DVRIP/set_dvrip.py 10.68.178.75 10.68.2.32
```

### 仅查看当前配置（不修改）

```bash
python scripts/DVRIP/set_dvrip.py 10.68.178.75 --show
```

输出示例：
```
10.68.178.75:  Address=10.68.2.27  Port=3002  Enable=True  DeviceID=CB43750BAK00010
```

### 批量修改多台设备

```bash
python scripts/DVRIP/set_dvrip.py \
  10.68.178.75 10.68.178.76 10.68.178.77 \
  10.68.2.32
```

### 指定端口和设备序列号

```bash
python scripts/DVRIP/set_dvrip.py 10.68.178.75 10.68.2.32 \
  --port 3002 --device-id CB43750BAK00010
```

### 自定义 SSH 凭据

```bash
python scripts/DVRIP/set_dvrip.py 10.68.178.75 10.68.2.32 \
  --ssh-user dahua --ssh-pass '123$iRAY567*'
```

### 作为模块导入调用

```python
from scripts.DVRIP.set_dvrip import quick_set

result = quick_set(
    host="10.68.178.75",
    new_ip="10.68.2.32",
    port=3002,
    device_id="CB43750BAK00010",
)
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `host` | AGV IP 地址（可多个，实现批量），必填 |
| `new_ip` | 新的平台注册 IP，必填 |
| `--port` | 注册端口，默认 3002 |
| `--device-id` | 设备序列号（可选） |
| `--ssh-user` | SSH 用户，默认 `dahua` |
| `--ssh-pass` | SSH 密码，默认 `123$iRAY567*` |
| `--show` | 仅查看当前配置，不修改 |

## 技术细节

### YAML 多行续接

ROS kinetic 的 `rosservice call` 输出 YAML 格式，长字符串会使用 YAML 双引号续行：

```yaml
result: 0
config: "{\"MCASTAddress\":\"239.255.42.42\",\"\
  MaxConnections\":10,\"RegisterServer\":{\"\
  DeviceID\":\"CB43750BAK00010\",...}"
```

每行末尾的 `\` + 换行是 YAML 续行标记。`yaml.safe_load` 可完整还原。

### setConfig 参数传递

`rosservice call` 的多参数需用**换行**分隔（`name:` 和 `config:` 各占一行）。通过 SSH 传递时改用 ANSI-C quoting：

```bash
rosservice call /platform/setConfig $'name: \'DVRIP\'\nconfig: \'{"key":"val"}\''
```

### JSON 格式要求

setConfig 服务要求 JSON **紧凑格式**（无多余空格），与 getConfig 返回的原始格式一致：

```python
json.dumps(config, separators=(",", ":"))
```

### 返回码约定

| 服务 | result=0 | result=1 |
|------|----------|----------|
| `getConfig` | 成功（含有效配置） | 失败 |
| `setConfig` | 成功 | 失败 |

## 与其他组件的关系

| 层级 | 组件 | 说明 |
|------|------|------|
| 工具层 | `set_dvrip.py` | 本工具，通过 SSH + ROS 服务修改 |
| 服务层 | `platform_access_node` | ROS 节点，提供 `/platform/setConfig` / `/getConfig` 服务 |
| 持久层 | `CustomConfig` | JSON 配置文件，`DVRIP` 段定义注册服务器地址 |

对应车端 `setcfg DVRIP` 命令定义在 `/home/dahua/.bashrc`，本质也是调用 `rosservice call /platform/{getConfig,setConfig}` 读写同一份配置。

## 注意事项

- AGV 需已启动 ROS（`roscore` + `platform_access_node`），可通过 `ps aux | grep platform_access_node` 确认
- 配置即时生效，无需重启设备
- SSH 账号密码与 AGV 设备信息页一致（默认 `dahua` / `123$iRAY567*`）
- `DeviceID` 需与实际设备序列号一致，可通过 `/var/robot/Product/Device.json` 查看
- 若修改后 WIFI/5G 断连检测脚本仍 ping 旧地址，检查 `/mnt/mtd/Config/CustomConfig` 确认配置是否持久化
