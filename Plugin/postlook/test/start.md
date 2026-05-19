我们先设计好前端页面的功能和视觉效果，然后给出可以直接放到 `postlook/src/postlook/static/` 下的完整文件，FastAPI 稍作配置就能跑起来。

---

## 前端功能规划

### 页面布局（左右两栏）
- **侧边栏**：  
  - 项目 Logo + 名称 “postlook”  
  - 导航：日志查询、配置管理、服务状态  
  - 底部：暗黑/浅色模式切换按钮
- **主内容区**：根据导航切换显示三个面板

### 面板 1：日志查询
- 表单字段：`folder`、`pattern`、`keyword`、`lines`、`tail`、`recent_files`
- 提交按钮 → POST `/api/logs`
- 结果区域：显示总行数、是否截断，每条结果用卡片展示（文件名、行号、内容）

### 面板 2：配置管理
- 从后端加载当前 TOML 配置（预留接口 GET `/api/config`）
- `<textarea>` 编辑 TOML 内容
- 保存按钮 → POST `/api/config`（预留）
- 语法高亮和格式校验提示（基础）

### 面板 3：服务状态
- 显示服务是否在线（通过 GET `/api/health` 或 `/docs` 检查）
- 显示当前监控的根目录（从配置读取，预留）
- 启动时间、日志文件数量等（可逐步实现）

### 视觉风格
- **Mac 风格**：  
  - 圆角卡片（`border-radius: 12px`）  
  - 毛玻璃效果（`backdrop-filter: blur(10px)`）  
  - 柔和阴影（`box-shadow: 0 8px 32px rgba(0,0,0,0.3)`）  
  - 系统字体：`-apple-system, BlinkMacSystemFont, "SF Pro Text", ...`  
- **暗黑模式默认**：背景深灰 `#1e1e1e`，文字 `#f5f5f5`，强调色 `#007aff`（苹果蓝）  
- **亮色模式**：背景 `#f2f2f7`，文字 `#1d1d1f`

---

## 文件结构与集成方式

```
postlook/
└── src/
    └── postlook/
        ├── static/
        │   ├── index.html
        │   ├── style.css
        │   └── app.js
        └── app.py
```

在 `app.py` 中挂载静态文件并设置首页：

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI()

# 挂载静态文件
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
```

这样就实现了访问 `http://localhost:5011` 直接打开前端页面，且 AJAX 请求的 `/api/logs` 路径也能正常工作（因为静态文件挂载在根路径，API 路由需在前面定义好，或使用 `@app.get("/api/logs")` 等，FastAPI 会优先匹配路由再匹配静态文件）。

---

## 核心代码展示

### index.html（骨架）

```html
<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>postlook · 日志查询</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="app">
        <aside class="sidebar">
            <div class="logo">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
                <span>postlook</span>
            </div>
            <nav>
                <a href="#" data-panel="logs" class="active">
                    <svg>...</svg> 日志查询
                </a>
                <a href="#" data-panel="config">
                    <svg>...</svg> 配置管理
                </a>
                <a href="#" data-panel="status">
                    <svg>...</svg> 服务状态
                </a>
            </nav>
            <div class="theme-toggle">
                <button id="themeBtn" title="切换浅色/暗黑模式">
                    <span class="icon-sun">☀️</span>
                    <span class="icon-moon">🌙</span>
                </button>
            </div>
        </aside>
        <main class="content">
            <!-- 日志查询面板 -->
            <section id="panel-logs" class="panel active">
                <h2>日志查询</h2>
                <form id="logForm" class="glass-card">
                    <!-- 表单输入项... -->
                    <button type="submit" class="btn-primary">查询</button>
                </form>
                <div id="logResults" class="results-area"></div>
            </section>
            <!-- 配置管理面板 -->
            <section id="panel-config" class="panel">
                <h2>配置管理 (TOML)</h2>
                <div class="glass-card">
                    <textarea id="configEditor" rows="15"></textarea>
                    <button id="saveConfigBtn" class="btn-primary">保存配置</button>
                </div>
            </section>
            <!-- 服务状态面板 -->
            <section id="panel-status" class="panel">
                <h2>服务状态</h2>
                <div class="glass-card" id="statusInfo">
                    正在检查...
                </div>
            </section>
        </main>
    </div>
    <script src="app.js"></script>
</body>
</html>
```

### style.css（部分关键变量和样式）

```css
:root {
    --bg-primary: #1e1e1e;
    --bg-secondary: #2c2c2e;
    --text-primary: #f5f5f7;
    --text-secondary: #a1a1a6;
    --accent: #007aff;
    --glass-bg: rgba(44, 44, 46, 0.6);
    --glass-border: rgba(255,255,255,0.1);
    --card-radius: 12px;
    --transition: 0.2s ease;
}

[data-theme="light"] {
    --bg-primary: #f2f2f7;
    --bg-secondary: #ffffff;
    --text-primary: #1d1d1f;
    --text-secondary: #6e6e73;
    --accent: #007aff;
    --glass-bg: rgba(255,255,255,0.7);
    --glass-border: rgba(0,0,0,0.1);
}

* { margin:0; padding:0; box-sizing:border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    transition: background var(--transition), color var(--transition);
}
.app { display: flex; height: 100vh; }
.sidebar {
    width: 240px;
    background: var(--bg-secondary);
    backdrop-filter: blur(20px);
    padding: 20px;
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--glass-border);
}
/* ... 卡片、按钮等样式 ... */
.glass-card {
    background: var(--glass-bg);
    backdrop-filter: blur(10px);
    border: 1px solid var(--glass-border);
    border-radius: var(--card-radius);
    padding: 20px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
```

### app.js（核心逻辑）

```javascript
document.addEventListener('DOMContentLoaded', () => {
    // 主题切换
    const themeBtn = document.getElementById('themeBtn');
    const html = document.documentElement;
    themeBtn.addEventListener('click', () => {
        const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
    });
    // 应用本地存储的主题
    const savedTheme = localStorage.getItem('theme') || 'dark';
    html.setAttribute('data-theme', savedTheme);

    // 面板切换
    document.querySelectorAll('.sidebar nav a').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const panel = link.dataset.panel;
            // 激活导航和面板
        });
    });

    // 日志查询表单提交
    document.getElementById('logForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const payload = Object.fromEntries(formData.entries());
        payload.lines = parseInt(payload.lines);
        payload.recent_files = parseInt(payload.recent_files);
        payload.tail = payload.tail === 'true';

        try {
            const res = await fetch('/api/logs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            renderLogResults(data);
        } catch (err) {
            document.getElementById('logResults').innerHTML = `<p class="error">请求失败: ${err.message}</p>`;
        }
    });

    // 配置加载与保存（预留）
    // ...
});
```

---

## 下一步

现在你已经有前端的基础框架。如果你需要，我可以把完整的三个静态文件内容一次性提供（可以通过后续对话），然后你只需要：

1. 将这些文件放入 `src/postlook/static/`
2. 在 `app.py` 中添加上述静态文件挂载代码
3. 确保 FastAPI 的路由优先于静态文件（将 `@app.post("/api/logs")` 等路由定义在 `app.mount` 之前）

启动后访问 `http://localhost:5011`，即可看到现代暗黑风格的界面，并能尝试查询日志（前提是后端 `/api/logs` 接口已实现）。

要我先输出完整的三个前端文件吗？