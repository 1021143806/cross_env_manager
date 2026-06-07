# RCS 日志目录 skill

## 用途
记录各服务器上 RCS 相关服务的日志目录位置，便于在不同服务器上通过 postlook 添加白名单和查询。

## 日志目录模板

### 算法服务
| 服务 | 目录模式 | 说明 |
|------|---------|------|
| 分配库 (rtpsa) | `/main/app/rtpsa-*/logs` | 任务分配算法 |
| 分配库 TAL | `/main/app/rtpsa-*/TAL_log/` | 分配库详细日志（dispatchTAL.log） |
| 分配库 DPL | `/main/app/rtpsa-*/DPL_log/` | 分配库 DPL 日志 |
| 规划库 (rtpsp) | `/main/app/rtpsp-*/logs` | 路径规划算法 |
| 规划库 TAL | `/main/app/rtpsp-*/TAL_log/` | 规划库详细日志 |
| 规划库 DPL | `/main/app/rtpsp-*/DPL_log/` | 规划库 DPL 日志 |

### 调度服务
| 服务 | 目录模式 | 说明 |
|------|---------|------|
| ICS | `/main/app/ics/logs` | 任务调度服务 |
| TPS | `/main/app/tps/logs` | 任务处理服务 |

### 业务服务
| 服务 | 目录模式 | 说明 |
|------|---------|------|
| FYWDS | `/main/app/fywds/logs` | 跨工序任务服务 |
| RDMS | `/main/app/rdms/logs` | 资源管理 |
| BMS | `/main/app/bms/logs` | 电池管理 |
| FMS | `/main/app/fms/logs` | 车队管理 |
| SPS | `/main/app/sps/logs` | 路径服务 |
| CMS | `/main/app/cms/logs` | 配置管理 |
| WDS-PCBA | `/main/app/wds-pcba/logs` | WDS PCBA |
| PSS-Proxy | `/main/app/pss-proxy/logs` | PSS 代理 |
| AccessControl | `/main/app/accessControl/logs` | 门禁控制 |
| Revent | `/main/app/revent/logs` | 事件上报 |

## 添加白名单

### 方法一：通过 postlook Web UI
1. 打开 `http://<服务器IP>:5011`
2. 左侧导航 → 配置管理
3. 使用"扫描日志目录"功能扫描 `/main/app`
4. 勾选需要的目录 → 添加到白名单 → 保存配置

### 方法二：通过 API
```bash
# 查看当前白名单
curl http://<IP>:5011/api/config

# 热更新白名单（添加目录）
curl -X POST http://<IP>:5011/api/config -H "Content-Type: application/json" \
  -d '{"content": "[server]\nhost = \"0.0.0.0\"\nport = 5011\n\n[logs]\nroot_dirs = [\"/var/log\", \"/main/app/ics/logs\", \"/main/app/tps/logs\"]\nmax_lines = 100\ndefault_lines = 50\ndefault_recent_files = 10\n\n[ui]\ntheme = \"dark\"\n"}'
```

### 方法三：手动编辑配置文件
```bash
vim /main/app/postlook/config/env.toml
# 修改 root_dirs 数组
sudo supervisorctl restart postlook
```

## 在新服务器上部署后添加白名单的步骤
1. 部署 postlook
2. 访问 Web UI → 配置管理 → 扫描 `/main/app`
3. 勾选需要的日志目录 → 添加到白名单 → 保存
4. 或通过 API 批量添加

## ds 说
- rtpsa 是分配库（Allocation），rtpsp 是规划库（Planning）
- 目录名中的数字是实例编号，多实例合并目录用逗号分隔
- TAL_log 和 DPL_log 是子目录，scan-dirs 扫不到（只扫 log/logs），需手动添加
- 添加白名单后热更新立即生效，无需重启
- 不同服务器的实例编号可能不同，需通过 scan-dirs 确认实际目录名

### 地图管理模块（FMS）
- 服务：FMS（车队管理）
- 日志：`/main/app/fms/logs`
- 地图存储：`/main/web/www/textureMap/{areaId}/{type}/Map/{version}/`（文件名含 region 参数）
- 地图下载 URL：`http://<server_ip>:8888/textureMap/{areaId}/origin/{version}.zip`
- 关键类：`cn.com.dahua.fms.util.MapUtil`（地图文件解压/生成）、`cn.com.dahua.fms.service.impl.MapServiceImpl`（地图入库）、`cn.com.dahua.fms.controller.FileUploadController`（上传入口）
- 排查关键字：`textureMap`、`generateOneFile`、`generateMapFile`、`processMap2Db`
- 说明：地图上传后由 FMS 解压处理并同步到数据库（BMS），nginx 在 8888 端口提供 HTTP 下载服务。AGV 的 `IssueMaps()` 命令下载的 zip 包即来自此模块。
- 已知问题：rtpsa-1 分配库 `restTask.cpp:80` 中 `map_node_map can't find content` 表示算法侧地图节点表为空，需检查分配库地图加载逻辑。
