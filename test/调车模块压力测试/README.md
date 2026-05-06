# 调车模块自动驾驶测试 - 模拟逻辑说明

## 整体架构

```mermaid
graph TB
    subgraph 测试脚本
        A[主循环线程<br/>0.5s间隔] -->|上报status=6| API1[/api/dispatch/report_status]
        B[负载完成线程<br/>0.6s间隔] -->|上报status=8| API1
        C[空车完成线程<br/>0.4s间隔] -->|上报status=8| API1
        A -->|每5轮| API2[/api/dispatch/execute]
    end
    subgraph 后端
        API1 -->|写入/删除| JSON[模板JSON文件]
        API1 -->|写入/删除| CC[currentCount.json]
        API2 -->|模拟下发空车| JSON
        API2 -->|记录| LOG[操作日志]
    end
```

## 主循环流程

```mermaid
flowchart TD
    START([开始]) --> INIT[初始化:<br/>禁用所有区域<br/>清理旧数据]
    INIT --> LOOP{主循环<br/>每0.5s}
    LOOP --> WAVE[正弦波计算<br/>in_prob = 0.5 + sin轮次×π/30×0.2<br/>概率30%~70%波动]
    WAVE --> RAND[随机选择区域]
    RAND --> DIR{in_prob决定方向}
    DIR -->|来任务| IN[随机选负载来模板+设备<br/>上报status=6<br/>记录deviceCode]
    DIR -->|离任务| OUT[随机选负载离模板+设备<br/>上报status=6<br/>记录deviceCode]
    IN --> CHECK{每5轮?}
    OUT --> CHECK
    CHECK -->|是| EXEC[调用execute API<br/>系统自动下发空车]
    CHECK -->|否| STAT{每10轮?}
    EXEC --> STAT
    STAT -->|是| PRINT[打印统计和区域摘要]
    STAT -->|否| WAIT[等待0.5s]
    PRINT --> WAIT
    WAIT --> LOOP
    LOOP -->|达到时长| CLEAN[清理数据]
    CLEAN --> END([结束])
```

## 负载任务完成流程

```mermaid
flowchart TD
    START([每0.6s触发]) --> GET[获取所有status=6的任务]
    GET -->    FILTER[过滤: 排除空车模板<br/>从配置动态获取]
    FILTER --> SORT[按create_time升序排序<br/>优先完成最早的任务]
    SORT --> PICK[取第一个任务]
    PICK --> REPORT[使用后端记录的deviceCode<br/>上报status=8]
    REPORT --> BACKEND{后端处理}
    BACKEND -->|direction=in<br/>来任务| IN[从模板JSON删除<br/>写入currentCount.json +1]
    BACKEND -->|direction=out<br/>离任务| OUT[从模板JSON删除<br/>从currentCount.json删除 -1]
```

## 空车任务完成流程

```mermaid
flowchart TD
    START([每0.4s触发]) --> GET[获取所有status=6的任务]
    GET -->    FILTER[过滤: 只取空车模板<br/>从配置动态获取]
    FILTER --> SORT[按create_time升序排序]
    SORT --> PICK[取第一个任务]
    PICK --> TYPE{模板类型?}
    TYPE -->|空车任务| DONE[使用后端记录的deviceCode+deviceNum<br/>上报status=8]
    IN --> BACKEND_IN[后端: 从模板JSON删除<br/>写入currentCount.json +1]
    OUT --> BACKEND_OUT[后端: 从模板JSON删除<br/>从currentCount.json删除 -1]
```

## 数据流示意

```mermaid
flowchart LR
    subgraph 来方向
        A1[负载来 status=6] -->|a+1| T1[模板JSON]
        T1 -->|完成 status=8| C1[currentCount.json +1]
        A2[empty_in来空车 status=6] -->|a+1| T2[模板JSON]
        T2 -->|完成 status=8| C2[currentCount.json +1]
    end
    subgraph 离方向
        B1[负载离 status=6] -->|b+1| T3[模板JSON]
        T3 -->|完成 status=8| C3[currentCount.json -1]
        B2[empty_out回空车 status=6] -->|b+1| T4[模板JSON]
        T4 -->|完成 status=8| C4[currentCount.json -1<br/>从currentCount选设备]
    end
```

## 计算公式

```mermaid
flowchart TD
    CC[currentCount] --> EC
    A[a = 来方向status=6任务数] --> EC
    B[b = 离方向status=6任务数] --> EC
    EC[expectedCount = currentCount + a - b] --> CMP{比较}
    CMP -->|> xmax| OUT[need = expectedCount - xmax<br/>正数, 需调出<br/>下发empty_out回空车]
    CMP -->|< xmin| IN[need = expectedCount - xmin<br/>负数, 需调入<br/>下发empty_in来空车]
    CMP -->|xmin ≤ ec ≤ xmax| BAL[need = 0<br/>平衡, 无需下发]
```

## 关键设计决策

| 决策 | 说明 |
|------|------|
| 负载来/离使用相同 deviceCode | 通过 dev_code_map 维护，确保同一设备先来后离时 deviceCode 一致 |
| DKCback 从 currentCount 选设备 | 模拟真实场景：回空车让当前区域中的设备离开 |
| 正弦波模拟高峰/低谷 | 来任务概率在 30%~70% 波动，周期60轮 |
| 空车完成比负载快 | 0.4s vs 0.6s，模拟空车调度更快 |
| 区域禁用模式 | 走模拟下发逻辑，不实际发送HTTP请求 |
