# 服务器故障排查思路

## 核心原则

1. **不要先入为主** — 看到"假死"别直接猜 OOM，看到"连不上"别直接猜网络。让证据说话
2. **四层递进** — 应用层 → 系统层 → 资源层 → 依赖层，一层一层排除
3. **时间线优先** — 先搞清楚什么事、什么时间发生的，再分析原因
4. **日志量分析是利器** — 日志量的"断崖式"下降比具体报错更能定位崩溃时间点

---

## 一、服务假死排查四层法

### 第一层：应用日志—定位故障面

**目标**：哪些服务挂了？什么时间开始的？报了什么错？

```
① 列出所有服务的日志最新修改时间
   → 停在天亮前的服务就是故障点
   
② 找到日志量最大的服务（通常是 gateway/网关）
   → 分析每分钟日志行数，找"断崖"
   → 暴跌的就是崩溃时间点
   
③ 查错误关键字
   → ERROR / Exception / recycle error / PersistenceException
   → OOM / OutOfMemory / Killed / SIGKILL
   → too busy / rejected / thread pool
   
④ 查重启证据
   → 应用日志中的 [main] 线程报错（重启时打印）
   → 多个进程同时重启说明是系统级事件
   → GC 日志文件生成时间 = JVM 启动时间
```

**判断系统级 vs 应用级：**
- 单个服务异常 → 应用自身问题（OOM/配置错误/线程池满）
- 多个独立进程同时异常 → 系统级事件（OOM Killer/整机重启/资源耗尽）
- 所有服务同时卡住 → 共享资源问题（数据库锁/网络中断/存储挂死）

### 第二层：系统日志—查 OS 级问题

**目标**：OOM Killer？内核 Panic？硬重启？硬件错误？

```
① OOM Killer
   → messages/ 中搜 oom_kill / Killed process / Out of memory
   → 特征：显示被杀进程名、内存使用、触发进程
   
② 内核异常
   → panic / soft lockup / hard lockup / Call Trace
   → hung_task / watchdog / NMI
   
③ 重启记录
   → sshd 重新监听端口 = 刚启动完
   → 内核版本变化 = 整机重启（注意新旧版本号对比）
   → reboot / shutdown / kexec
   
④ 资源上限
   → kauditd_printk_skb: 48 callbacks suppressed — 审计子系统过载
   → "too many open files" — FD 耗尽
   → "fork: Cannot allocate memory" — 进程表满
```

**小技巧**：系统日志不可读时（权限不够），尝试用 `setfacl` 授权，不需要改为 root 运行。

### 第三层：资源监控—看 CPU/内存/I/O

**目标**：排除资源耗尽类问题

```
① CPU
   → 看 sar -u 数据：%idle 是否接近 0
   → 长时间 100% 说明 CPU 打满
   
② 内存
   → sar -r：kbmemfree / %memused
   → swap 使用率：突然飙升说明内存不足
   
③ Java GC 日志
   → Full GC 频率：频繁 Full GC = 内存压力大
   → GC pause 时间：长时间 STW 会导致进程"假死"
   
④ 系统负载
   → sar -q：runq-sz / load average
   → 负载远高于 CPU 核数说明 IO 瓶颈或锁竞争
```

**注意**：不同系统的 sysstat 格式可能不同（如 iRaypleOS 使用自定义二进制格式），本地 `sar` 可能无法直接解码。

### 第四层：数据库/中间件—查依赖组件

**目标**：确认共享组件状态

```
① 数据库连接
   → 连接池是否耗尽：Druid recycle error / Hikari timeout
   → 连接数是否打满：max_connections
   
② 慢查询分析
   ┌─────────────────────────────────────────────┐
   │ Query_time 大 + Rows_examined 大 → 全表扫描│
   │ Query_time 大 + Rows_examined 小 → 锁等待  │
   └─────────────────────────────────────────────┘
   
③ 事务与锁
   → information_schema.innodb_trx — 查看当前事务
   → SHOW ENGINE INNODB STATUS — 查看锁信息
   → 长时间未提交的事务就是锁的源头
   
④ 网络/中间件
   → Nacos/Consul 连接数：稳定说明网络正常
   → Redis 响应：超时说明缓存层可能有问题
```

