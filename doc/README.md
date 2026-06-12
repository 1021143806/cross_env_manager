# 文档目录

> 跨环境任务模板管理系统 - 文档中心

```
doc/
├── README.md                          # 本文档目录
├── api/                               # API 接口文档（按模块拆分）
│   ├── 00_index.md                    #   总览 + 状态码 + 数据库表
│   ├── 01_page_routes.md             #   页面路由
│   ├── 02_template.md                #   模板管理 API
│   ├── 03_task.md                    #   任务查询 & 重发 API
│   ├── 04_stats.md                   #   统计 API
│   ├── 05_join_qr.md                 #   交接点配置 API
│   ├── 06_config.md                  #   配置管理 API
│   ├── 07_auth.md                    #   认证 API
│   ├── 08_system.md                  #   系统 API（健康检查 + 升级管理）
│   └── 09_custom_table.md            #   定制表编辑 API
├── architecture/                      # 架构设计
│   ├── 整体架构.md                    #   三层架构、模块依赖、数据流
│   └── 数据库关系.md                  #   表结构、核心关联字段
├── dev/                               # 开发要求 & 规范
│   ├── 华睿要求.md                    #   ICS 任务状态码、调车逻辑约束
│   └── 定制表开发要求.md              #   定制表 CRUD 约束规则
├── modules/                           # 模块介绍
│   ├── dispatch.md                    #   调车模块
│   ├── addtask.md                     #   任务下发模块
│   ├── query.md                       #   查询模块
│   ├── config.md                      #   配置管理模块
│   └── upgrade.md                     #   升级管理模块
└── old/                               # 备份
    └── API.md                         #   旧版 API 文档（单文件）
```
