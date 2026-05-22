# FYWDS 日志分析 skill

## 日志目录
- 路径：`/main/app/fywds/logs`
- 文件数：216 个（213 个 .log 文件）
- 当前日志：`FYWDS.log`（实时写入）
- 历史日志：`FYWDS-YYYY-MM-DD.N.log`（按天+序号滚动，每个约 100MB）
- 最早日志：2024-05-26

## 日志格式
```
时间戳 [traceId] [线程池] 级别  类名 - 消息
2026-05-21 11:51:14.097 [-] [capacity-control-pool-1] INFO  cn.com.dahua.task.AutoCreateTask - [autoIssueTask] ...
```

## 核心业务模块

### 1. 自动任务下发 (AutoCreateTask)
- 关键字：`autoIssueTask`、`modelProcessId`、`modelCodeList size`
- 说明：根据模板自动创建跨工序任务
- 排查：`modelProcessId is XXX` 查看特定模板

### 2. 任务处理 (TaskHandleManager)
- 关键字：`subTaskCreate`、`updateFyTaskStatus`、`updateSubTaskStatus`
- 子任务创建：`insert into detail FyCrossTaskDetail(id=XXX`
- 状态更新：`修改 map {errorDesc=已下发, subOrderId=XXX`
- 异常：`errorDesc=请勿频繁请求`、`请勿重复下发任务`

### 3. HTTP 调用 (HttpUtil)
- 关键字：`url is >`、`response2 is >`
- 下发任务：`/ics/taskOrder/addTask`
- 继续任务：`/ics/out/task/continueTask`
- 查询库存：`/ics/out/getStockStatus`

### 4. 容量控制 (CrossTaskOrderServiceImpl)
- 关键字：`judgeHasEnoughCapacity`、`working task has`、`useCapaCity`
- 说明：判断区域容量是否足够

### 5. 任务状态上报 (RemoteTaskUploadThread)
- 关键字：`RemoteTaskUploadThread`、`PushJobStatus`、`report_status`
- 上报目标：RCS (10.1.107.31:5000)、调度系统 (10.68.2.40:5000)

### 6. 控制器 (CrossTaskController / TaskController)
- 下发入口：`ErpTaskController issue params`
- 状态更新：`TaskController updateTaskState params`
- 查询：`Controller query params`

## 常用查询

### 查特定任务
```bash
# 按 orderId 查
curl -X POST :5011/api/logs -d '{"folder":"/main/app/fywds/logs","pattern":"FYWDS*.log","keyword":"pad_html2026-05-21","line_start":1,"line_end":50000}'

# 按 tg_id 查
curl -X POST :5011/api/logs -d '{"folder":"/main/app/fywds/logs","pattern":"FYWDS*.log","keyword":"6631008","line_start":1,"line_end":50000}'
```

### 查模板调度
```bash
curl -X POST :5011/api/logs -d '{"folder":"/main/app/fywds/logs","pattern":"FYWDS.log","keyword":"modelProcessId is 519","line_start":1,"line_end":500}'
```

### 查异常
```bash
# 频繁请求
curl -X POST :5011/api/logs -d '{"folder":"/main/app/fywds/logs","pattern":"FYWDS*.log","keyword":"请勿频繁","line_start":1,"line_end":500}'

# 容量满
curl -X POST :5011/api/logs -d '{"folder":"/main/app/fywds/logs","pattern":"FYWDS*.log","keyword":"maxCapacity","line_start":1,"line_end":500}'
```

## 任务状态码
| 状态值 | 含义 |
|--------|------|
| 2 | 执行中 |
| 3 | 继续任务 (continueTask) |
| 4 | 已下发 |
| 10 | 执行中（未知） |

## ds 说
- FYWDS 日志量大（每天约 1.5GB），查询时建议指定日期文件缩小范围
- `pad_html` 前缀的任务来自 pad-html 系统
- `C2026` 前缀来自 ERP 系统，`CMP2026` 前缀来自 MES 系统
- 模板 519 是高频模板，约每 15 秒调度一次
- 容量满载时 `useCapaCity == maxCapacity`，新任务需等待