---

## 二、常见问题模式

### 模式 1：OOM Killer

**特征**：
- 多个进程同时消失（被杀了）
- userspace 日志中无异常记录（进程直接被内核杀掉，没有机会写日志）
- survivor 进程重启后正常

**验证**：
```
搜 messages: oom_kill
搜 messages: Killed process
确认被杀进程 PID 是否与日志中断裂的时间点对应
```

### 模式 2：锁等待占满连接池

**特征**：
- 慢查询中 `Query_time` 很大（几百到几千秒）但 `Rows_examined` 很小（几十到几百行）
- 所有慢查询的 `SET timestamp` 集中在很短的时间窗口内
- application.properties 中 `spring.datasource.druid.max-active` 被占满

**验证**：
```
慢查询日志 → 对比 Query_time 和 Rows_examined
确认是否有长时间未提交的事务在前面持有锁
```

### 模式 3：进程崩溃 + 自动重启

**特征**：
- 日志中有时间断层
- `[main]` 线程报错（重启过程的标志）
- 被 supervisor/systemd 自动拉起的进程 PID 发生变化

**验证**：
```
找 PID 变化 + GC 日志生成时间 = 进程启动时间
确认崩溃前最后的错误日志
```

### 模式 4：审计子系统过载

**特征**：
- `messages` 中出现 `kauditd_printk_skb: N callbacks suppressed`
- 系统越来越慢但不报具体错误
- cron 或其他定时任务执行过于频繁

**验证**：
```
搜 messages: kauditd_printk_skb
搜 messages: CMD → 统计 cron 执行间隔
正常应低于每分钟 10-20 次
```

### 模式 5：整机重启

**特征**：
- messages 中有两次内核 `Linux version` 日志（新旧各一次）
- 所有应用进程 PID 全部刷新
- sshd 重新开始监听

**验证**：
```
对比两次 kernel boot 的内核版本和启动时间
所有服务的日志文件创建时间集中在同一时刻
```

---

## 三、排查流程图

```
服务器"假死" / SSH 连不上
  │
  ├─ 应用日志排查
  │   ├─ 哪些服务活、哪些死 → 找故障面
  │   ├─ 分钟级日志量分析 → 找崩溃时间点
  │   └─ 错误关键字搜索 → 找报错类型
  │
  ├─ 是系统级还是应用级？
  │   ├─ 单服务 → 排查该服务(JVM/配置/线程池)
  │   └─ 多服务 → 往下走
  │
  ├─ 系统日志排查
  │   ├─ OOM Killer？ → 确认被杀进程
  │   ├─ 内核panic/lockup？ → 确认异常类型
  │   └─ 整机重启？ → 对比内核版本、确认重启原因
  │
  ├─ 资源排查
  │   ├─ CPU/内存 → sar 数据
  │   ├─ GC → Full GC 频率
  │   └─ 负载 → runq / load average
  │
  └─ 数据库排查
      ├─ 连接池是否耗尽？ → recycle error / timeout
      ├─ 慢查询是扫描还是等锁？ → Rows_examined vs Query_time
      └─ 是否有大事务未提交？ → innodb_trx / binlog
```

---

## 四、排查后建议模板

每次排查完成后应产出的结果：

```
1. 时间线（精确到秒）
   格式：HH:MM:SS  事件  [证据来源]

2. 根因链
   格式：A → B → C → 故障 [确认状态]

3. 排除项
   格式：可能性 → 结论 → 排除依据

4. 建议
   - 短期止血（症状缓解）
   - 中期防范（同类问题预防）
   - 长期建设（可观测性/监控）
```
