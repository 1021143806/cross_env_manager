        // 业务逻辑 (保留原有全部逻辑，仅调整DOM操作适配新结构)
        (function() {
            if (typeof config === 'undefined') {
                alert('配置文件加载失败，请确保config.js存在且可访问。');
                throw new Error('config is not defined');
            }

            const shelfHistory = {};
            let _enableRollerTask = false;  // 全局辊筒任务开关（从 config._features 读取）
            let _rollerRefreshTimer = null;  // 定时刷新 timer
            let priorityLastClickTime = 0;
            const lastCapacityLoadByCode = {};

            const areaSelect = document.getElementById('area-select');
            const taskSelect = document.getElementById('task-select');
            const shelfGroup = document.getElementById('shelf-group');
            const shelfInput = document.getElementById('shelf-input');
            const shelfError = document.getElementById('shelf-error');
            const shelfLock = document.getElementById('shelf-lock');
            const taskPathGroup = document.getElementById('task-path-group');
            const taskPathSelect = document.getElementById('task-path-select');
            const taskPathError = document.getElementById('task-path-error');
            const rollerTaskInfo = document.getElementById('roller-task-info');
            const rollerPointDisplay = document.getElementById('roller-point-display');
            const rollerSentOrders = document.getElementById('roller-sent-orders');
            const rollerSentOrdersList = document.getElementById('roller-sent-orders-list');
            const rollerCapacityBadge = document.getElementById('roller-capacity-badge');
            const submitBtn = document.getElementById('submit-btn');
            const responseBox = document.getElementById('response-box');
            const debugToggle = document.getElementById('debug-toggle');
            const debugInfo = document.getElementById('debug-info');
            const queryToggleOptions = document.querySelectorAll('.toggle-option');
            const shelfQueryGroup = document.getElementById('shelf-query-group');
            const orderQueryGroup = document.getElementById('order-query-group');
            const deviceQueryGroup = document.getElementById('device-query-group');
            const shelfQueryInput = document.getElementById('shelf-query-input');
            const orderQueryInput = document.getElementById('order-query-input');
            const deviceQueryInput = document.getElementById('device-query-input');
            const queryBtn = document.getElementById('query-btn');
            const taskDetails = document.getElementById('task-details');
            const emptyState = document.getElementById('empty-state');
            const queryHistoryContainer = document.getElementById('query-history-container');
            const noResponsePlaceholder = document.getElementById('no-response-placeholder');
            const deviceInput = document.getElementById('device-input');
            const deviceDropdownMenu = document.getElementById('device-dropdown-menu');
            const deviceClearBtn = document.getElementById('device-clear-btn');
            let currentDeviceSuggestions = [];  // agv_robot_ext: [{deviceCode, deviceNum}]

            // Bootstrap modals
            const successModal = new bootstrap.Modal(document.getElementById('success-modal'));
            const taskExistsModal = new bootstrap.Modal(document.getElementById('task-exists-modal'));
            const priorityModal = new bootstrap.Modal(document.getElementById('priority-modal'));
            const capacityModal = new bootstrap.Modal(document.getElementById('capacity-modal'));
            const helpModal = new bootstrap.Modal(document.getElementById('help-modal'));
            
            const taskExistsMessage = document.getElementById('task-exists-message');
            const priorityModalTitle = document.getElementById('priority-modal-title');
            const priorityModalMessage = document.getElementById('priority-modal-message');
            const capacityModalMessage = document.getElementById('capacity-modal-message');
            const helpModalBody = document.getElementById('help-modal-body');

            // ==================== 最近使用任务功能 ====================
            const RECENT_TASKS_KEY = 'recent_tasks';
            const MAX_RECENT = 5;

            // ==================== 每日区域使用统计 ====================
            const AREA_USAGE_KEY = 'area_usage';

            function getAreaUsage() {
                try {
                    const data = localStorage.getItem(AREA_USAGE_KEY);
                    return data ? JSON.parse(data) : {};
                } catch { return {}; }
            }

            function recordAreaUsage(areaName) {
                const usage = getAreaUsage();
                const today = new Date().toISOString().slice(0, 10);
                if (!usage[today]) usage[today] = {};
                usage[today][areaName] = (usage[today][areaName] || 0) + 1;
                try {
                    localStorage.setItem(AREA_USAGE_KEY, JSON.stringify(usage));
                } catch (e) {
                    console.warn('保存区域使用统计失败:', e);
                }
            }

            function getTodayUsage() {
                const usage = getAreaUsage();
                const today = new Date().toISOString().slice(0, 10);
                return usage[today] || {};
            }

            // ==================== 每日任务使用统计 ====================
            const TASK_USAGE_KEY = 'task_usage';

            function getTaskUsage() {
                try {
                    const data = localStorage.getItem(TASK_USAGE_KEY);
                    return data ? JSON.parse(data) : {};
                } catch { return {}; }
            }

            function recordTaskUsageCount(areaName, taskName) {
                const usage = getTaskUsage();
                const today = new Date().toISOString().slice(0, 10);
                if (!usage[today]) usage[today] = {};
                const key = `${areaName}::${taskName}`;
                usage[today][key] = (usage[today][key] || 0) + 1;
                try {
                    localStorage.setItem(TASK_USAGE_KEY, JSON.stringify(usage));
                } catch (e) {
                    console.warn('保存任务使用统计失败:', e);
                }
            }

            function getTodayTaskUsage() {
                const usage = getTaskUsage();
                const today = new Date().toISOString().slice(0, 10);
                return usage[today] || {};
            }

            // ==================== 每日设备使用统计 ====================
            const DEVICE_USAGE_KEY = 'device_usage';

            function getDeviceUsage() {
                try { const d = localStorage.getItem(DEVICE_USAGE_KEY); return d ? JSON.parse(d) : {}; } catch { return {}; }
            }

            function recordDeviceUsage(deviceCode) {
                const usage = getDeviceUsage();
                const today = new Date().toISOString().slice(0, 10);
                if (!usage[today]) usage[today] = {};
                usage[today][deviceCode] = (usage[today][deviceCode] || 0) + 1;
                try { localStorage.setItem(DEVICE_USAGE_KEY, JSON.stringify(usage)); } catch {}
            }

            function getTodayDeviceUsage() {
                const usage = getDeviceUsage();
                const today = new Date().toISOString().slice(0, 10);
                return usage[today] || {};
            }

            // ==================== 通用工具函数 ====================
            function escapeHtml(str) {
                const div = document.createElement('div');
                div.textContent = str;
                return div.innerHTML;
            }

            function copyText(text, msg) {
                // 尝试 Clipboard API（HTTPS 或 localhost 环境）
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).then(() => {
                        showAlert(msg || '已复制', 'success');
                    }).catch(() => fallbackCopy(text, msg));
                } else {
                    fallbackCopy(text, msg);
                }
            }

            function fallbackCopy(text, msg) {
                // 尝试劫持 copy 事件 + execCommand
                const handler = (e) => {
                    e.clipboardData.setData('text/plain', text);
                    e.preventDefault();
                };
                document.addEventListener('copy', handler);
                try {
                    if (document.execCommand('copy')) {
                        showAlert(msg || '已复制', 'success');
                        document.removeEventListener('copy', handler);
                        return;
                    }
                } catch (e) { /* fallback below */ }
                document.removeEventListener('copy', handler);
                // 终极 fallback：弹出提示框，用户按 Ctrl+C 手动复制
                try {
                    window.prompt(`按 Ctrl+C 复制${msg ? '（' + msg + '）' : ''}，然后点击取消关闭:`, text);
                } catch (e) {
                    showAlert('复制失败，请手动复制文本', 'warning');
                }
            }

            function getBuildingColor(prefix) {
                if (!prefix || prefix === '其他') return '#6c757d';
                let hash = 0;
                for (let i = 0; i < prefix.length; i++) {
                    hash = ((hash << 5) - hash) + prefix.charCodeAt(i);
                    hash |= 0;
                }
                // 黄金角散布，确保相邻楼栋色相差异大
                const hue = ((Math.abs(hash) * 137.508) % 360);
                return `hsl(${hue}, 60%, 50%)`;
            }

            function refreshCountDisplay() {
                // 刷新区域下拉框计数文本（不重建DOM，保留已选项）
                const todayUsage = getTodayUsage();
                areaSelect.querySelectorAll('optgroup option').forEach(opt => {
                    const count = todayUsage[opt.value] || 0;
                    opt.textContent = count > 0 ? `${opt.value}（今日${count}次）` : opt.value;
                });
                // 刷新任务下拉框计数文本
                const area = areaSelect.value;
                if (area && config.areas[area]) {
                    const todayTaskUsage = getTodayTaskUsage();
                    taskSelect.querySelectorAll('optgroup option').forEach(opt => {
                        const count = todayTaskUsage[`${area}::${opt.value}`] || 0;
                        opt.textContent = count > 0 ? `${opt.value}（今日${count}次）` : opt.value;
                    });
                }
            }

            // ==================== 查询历史 ====================
            const QUERY_HISTORY_KEY = 'query_history';
            const MAX_QUERY_HISTORY = 5;

            function getQueryHistory() {
                try {
                    const data = localStorage.getItem(QUERY_HISTORY_KEY);
                    return data ? JSON.parse(data) : [];
                } catch { return []; }
            }

            function saveQueryHistory(entry) {
                const history = getQueryHistory();
                const key = entry.type + '::' + entry.value;
                const idx = history.findIndex(h => h.type + '::' + h.value === key);
                if (idx > -1) history.splice(idx, 1);
                history.unshift(entry);
                if (history.length > MAX_QUERY_HISTORY) history.length = MAX_QUERY_HISTORY;
                try {
                    localStorage.setItem(QUERY_HISTORY_KEY, JSON.stringify(history));
                } catch (e) { console.warn('保存查询历史失败:', e); }
            }

            function getRecentTasks() {
                try {
                    const data = localStorage.getItem(RECENT_TASKS_KEY);
                    return data ? JSON.parse(data) : [];
                } catch {
                    return [];
                }
            }

            function saveRecentTasks(tasks) {
                try {
                    localStorage.setItem(RECENT_TASKS_KEY, JSON.stringify(tasks));
                } catch (e) {
                    console.warn('保存最近任务失败:', e);
                }
            }

            function recordTaskUsage(taskName, areaName) {
                const recent = getRecentTasks();
                const entry = `${areaName}::${taskName}`;
                
                // 去重：如果已存在则移除旧记录
                const index = recent.indexOf(entry);
                if (index > -1) recent.splice(index, 1);
                
                // 插入到最前面
                recent.unshift(entry);
                
                // 限制数量
                if (recent.length > MAX_RECENT) recent.pop();
                
                saveRecentTasks(recent);
                renderRecentTasks();
            }

            function renderRecentTasks() {
                const container = document.getElementById('recent-tasks-container');
                if (!container) return;
                
                const recent = getRecentTasks();
                if (recent.length === 0) {
                    container.innerHTML = '';
                    return;
                }
                
                let html = '<div class="recent-tasks">';
                html += '<span class="recent-tasks-label"><i class="bi bi-clock-history me-1"></i>最近:</span>';
                
                recent.forEach((entry, idx) => {
                    const parts = entry.split('::');
                    if (parts.length !== 2) return;
                    const [area, task] = parts;
                    
                    // 检查区域和任务是否还存在
                    if (!config.areas[area] || !config.areas[area].tasks[task]) {
                        // 如果不存在，跳过（下次保存时会自动清除）
                        return;
                    }
                    
                    html += `<button class="btn btn-sm btn-outline-secondary recent-task-btn" 
                             data-area="${area}" data-task="${task}" 
                             title="${task} (${area})">${task}</button>`;
                });
                
                html += '</div>';
                container.innerHTML = html;
                
                // 绑定点击事件
                container.querySelectorAll('.recent-task-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const area = this.dataset.area;
                        const task = this.dataset.task;
                        
                        // 检查区域和任务是否仍然有效
                        if (!config.areas[area] || !config.areas[area].tasks[task]) {
                            showAlert('该任务已不存在，已从最近任务中移除', 'warning');
                            // 从最近任务中移除
                            const recent = getRecentTasks();
                            const entry = `${area}::${task}`;
                            const idx = recent.indexOf(entry);
                            if (idx > -1) {
                                recent.splice(idx, 1);
                                saveRecentTasks(recent);
                                renderRecentTasks();
                            }
                            return;
                        }
                        
                        // 自动切换区域
                        areaSelect.value = area;
                        updateTaskOptions();
                        
                        // 自动切换任务
                        taskSelect.value = task;
                        updateFormFields();
                        
                        // 高亮提醒
                        this.classList.add('btn-primary');
                        this.classList.remove('btn-outline-secondary');
                        setTimeout(() => {
                            this.classList.remove('btn-primary');
                            this.classList.add('btn-outline-secondary');
                        }, 1500);
                    });
                });
                
                // 如果没有有效的最近任务，隐藏容器
                if (!container.querySelector('.recent-task-btn')) {
                    container.innerHTML = '';
                }
            }

            function renderAreaOptions() {
                const todayUsage = getTodayUsage();
                const groups = {};
                areaSelect.innerHTML = '<option value="">请选择区域</option>';
                Object.keys(config.areas).sort((a, b) => {
                    const countA = todayUsage[a] || 0;
                    const countB = todayUsage[b] || 0;
                    if (countB !== countA) return countB - countA;
                    return a.localeCompare(b, 'zh-Hans-CN');
                }).forEach(area => {
                    const match = area.match(/^(A\d+)/);
                    const group = match ? match[1] + ' 栋' : '其他';
                    if (!groups[group]) groups[group] = [];
                    groups[group].push(area);
                });
                const groupOrder = Object.keys(groups).sort((a, b) => {
                    if (a === '其他') return 1;
                    if (b === '其他') return -1;
                    return a.localeCompare(b, 'zh-Hans-CN', { numeric: true });
                });
                groupOrder.forEach(groupName => {
                    const bldPrefix = groupName.replace(' 栋', '');
                    const bldColor = getBuildingColor(bldPrefix);
                    const optgroup = document.createElement('optgroup');
                    optgroup.label = groupName;
                    if (bldColor) optgroup.style.color = bldColor;
                    groups[groupName].forEach(area => {
                        const count = todayUsage[area] || 0;
                        const option = document.createElement('option');
                        option.value = area;
                        option.className = 'with-building-border';
                        if (bldColor) option.style.borderLeftColor = bldColor;
                        option.textContent = count > 0 ? `${area}（今日${count}次）` : area;
                        optgroup.appendChild(option);
                    });
                    areaSelect.appendChild(optgroup);
                });
            }

            function initPage() {
                renderAreaOptions();
                // 显示配置版本号
                const verEl = document.getElementById('config-version');
                if (verEl) verEl.textContent = 'v' + (config._version || config._client_version || '?');
                // 显示查询历史
                renderQueryHistory();
                // 预加载设备列表
                loadDeviceSuggestions();
                
                // 读取辊筒任务全局开关
                _enableRollerTask = config._features && config._features.enable_roller_task === true;
                
                areaSelect.addEventListener('change', updateTaskOptions);
                areaSelect.addEventListener('change', () => { if (deviceInput) deviceInput.value = ''; });
                taskSelect.addEventListener('change', updateFormFields);
                taskSelect.addEventListener('change', () => { if (deviceInput) deviceInput.value = ''; });
                submitBtn.addEventListener('click', submitTask);
                debugToggle.addEventListener('click', () => {
                    debugInfo.style.display = debugInfo.style.display === 'block' ? 'none' : 'block';
                    debugToggle.innerHTML = debugInfo.style.display === 'block' ? 
                        '<i class="bi bi-code-slash me-2"></i>隐藏发送的报文' : 
                        '<i class="bi bi-code-slash me-2"></i>查看发送的报文';
                });
                
                queryToggleOptions.forEach(opt => opt.addEventListener('click', toggleQueryType));
                queryBtn.addEventListener('click', queryTasks);
                
                // 复制图标事件委托 (处理动态生成的任务查询结果中的复制)
                taskDetails.addEventListener('click', (e) => {
                    const icon = e.target.closest('.copy-icon');
                    if (icon && icon.dataset.copy) {
                        copyText(icon.dataset.copy, icon.dataset.msg || '已复制');
                    }
                });
                // 响应信息复制按钮
                responseBox.addEventListener('click', (e) => {
                    const btn = e.target.closest('#copy-response-btn');
                    if (btn) {
                        const jsonEl = document.getElementById('response-json');
                        if (jsonEl) copyText(jsonEl.textContent, '响应已复制');
                    }
                });
                
                taskPathSelect.addEventListener('change', () => {
                    if (taskPathSelect.value && taskPathSelect.value !== '请选择任务路径') {
                        taskPathError.style.display = 'none';
                        taskPathSelect.style.borderColor = 'var(--border-color)';
                    } else {
                        taskPathSelect.style.borderColor = '#dc3545';
                    }
                });
                
                shelfInput.addEventListener('input', function() {
                    if (this.value.trim()) {
                        shelfError.style.display = 'none';
                        this.style.borderColor = 'var(--border-color)';
                    } else {
                        this.style.borderColor = '#dc3545';
                    }
                    validateShelfLock();
                });

                taskPathSelect.addEventListener('focus', () => {
                    const area = areaSelect.value;
                    const taskName = taskSelect.value;
                    if (area && taskName) {
                        const task = config.areas[area]?.tasks[taskName];
                        if (task && task.requires_task_path && task.capacity > 0) {
                            loadPathCapacity(task.code, task.capacity);
                        }
                    }
                });

                document.getElementById('help-toggle').addEventListener('click', showHelpModal);
                
                // 只有在配置管理按钮存在时才添加事件监听器
                const configToggle = document.getElementById('config-toggle');
                if (configToggle) {
                    configToggle.addEventListener('click', function() {
                        // 切换到内联配置视图
                        if (typeof switchToConfig === 'function') {
                            switchToConfig();
                        } else {
                            window.open('/config', '_blank');
                        }
                    });
                }
                
                // 登录相关事件监听
                setupLoginHandlers();
                
                // 渲染最近使用任务
                renderRecentTasks();
            }

            // ==================== 登录相关函数 ====================
            
            function setupLoginHandlers() {
                // 登录按钮点击事件
                const loginBtn = document.getElementById('login-btn');
                if (loginBtn) {
                    loginBtn.addEventListener('click', function() {
                        // 模态框已通过data-bs-target自动打开
                    });
                }
                
                // 登录提交按钮
                const loginSubmitBtn = document.getElementById('login-submit');
                if (loginSubmitBtn) {
                    loginSubmitBtn.addEventListener('click', handleLogin);
                }
                
                // 注销按钮
                const logoutBtn = document.getElementById('logout-btn');
                if (logoutBtn) {
                    logoutBtn.addEventListener('click', handleLogout);
                }
                
                // 监听登录模态框中的回车键
                const loginModal = document.getElementById('login-modal');
                if (loginModal) {
                    loginModal.addEventListener('keypress', function(e) {
                        if (e.key === 'Enter' && e.target.closest('#login-modal .modal-body')) {
                            handleLogin();
                        }
                    });
                }
                
                // 检查登录状态
                checkAuthStatus();
            }
            
            async function handleLogin() {
                const username = document.getElementById('login-username').value.trim();
                const password = document.getElementById('login-password').value.trim();
                const loginError = document.getElementById('login-error');
                const loginSpinner = document.getElementById('login-spinner');
                const loginSubmitBtn = document.getElementById('login-submit');
                
                if (!username || !password) {
                    showLoginError('请输入用户名和密码');
                    return;
                }
                
                // 显示加载状态
                loginSpinner.classList.remove('d-none');
                loginSubmitBtn.disabled = true;
                loginError.style.display = 'none';
                
                try {
                    const response = await fetch('/api/login', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ username, password })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        // 登录成功，关闭模态框并刷新页面
                        const loginModal = bootstrap.Modal.getInstance(document.getElementById('login-modal'));
                        if (loginModal) {
                            loginModal.hide();
                        }
                        
                        // 显示成功消息
                        showAlert('登录成功！', 'success');
                        
                        // 刷新页面以更新登录状态
                        setTimeout(() => {
                            window.location.reload();
                        }, 1000);
                    } else {
                        showLoginError(data.error || '登录失败');
                    }
                } catch (error) {
                    showLoginError('网络错误，请检查连接');
                    console.error('登录错误:', error);
                } finally {
                    // 恢复按钮状态
                    loginSpinner.classList.add('d-none');
                    loginSubmitBtn.disabled = false;
                }
            }
            
            async function handleLogout() {
                try {
                    const response = await fetch('/api/logout', {
                        method: 'POST'
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        showAlert('已成功注销', 'info');
                        // 刷新页面以更新登录状态
                        setTimeout(() => {
                            window.location.reload();
                        }, 1000);
                    } else {
                        showAlert('注销失败: ' + (data.error || '未知错误'), 'danger');
                    }
                } catch (error) {
                    showAlert('网络错误，请检查连接', 'danger');
                    console.error('注销错误:', error);
                }
            }
            
            async function checkAuthStatus() {
                try {
                    const response = await fetch('/api/auth/status');
                    const data = await response.json();
                    
                    // 更新页面上的登录状态显示
                    updateLoginUI(data.logged_in, data.username);
                    
                    // 根据登录状态控制按钮显示
                    toggleButtonsByLoginStatus(data.logged_in);
                } catch (error) {
                    console.error('检查登录状态错误:', error);
                }
            }
            
            function updateLoginUI(loggedIn, username) {
                // 这个函数主要用于动态更新（如果页面不是通过模板渲染）
                // 对于模板渲染的页面，登录状态已经在服务器端渲染
                console.log('登录状态:', loggedIn ? `已登录 (${username})` : '未登录');
            }
            
            function toggleButtonsByLoginStatus(loggedIn) {
                // 根据登录状态显示/隐藏按钮
                // 这里可以添加需要根据登录状态控制的按钮
                const taskItems = document.querySelectorAll('.task-item');
                
                taskItems.forEach(item => {
                    // 如果已登录，添加点击跳转功能
                    if (loggedIn) {
                        item.style.cursor = 'pointer';
                        item.addEventListener('click', function() {
                            const taskId = this.dataset.taskId;
                            if (taskId) {
                                // 跳转到任务查询页面
                                window.open(`/task_query?task_id=${taskId}`, '_blank');
                            }
                        });
                    } else {
                        item.style.cursor = 'default';
                        // 移除事件监听器
                        const newItem = item.cloneNode(true);
                        item.parentNode.replaceChild(newItem, item);
                    }
                });
            }
            
            function showLoginError(message) {
                const loginError = document.getElementById('login-error');
                loginError.textContent = message;
                loginError.style.display = 'block';
            }
            
            function showAlert(message, type = 'info') {
                const alertContainer = document.querySelector('.alert-container');
                if (!alertContainer) return;
                
                const alertId = 'alert-' + Date.now();
                const alertHtml = `
                    <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show animate__animated animate__fadeInRight" role="alert">
                        ${message}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                `;
                
                alertContainer.insertAdjacentHTML('beforeend', alertHtml);
                
                // 5秒后自动消失
                setTimeout(() => {
                    const alert = document.getElementById(alertId);
                    if (alert) {
                        alert.classList.remove('show');
                        setTimeout(() => alert.remove(), 300);
                    }
                }, 5000);
            }

            function validateShelfLock() {
                const area = areaSelect.value;
                const taskName = taskSelect.value;
                if (area && taskName && config.areas[area]?.tasks[taskName]) {
                    const task = config.areas[area].tasks[taskName];
                    if (task.requires_shelf) {
                        const shelf = shelfInput.value.trim();
                        if (shelf && shelfHistory[shelf] && (Date.now() - shelfHistory[shelf]) < 300000) {
                            shelfLock.style.display = 'block';
                            submitBtn.disabled = true;
                        } else {
                            shelfLock.style.display = 'none';
                            submitBtn.disabled = false;
                        }
                    }
                }
            }

            // ==================== 辊筒任务已下发缓存管理 ====================
            const SENT_ORDERS_KEY = 'roller_sent_orders';

            function getRollerSentOrders(area, taskName) {
                try {
                    const all = JSON.parse(localStorage.getItem(SENT_ORDERS_KEY) || '{}');
                    return all[`${area}::${taskName}`] || [];
                } catch { return []; }
            }

            function saveRollerSentOrders(area, taskName, orders) {
                try {
                    const all = JSON.parse(localStorage.getItem(SENT_ORDERS_KEY) || '{}');
                    all[`${area}::${taskName}`] = orders;
                    localStorage.setItem(SENT_ORDERS_KEY, JSON.stringify(all));
                } catch (e) { console.warn('保存辊筒任务缓存失败:', e); }
            }

            function addRollerSentOrder(area, taskName, orderId, rollerPoint) {
                const orders = getRollerSentOrders(area, taskName);
                orders.unshift({ orderId, rollerPoint, dispatchedAt: Date.now() });
                saveRollerSentOrders(area, taskName, orders);
            }

            async function checkAndCleanRollerOrders(area, taskName) {
                const task = config.areas[area]?.tasks[taskName];
                if (!task) return [];
                const orders = getRollerSentOrders(area, taskName);
                if (orders.length === 0) return [];

                // 逐个查询状态，移除已完成的 (status===8)
                const active = [];
                for (const o of orders) {
                    try {
                        const res = await fetch('/addtask/query', {
                            method: 'POST', headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ orderId: o.orderId })
                        });
                        if (res.status === 404) { active.push(o); continue; }
                        const data = await res.json();
                        if (data.success && data.mainTask) {
                            if (data.mainTask.taskStatus === 8) continue; // 已完成，自动释放
                            o.status = data.mainTask.taskStatus;
                            active.push(o);
                        } else {
                            active.push(o);
                        }
                    } catch { active.push(o); }
                }
                saveRollerSentOrders(area, taskName, active);
                return active;
            }

            function renderRollerSentOrders(orders, capacity) {
                if (!rollerSentOrdersList) return;
                const cap = capacity || 0;
                if (orders.length === 0) {
                    rollerSentOrdersList.innerHTML = '<div class="text-muted" style="font-size:0.75rem;">暂无已下发任务</div>';
                    rollerCapacityBadge.style.display = 'none';
                    return;
                }
                const statusMap = {4:'正在发送',6:'执行中',8:'已完成',9:'已下发','-1':'容量管控'};
                rollerCapacityBadge.style.display = 'inline-block';
                rollerCapacityBadge.textContent = `${orders.filter(o => o.status !== 8).length}/${cap || '∞'}`;
                let html = '';
                orders.slice(0, 5).forEach(o => {
                    const st = o.status || 0;
                    const label = statusMap[st] || `状态${st}`;
                    const cls = st === 8 ? 'text-success' : (st === 6 ? 'text-primary' : 'text-warning');
                    const shortId = o.orderId.length > 40 ? o.orderId.slice(0, 38) + '…' : o.orderId;
                    const time = o.dispatchedAt ? new Date(o.dispatchedAt).toLocaleTimeString() : '';
                    html += `<div class="d-flex justify-content-between align-items-center py-1 border-bottom" style="font-size:0.75rem;">
                        <span title="${o.orderId}">${shortId}</span>
                        <span class="${cls} fw-semibold">${label}</span>
                    </div>`;
                });
                if (orders.length > 5) {
                    html += `<div class="text-muted text-center mt-1" style="font-size:0.7rem;">还有 ${orders.length - 5} 条…</div>`;
                }
                rollerSentOrdersList.innerHTML = html;
            }

            async function refreshRollerSentOrders() {
                const area = areaSelect.value;
                const taskName = taskSelect.value;
                if (!area || !taskName) return;
                const task = config.areas[area]?.tasks[taskName];
                if (!task || !(_enableRollerTask && task.roller_task === true)) return;
                const active = await checkAndCleanRollerOrders(area, taskName);
                renderRollerSentOrders(active, task.capacity || 0);
            }

            function startRollerRefreshTimer() {
                stopRollerRefreshTimer();
                _rollerRefreshTimer = setInterval(refreshRollerSentOrders, 15000);
            }

            function stopRollerRefreshTimer() {
                if (_rollerRefreshTimer) {
                    clearInterval(_rollerRefreshTimer);
                    _rollerRefreshTimer = null;
                }
            }

            function updateTaskOptions() {
                const area = areaSelect.value;
                taskSelect.innerHTML = '<option value="">请选择任务模板</option>';
                if (area && config.areas[area]) {
                    const tasks = config.areas[area].tasks;
                    const todayTaskUsage = getTodayTaskUsage();
                    const getCount = (name) => todayTaskUsage[`${area}::${name}`] || 0;

                    // 辊筒任务（roller_task=true）→ 辊筒分组
                    // 空车任务（requires_shelf=false, 非辊筒）→ 空车分组
                    // 非空车任务（requires_shelf=true）→ 非空车分组
                    const rollerTasks = _enableRollerTask
                        ? Object.keys(tasks).filter(n => tasks[n].roller_task === true)
                        : [];
                    const rollerSet = new Set(rollerTasks);
                    const emptyTasks = Object.keys(tasks).filter(n => !tasks[n].requires_shelf && !rollerSet.has(n));
                    const loadedTasks = Object.keys(tasks).filter(n => tasks[n].requires_shelf);
                    const sortByUsage = (a, b) => {
                        const ca = getCount(a), cb = getCount(b);
                        if (cb !== ca) return cb - ca;
                        return a.localeCompare(b, 'zh-Hans-CN');
                    };
                    rollerTasks.sort(sortByUsage);
                    emptyTasks.sort(sortByUsage);
                    loadedTasks.sort(sortByUsage);

                    // 创建辊筒任务分组（最前面）
                    if (rollerTasks.length > 0) {
                        const rollerGroup = document.createElement('optgroup');
                        rollerGroup.label = `⏏️ 辊筒任务 (${rollerTasks.length})`;
                        rollerTasks.forEach(taskName => {
                            const count = getCount(taskName);
                            const option = document.createElement('option');
                            option.value = taskName;
                            option.textContent = count > 0 ? `${taskName}（今日${count}次）` : taskName;
                            rollerGroup.appendChild(option);
                        });
                        taskSelect.appendChild(rollerGroup);
                    }

                    // 创建空车任务分组
                    if (emptyTasks.length > 0) {
                        const emptyGroup = document.createElement('optgroup');
                        emptyGroup.label = `🚚 空车任务 (${emptyTasks.length})`;
                        emptyTasks.forEach(taskName => {
                            const count = getCount(taskName);
                            const option = document.createElement('option');
                            option.value = taskName;
                            option.textContent = count > 0 ? `${taskName}（今日${count}次）` : taskName;
                            emptyGroup.appendChild(option);
                        });
                        taskSelect.appendChild(emptyGroup);
                    }

                    // 创建非空车任务分组
                    if (loadedTasks.length > 0) {
                        const loadedGroup = document.createElement('optgroup');
                        loadedGroup.label = `📦 非空车任务 (${loadedTasks.length})`;
                        loadedTasks.forEach(taskName => {
                            const count = getCount(taskName);
                            const option = document.createElement('option');
                            option.value = taskName;
                            option.textContent = count > 0 ? `${taskName}（今日${count}次）` : taskName;
                            loadedGroup.appendChild(option);
                        });
                        taskSelect.appendChild(loadedGroup);
                    }
                }
                updateFormFields();
            }

            function updateFormFields() {
                const area = areaSelect.value;
                const taskName = taskSelect.value;
                shelfError.style.display = 'none';
                taskPathError.style.display = 'none';
                shelfLock.style.display = 'none';
                
                if (area && taskName && config.areas[area]?.tasks[taskName]) {
                    const task = config.areas[area].tasks[taskName];
                    const isRoller = _enableRollerTask && task.roller_task === true;
                    
                    if (isRoller) {
                        // 辊筒任务：隐藏货架和路径，显示固定点位信息
                        shelfGroup.style.display = 'none';
                        taskPathGroup.style.display = 'none';
                        rollerTaskInfo.style.display = 'block';
                        const label = task.roller_point_label || '';
                        const point = task.roller_point || '';
                        rollerPointDisplay.textContent = label ? `${label}（${point}）` : (point || '未配置');
                        // 加载已下发任务缓存并显示
                        rollerSentOrders.style.display = 'block';
                        checkAndCleanRollerOrders(area, taskName).then(active => {
                            renderRollerSentOrders(active, task.capacity || 0);
                        });
                        startRollerRefreshTimer();
                        submitBtn.disabled = false;
                    } else {
                        rollerTaskInfo.style.display = 'none';
                        rollerSentOrders.style.display = 'none';
                        stopRollerRefreshTimer();
                        
                        if (task.requires_shelf) {
                            shelfGroup.style.display = 'block';
                            validateShelfLock();
                        } else {
                            shelfGroup.style.display = 'none';
                            submitBtn.disabled = false;
                        }
                        
                        if (task.requires_task_path) {
                            taskPathGroup.style.display = 'block';
                            taskPathSelect.innerHTML = '<option value="">请选择任务路径</option>';
                            task.task_path_options.forEach(option => {
                                const opt = document.createElement('option');
                                let value, baseText;
                                if (typeof option === 'object') {
                                    value = option.value;
                                    baseText = option.label ? `${option.label} (${option.value})` : option.value;
                                } else {
                                    value = option;
                                    baseText = option;
                                }
                                opt.value = value;
                                opt.textContent = baseText;
                                opt.dataset.baseText = baseText;
                                taskPathSelect.appendChild(opt);
                            });
                            if (task.capacity > 0) loadPathCapacity(task.code, task.capacity);
                        } else {
                            taskPathGroup.style.display = 'none';
                        }
                    }
                } else {
                    shelfGroup.style.display = 'none';
                    taskPathGroup.style.display = 'none';
                    rollerTaskInfo.style.display = 'none';
                    rollerSentOrders.style.display = 'none';
                    stopRollerRefreshTimer();
                    submitBtn.disabled = false;
                }
                // 切换任务时加载设备建议
                if (area && taskName && config.areas[area]?.tasks[taskName]) {
                    const task = config.areas[area].tasks[taskName];
                    loadDeviceSuggestions();
                }
            }

            async function loadDeviceSuggestions() {
                if (!deviceInput || !deviceDropdownMenu) return;
                try {
                    const res = await fetch('/addtask/device/suggest');
                    const data = await res.json();
                    currentDeviceSuggestions = data.devices || [];
                    _renderDeviceDropdown();
                } catch { currentDeviceSuggestions = []; _renderDeviceDropdown(); }
            }

            function _renderDeviceDropdown(filter) {
                if (!deviceDropdownMenu) return;
                let list = currentDeviceSuggestions;
                const q = (filter || '').trim().toLowerCase();
                if (q) {
                    list = list.filter(d =>
                        d.deviceNum.toLowerCase().includes(q) ||
                        d.deviceCode.toLowerCase().includes(q)
                    );
                } else {
                    list = list.slice(0, 50); // 未筛选时显示前50条
                }
                if (list.length === 0) {
                    deviceDropdownMenu.innerHTML = `<li><span class="dropdown-item-text text-muted small">${q ? '无匹配设备' : '无设备数据'}</span></li>`;
                } else {
                    const usage = getTodayDeviceUsage();
                    // 按今日使用次数降序，同次数字母序
                    list.sort((a, b) => {
                        const ca = usage[a.deviceCode] || 0;
                        const cb = usage[b.deviceCode] || 0;
                        if (cb !== ca) return cb - ca;
                        return a.deviceNum.localeCompare(b.deviceNum, 'zh-Hans-CN');
                    });
                    deviceDropdownMenu.innerHTML = list.map(d => {
                        const cnt = usage[d.deviceCode] || 0;
                        const suffix = cnt > 0 ? ` <small class="text-primary">(今日${cnt}次)</small>` : '';
                        return `<li><a class="dropdown-item" href="#" data-devicecode="${d.deviceCode}" data-devicenum="${d.deviceNum}">
                            <strong>${d.deviceNum}</strong> <small class="text-muted">— ${d.deviceCode}</small>${suffix}
                        </a></li>`;
                    }).join('');
                }
            }

            // 点击下拉项目：填入设备编号
            deviceDropdownMenu.addEventListener('click', (e) => {
                const item = e.target.closest('.dropdown-item');
                if (item) {
                    deviceInput.value = item.dataset.devicenum;
                    deviceClearBtn.style.display = 'inline-block';
                    _updateDropdownVisibility(false);
                }
            });

            // 输入框获得焦点：打开下拉（如果有数据）
            deviceInput.addEventListener('focus', () => {
                if (currentDeviceSuggestions.length > 0) _updateDropdownVisibility(true);
            });

            // 输入时：过滤列表 + 打开下拉 + 显示/隐藏清除按钮
            deviceInput.addEventListener('input', () => {
                const v = deviceInput.value;
                deviceClearBtn.style.display = v ? 'inline-block' : 'none';
                _renderDeviceDropdown(v);
                if (currentDeviceSuggestions.length > 0) _updateDropdownVisibility(true);
            });

            // 失焦时关闭下拉（延迟让下拉项点击事件先触发）
            deviceInput.addEventListener('blur', () => {
                setTimeout(() => {
                    if (!deviceDropdownMenu.contains(document.activeElement)) {
                        _updateDropdownVisibility(false);
                    }
                }, 150);
            });

            // 清除按钮
            deviceClearBtn.addEventListener('click', () => {
                deviceInput.value = '';
                deviceClearBtn.style.display = 'none';
                _renderDeviceDropdown();
            });

            function _updateDropdownVisibility(show) {
                if (!deviceDropdownMenu) return;
                const isShown = deviceDropdownMenu.classList.contains('show');
                if (show === isShown) return;
                deviceDropdownMenu.classList.toggle('show', show);
            }

            async function loadPathCapacity(modelProcessCode, capacity) {
                const now = Date.now();
                if (lastCapacityLoadByCode[modelProcessCode] && now - lastCapacityLoadByCode[modelProcessCode] < 3000) return;
                lastCapacityLoadByCode[modelProcessCode] = now;
                try {
                    const statusList = [4, 6, 9, -1];
                    const countMap = new Map();
                    for (const status of statusList) {
                        const res = await fetch('http://10.68.2.32:8315/crossTask/query', {
                            method: 'POST', headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({modelProcessCode, taskStatus: status.toString(), pageSize: 100, pageNo: 1})
                        });
                        const data = await res.json();
                        if (data.code === 1000 && data.data.list) {
                            data.data.list.forEach(t => { if (t.taskPath) countMap.set(t.taskPath, (countMap.get(t.taskPath)||0)+1); });
                        }
                    }
                    Array.from(taskPathSelect.options).forEach(opt => {
                        if (opt.value && opt.dataset.baseText) {
                            const cnt = countMap.get(opt.value) || 0;
                            opt.textContent = `${opt.dataset.baseText} [${cnt}/${capacity}]`;
                            opt.disabled = cnt >= capacity;
                        }
                    });
                } catch (e) { console.error('容量加载失败', e); }
            }

            async function isPathCapacityFull(code, path, cap) {
                if (!cap) return false;
                try {
                    let total = 0;
                    for (const st of [4,6,9,-1]) {
                        const res = await fetch('http://10.68.2.32:8315/crossTask/query', {
                            method: 'POST', headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({modelProcessCode: code, taskStatus: st.toString(), pageSize: 100, pageNo: 1})
                        });
                        const d = await res.json();
                        if (d.code===1000 && d.data.list) total += d.data.list.filter(t=>t.taskPath===path).length;
                    }
                    return total >= cap;
                } catch { return false; }
            }

            async function checkShelfTaskStatus(shelf) {
                for (const st of [4,6,9,-1]) {
                    try {
                        const res = await fetch('http://10.68.2.32:8315/crossTask/query', {
                            method: 'POST', headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({taskStatus: st.toString(), shelfNum: shelf, pageSize: 20, pageNo: 1})
                        });
                        const d = await res.json();
                        if (d.code===1000 && d.data.list?.length>0) {
                            const text = {4:'正在发送',6:'执行中',9:'已下发','-1':'容量管控'}[st]||`状态${st}`;
                            return {exists: true, status: text};
                        }
                    } catch {}
                }
                return {exists: false};
            }

            async function submitTask() {
                const area = areaSelect.value, taskName = taskSelect.value;
                if (!area || !taskName) return alert('请完整选择区域和任务');
                const task = config.areas[area].tasks[taskName];
                const isRoller = _enableRollerTask && task.roller_task === true;
                let shelf = shelfInput.value.trim();
                
                // 辊筒任务跳过货架校验
                if (isRoller) {
                    // 容量管控：已下发未完成数 >= capacity 时禁止下发
                    if (task.capacity > 0) {
                        const active = await checkAndCleanRollerOrders(area, taskName);
                        if (active.length >= task.capacity) {
                            capacityModalMessage.textContent =
                                `该辊筒任务已达到容量上限 (${active.length}/${task.capacity})，` +
                                `请等待已有任务完成后（状态变为已完成）再下发。`;
                            capacityModal.show();
                            return;
                        }
                    }
                } else {
                    if (task.requires_shelf && !shelf) { shelfError.style.display='block'; return; }
                    if (task.requires_task_path && (!taskPathSelect.value || taskPathSelect.value==='请选择任务路径')) {
                        taskPathError.style.display='block'; return;
                    }
                    if (task.requires_shelf && shelfHistory[shelf] && Date.now()-shelfHistory[shelf]<300000) {
                        shelfLock.style.display='block'; return;
                    }
                }
                
                if (!isRoller && task.requires_shelf) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>检查中...';
                    const check = await checkShelfTaskStatus(shelf);
                    if (check.exists) {
                        if (taskExistsMessage) {
                            taskExistsMessage.textContent = `当前货架 ${shelf} 有任务正在${check.status}，请勿重复下发！`;
                        }
                        taskExistsModal.show();
                        if (shelfQueryInput) shelfQueryInput.value = shelf;
                        const shelfTab = document.querySelector('[data-type="shelf"]');
                        const orderTab = document.querySelector('[data-type="order"]');
                        if (shelfTab) shelfTab.classList.add('active');
                        if (orderTab) orderTab.classList.remove('active');
                        if (shelfQueryGroup) shelfQueryGroup.style.display='block';
                        if (orderQueryGroup) orderQueryGroup.style.display='none';
                        setTimeout(queryTasks, 200);
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = '<i class="bi bi-send me-2"></i>下发任务';
                        return;
                    }
                    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>下发中...';
                }
                
                if (!isRoller && task.requires_task_path && task.capacity>0) {
                    if (await isPathCapacityFull(task.code, taskPathSelect.value, task.capacity)) {
                        capacityModalMessage.textContent = `点位 ${taskPathSelect.value} 容量已满 (${task.capacity}/${task.capacity})`;
                        capacityModal.show();
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = '<i class="bi bi-send me-2"></i>下发任务';
                        return;
                    }
                }
                
                const generateOrderId = () => {
                    const now = new Date();
                    // 格式: CEM_YYYY-MM-DD HH:MM:SS.毫秒__随机数（跨环境）
                    // 格式: RLLR_YYYY-MM-DD HH:MM:SS.毫秒__随机数（辊筒）
                    const prefix = isRoller ? 'RLLR' : 'CEM';
                    const dateStr = now.toLocaleString('sv-SE', {timeZone:'Asia/Shanghai'}).replace('T',' ');
                    const ms = now.getMilliseconds().toString().padStart(3, '0');
                    const random = Math.floor(Math.random() * 10000).toString().padStart(4, '0');
                    return `${prefix}_${dateStr}.${ms}__${random}`;
                };
                const orderId = generateOrderId();
                const taskPathVal = isRoller
                    ? (task.roller_point || "")
                    : (task.requires_task_path ? taskPathSelect.value : "");
                const requestData = [{
                    modelProcessCode: task.code, priority: 6, orderId, fromSystem: "CEM",
                    taskOrderDetail: { taskPath: taskPathVal, shelfNumber: task.requires_shelf ? shelf : "" }
                }];
                // 处理指定设备
                const deviceVal = deviceInput ? deviceInput.value.trim() : '';
                if (deviceVal) {
                    // 从 agv_robot_ext 数据中解析 deviceNum → deviceCode
                    const match = currentDeviceSuggestions.find(d => d.deviceNum === deviceVal || d.deviceCode === deviceVal);
                    if (match) {
                        requestData[0].taskOrderDetail.deviceCode = match.deviceCode;
                    } else if (deviceVal.length > 10) {
                        requestData[0].taskOrderDetail.deviceCode = deviceVal;
                    } else {
                        showAlert(`设备 "${deviceVal}" 未找到，请从下拉列表选择或输入完整设备序列号`, 'warning');
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = '<i class="bi bi-send me-2"></i>下发任务';
                        return;
                    }
                    // 指定设备下发前确认
                    const displayName = match ? match.deviceNum : deviceVal;
                    if (!confirm(`⚠️  指定了设备：${displayName}` + 
                        `\n\n该任务将仅由该设备执行，确认继续下发？`)) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = '<i class="bi bi-send me-2"></i>下发任务';
                        return;
                    }
                }
                debugInfo.textContent = JSON.stringify(requestData, null, 2);
                
                try {
                    const res = await fetch(task.base_url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(requestData)});
                    const data = await res.json();
                    responseBox.style.display = 'block';
                    responseBox.innerHTML = `<div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="fw-semibold text-success"><i class="bi bi-check-circle me-1"></i>响应数据</span>
                        <button class="btn btn-sm btn-outline-secondary py-0" id="copy-response-btn" title="复制响应数据"><i class="bi bi-clipboard me-1"></i>复制</button>
                    </div>
                    <pre id="response-json" class="response-json mb-0">${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
                    noResponsePlaceholder.style.display = 'none';
                    if (data.code === 1000) {
                        successModal.show();
                        if (isRoller) {
                            addRollerSentOrder(area, taskName, orderId, task.roller_point || '');
                            refreshRollerSentOrders();
                        }
                        if (task.requires_shelf) shelfHistory[shelf] = Date.now();
                        orderQueryInput.value = orderId;
                        // 统一切换到 OrderId 查询（关闭其他模式）
                        document.querySelectorAll('.toggle-option').forEach(o => o.classList.remove('active'));
                        document.querySelector('[data-type="order"]').classList.add('active');
                        shelfQueryGroup.style.display='none'; orderQueryGroup.style.display='block'; deviceQueryGroup.style.display='none';
                        // 等待1.5秒让ICS处理完成后自动搜索
                        autoQueryAfterSubmit(orderId);
                        if (task.requires_task_path && task.capacity>0) setTimeout(()=>loadPathCapacity(task.code, task.capacity), 500);
                        // 记录最近使用任务
                        recordTaskUsage(taskName, area);
                        // 记录每日区域使用次数
                        recordAreaUsage(area);
                        // 记录每日任务使用次数
                        recordTaskUsageCount(area, taskName);
                        // 记录每日设备使用次数
                        const sentDeviceCode = requestData[0].taskOrderDetail.deviceCode;
                        if (sentDeviceCode) recordDeviceUsage(sentDeviceCode);
                        // 刷新下拉框计数文本（不重建DOM，保留已选项）
                        refreshCountDisplay();
                    }
                } catch (e) {
                    responseBox.style.display = 'block';
                    responseBox.innerHTML = `<div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="fw-semibold text-danger"><i class="bi bi-exclamation-triangle me-1"></i>请求失败</span>
                    </div>
                    <pre class="response-json mb-0 text-danger">${escapeHtml(e.message)}</pre>`;
                    noResponsePlaceholder.style.display = 'none';
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="bi bi-send me-2"></i>下发任务';
                }
            }

            function toggleQueryType(e) {
                const type = e.target.dataset.type;
                queryToggleOptions.forEach(o=>o.classList.remove('active'));
                e.target.classList.add('active');
                shelfQueryGroup.style.display = type==='shelf'?'block':'none';
                orderQueryGroup.style.display = type==='order'?'block':'none';
                deviceQueryGroup.style.display = type==='device'?'block':'none';
            }

            let _pendingAutoSearch = null;
            let queryLastClickTime = 0;

            function autoQueryAfterSubmit(orderId) {
                if (_pendingAutoSearch) clearTimeout(_pendingAutoSearch);
                _pendingAutoSearch = setTimeout(() => {
                    _pendingAutoSearch = null;
                    // 执行前再检查：用户没有切换模式或修改输入
                    const currentVal = orderQueryInput.value.trim();
                    const isOrderActive = document.querySelector('[data-type="order"]')?.classList.contains('active');
                    if (!isOrderActive || currentVal !== orderId) return;
                    queryTasks(true);
                }, 1500);
            }

            async function queryTasks(force) {
                if (Date.now() - queryLastClickTime < 2000 && !force) return;
                queryLastClickTime = Date.now();
                const activeType = document.querySelector('.toggle-option.active')?.dataset.type || 'shelf';
                const shelf = shelfQueryInput.value.trim(), orderId = orderQueryInput.value.trim(), deviceNum = deviceQueryInput.value.trim();
                if (activeType === 'shelf' && !shelf) return alert('请输入货架号');
                if (activeType === 'order' && !orderId) return alert('请输入OrderId');
                if (activeType === 'device' && !deviceNum) return alert('请输入设备号');
                queryBtn.disabled = true;
                queryBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>查询中...';
                try {
                    const body = {};
                    if (activeType === 'shelf') body.shelfNum = shelf;
                    else if (activeType === 'order') body.orderId = orderId;
                    else body.deviceNum = deviceNum;
                    
                    const res = await fetch('/addtask/query', {
                        method:'POST', headers:{'Content-Type':'application/json'},
                        body: JSON.stringify(body)
                    });
                    const data = await res.json();
                    
                    if (!data.success || !data.mainTask) { 
                        emptyState.style.display='block'; 
                        taskDetails.innerHTML = ''; 
                        renderQueryHistory();
                        return; 
                    }
                    // 保存查询历史
                    saveQueryHistory({ type: activeType, value: activeType === 'shelf' ? shelf : activeType === 'order' ? orderId : deviceNum });
                    renderQueryHistory();
                    displayTaskDetails(data.mainTask, data.subs || [], data.detail_error);
                } catch (e) { 
                    alert('查询失败: ' + e.message); 
                } finally {
                    queryBtn.disabled = false;
                    queryBtn.innerHTML = '<i class="bi bi-search me-2"></i>查询任务';
                }
            }

            function getStatusText(st) {
                const map = {8:'已完成',6:'执行中',4:'正在发送',9:'已下发','-1':'容量管控'};
                return map[st] || `状态${st}`;
            }

            function renderQueryHistory() {
                if (!queryHistoryContainer) return;
                const history = getQueryHistory();
                if (!history.length) { queryHistoryContainer.innerHTML = ''; return; }
                queryHistoryContainer.innerHTML = `<div class="d-flex flex-wrap gap-1 align-items-center"><span class="small text-muted me-1"><i class="bi bi-clock-history me-1"></i>最近查询:</span>` +
                    history.map(h => {
                        const label = h.type === 'shelf' ? `📦 ${h.value}` : h.type === 'device' ? `🔧 ${h.value}` : `📋 ${h.value}`;
                        return `<span class="badge bg-secondary" style="cursor:pointer" onclick="quickQuery('${h.type}','${h.value.replace(/'/g, "\\'")}')"><i class="bi bi-arrow-repeat me-1"></i>${label}</span>`;
                    }).join('') + `</div>`;
            }

            window.quickQuery = function(type, value) {
                if (type === 'shelf') {
                    document.querySelector('[data-type="shelf"]').click();
                    shelfQueryInput.value = value;
                } else if (type === 'order') {
                    document.querySelector('[data-type="order"]').click();
                    orderQueryInput.value = value;
                } else if (type === 'device') {
                    document.querySelector('[data-type="device"]').click();
                    deviceQueryInput.value = value;
                }
                queryTasks();
            };

            function displayTaskDetails(main, subs, detailError) {
                emptyState.style.display = 'none';
                let html = '';
                
                if (main.isRoller) {
                    // ======== 辊筒任务专属卡片（非跨环境） ========
                    const statusLabel = getStatusText(main.taskStatus);
                    const timeStr = main.createTime ? new Date(main.createTime).toLocaleString() : '--';
                    const rollerTimeStr = main.rollerTime ? new Date(main.rollerTime).toLocaleString() : '--';
                    html += `<div class="task-item">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h5 class="mb-0 d-flex align-items-center gap-2">
                                <span class="badge bg-secondary" style="font-size:0.65rem;">辊筒</span>
                                辊筒任务
                            </h5>
                            <span class="task-status status-${main.taskStatus}">${statusLabel}</span>
                        </div>
                        <div class="small">
                            <span class="fw-semibold">OrderId:</span> ${main.orderId}
                            <i class="bi bi-clipboard copy-icon ms-1" data-copy="${(main.orderId||'').replace(/"/g, '&quot;').replace(/</g, '&lt;')}" data-msg="OrderId 已复制" title="复制OrderId"></i>
                        </div>
                        <div class="small">
                            <span class="fw-semibold">下发点位:</span>
                            ${main.qrContent ? `<code class="px-2 py-1 rounded" style="background:var(--detail-card-bg);border:1px solid var(--border-color);font-size:0.85rem;">${main.qrContent}</code>` : '--'}
                        </div>
                        <div class="small"><span class="fw-semibold">设备编号:</span> ${main.deviceNum||'无'}</div>
                        <div class="small"><span class="fw-semibold">任务状态:</span> ${statusLabel} (${main.taskStatus})</div>
                        <div class="small"><span class="fw-semibold">创建时间:</span> ${timeStr}</div>
                        <div class="small"><span class="fw-semibold">最近更新:</span> ${rollerTimeStr}</div>
                        <div class="mt-3 d-flex flex-wrap gap-2">
                            <button class="btn btn-sm btn-outline-info" onclick="showTaskJsonModal(${JSON.stringify(main).replace(/"/g, '&quot;').replace(/'/g, "&#39;")}, ${JSON.stringify(subs).replace(/"/g, '&quot;').replace(/'/g, "&#39;")})">
                                <i class="bi bi-code-slash me-1"></i>查看JSON数据
                            </button>
                        </div>
                    </div>`;
                    // 辊筒任务无子任务，不需要后续渲染
                    taskDetails.innerHTML = html;
                    return;
                }
                
                // ======== 跨环境任务卡片（原逻辑） ========
                const encodedOrderId = encodeURIComponent(main.orderId);
                html += `<div class="task-item"><div class="d-flex justify-content-between align-items-center mb-2"><h5 class="mb-0">主任务</h5><span class="task-status status-${main.taskStatus}">${getStatusText(main.taskStatus)}</span></div>
                    <div class="small"><span class="fw-semibold">OrderId:</span> ${main.orderId} <i class="bi bi-clipboard copy-icon ms-1" data-copy="${(main.orderId||'').replace(/"/g, '&quot;').replace(/</g, '&lt;')}" data-msg="OrderId 已复制" title="复制OrderId"></i></div>
                    <div class="small"><span class="fw-semibold">任务名称:</span> ${main.modelProcessName}</div>
                    <div class="small"><span class="fw-semibold">任务模板:</span> <a href="/search?search_term=${encodeURIComponent(main.modelProcessCode||'')}" target="_blank" class="text-decoration-none" title="查看模板详情">${main.modelProcessCode} <i class="bi bi-box-arrow-up-right" style="font-size:0.7rem;"></i></a></div>
                    <div class="small"><span class="fw-semibold">货架号:</span> ${main.shelfNum||'无'} ${main.shelfNum ? `<i class="bi bi-clipboard copy-icon ms-1" data-copy="${main.shelfNum.replace(/"/g, '&quot;').replace(/</g, '&lt;')}" data-msg="货架号已复制" title="复制货架号"></i>` : ''}</div>
                    <div class="small"><span class="fw-semibold">设备编号:</span> ${main.deviceNum||'无'}</div>
                    <div class="small"><span class="fw-semibold">任务状态:</span> ${getStatusText(main.taskStatus)} (${main.taskStatus})</div>
                    <div class="small"><span class="fw-semibold">创建时间:</span> ${new Date(main.createTime).toLocaleString()}</div>
                    <div class="mt-3 d-flex flex-wrap gap-2">
                        <a href="/query?orderId=${encodedOrderId}" target="_blank" class="btn btn-sm btn-outline-primary">
                            <i class="bi bi-box-arrow-up-right me-1"></i>查看完整详情
                        </a>
                        <button class="btn btn-sm btn-outline-info" onclick="showTaskJsonModal(${JSON.stringify(main).replace(/"/g, '&quot;').replace(/'/g, "&#39;")}, ${JSON.stringify(subs).replace(/"/g, '&quot;').replace(/'/g, "&#39;")})">
                            <i class="bi bi-code-slash me-1"></i>查看JSON数据
                        </button>
                    </div></div>`;
                
                if (subs && subs.length > 0) {
                    subs.sort((a,b)=>a.taskSeq-b.taskSeq);
                    html += `<h6 class="mt-3 mb-2">子任务列表</h6>`;
                    subs.forEach((t,idx)=>{
                        const canPriority = [4,9].includes(t.status);
                        html += `<div class="task-item ${idx===0?'border-primary':''}"><div class="d-flex justify-content-between"><strong>子任务 ${t.taskSeq}</strong><span class="task-status status-${t.status}">${getStatusText(t.status)}</span></div>
                            <div class="small mt-2"><span class="fw-semibold">模板:</span> ${t.templateName}</div>
                            <div class="small"><span class="fw-semibold">子任务ID:</span> ${t.subOrderId} <i class="bi bi-clipboard copy-icon ms-1" data-copy="${(t.subOrderId||'').replace(/"/g, '&quot;').replace(/</g, '&lt;')}" data-msg="子任务ID已复制" title="复制子任务ID"></i></div>
                            <div class="small"><span class="fw-semibold">服务地址:</span> ${t.serviceUrl}</div>
                            <div class="small"><span class="fw-semibold">任务路径:</span> ${t.taskPath||'无'}</div>
                            ${idx===0 ? `<button class="btn btn-sm ${canPriority?'btn-warning':'btn-secondary'} mt-2" onclick="updateTaskPriority('${t.subOrderId}','${t.serviceUrl}',${t.status})" ${!canPriority?'disabled':''}><i class="bi bi-star-fill me-1"></i>优先执行</button>`:''}
                        </div>`;
                    });
                } else {
                    html += `<div class="mt-3 text-muted small"><i class="bi bi-info-circle me-1"></i>暂无子任务详情${detailError ? ` <span class="text-warning">(${escapeHtml(detailError)})</span>` : ''}</div>`;
                }
                taskDetails.innerHTML = html;
            }

            window.updateTaskPriority = async function(subOrderId, serviceUrl, status) {
                if (Date.now() - priorityLastClickTime < 2000) return;
                priorityLastClickTime = Date.now();
                if (![4,9].includes(status)) {
                    priorityModalTitle.textContent = '无法调整优先级';
                    priorityModalMessage.textContent = '只有正在发送或已下发的任务才能调整优先级';
                    priorityModal.show(); return;
                }
                try {
                    const url = new URL(serviceUrl);
                    const updateUrl = `${url.protocol}//${url.host}/ics/out/updateTaskPriority`;
                    const res = await fetch(updateUrl, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({orderId: subOrderId, score:"100000"})});
                    const data = await res.json();
                    priorityModalTitle.textContent = data.code===1000 ? '优先级调整成功' : '优先级调整失败';
                    priorityModalMessage.textContent = data.code===1000 ? '任务优先级已提高' : (data.desc||'未知错误');
                    priorityModal.show();
                } catch(e) {
                    priorityModalTitle.textContent = '错误';
                    priorityModalMessage.textContent = e.message;
                    priorityModal.show();
                }
            };

            // 密码验证相关函数
            function showPasswordModal() {
                const passwordModal = new bootstrap.Modal(document.getElementById('password-modal'));
                const passwordInput = document.getElementById('password-input');
                const passwordError = document.getElementById('password-error');
                
                // 重置表单
                passwordInput.value = '';
                passwordError.style.display = 'none';
                passwordError.textContent = '';
                
                // 显示模态框
                passwordModal.show();
                
                // 设置提交按钮事件
                document.getElementById('password-submit').onclick = function() {
                    const password = passwordInput.value.trim();
                    if (password === 'admin123456') {
                        passwordModal.hide();
                        // 打开配置管理页面
                        window.open('/config', '_blank');
                    } else {
                        passwordError.textContent = '密码错误，请重新输入';
                        passwordError.style.display = 'block';
                        passwordInput.focus();
                    }
                };
                
                // 回车键提交
                passwordInput.onkeypress = function(e) {
                    if (e.key === 'Enter') {
                        document.getElementById('password-submit').click();
                    }
                };
            }

            async function showHelpModal() {
                if (!helpModalBody.dataset.loaded) {
                    try {
                        const res = await fetch('/addtask/help');
                        const html = await res.text();
                        helpModalBody.innerHTML = html;
                        helpModalBody.dataset.loaded = true;
                        
                        // 添加交互功能：代码复制、标题锚点等
                        addMarkdownInteractiveFeatures();
                        
                        // 渲染 Mermaid 流程图
                        if (typeof window.renderMermaidDiagrams === 'function') {
                            window.renderMermaidDiagrams('#help-modal-body');
                        }
                    } catch(e) { 
                        helpModalBody.innerHTML = `<p class="text-danger">加载失败: ${e.message}</p>`;
                    }
                }
                helpModal.show();
                // 模态框显示后重新渲染，确保尺寸正确
                setTimeout(function() {
                    if (typeof window.renderMermaidDiagrams === 'function') {
                        window.renderMermaidDiagrams('#help-modal-body');
                    }
                }, 300);
            }

            // 添加Markdown交互功能
            function addMarkdownInteractiveFeatures() {
                // 为所有标题添加锚点
                document.querySelectorAll('#help-modal-body h1, #help-modal-body h2, #help-modal-body h3, #help-modal-body h4, #help-modal-body h5, #help-modal-body h6').forEach(heading => {
                    const id = heading.textContent.toLowerCase().replace(/[^\w]+/g, '-');
                    heading.id = id;
                    
                    // 添加锚点链接
                    const anchor = document.createElement('a');
                    anchor.href = `#${id}`;
                    anchor.className = 'heading-anchor ms-2';
                    anchor.innerHTML = '<i class="bi bi-link-45deg"></i>';
                    anchor.style.opacity = '0.5';
                    anchor.style.textDecoration = 'none';
                    anchor.style.fontSize = '0.8em';
                    
                    heading.appendChild(anchor);
                    
                    // 鼠标悬停时显示锚点
                    heading.addEventListener('mouseenter', () => {
                        anchor.style.opacity = '1';
                    });
                    heading.addEventListener('mouseleave', () => {
                        anchor.style.opacity = '0.5';
                    });
                });
                
                // 复制代码块功能
                document.querySelectorAll('#help-modal-body pre').forEach(pre => {
                    const button = document.createElement('button');
                    button.className = 'btn btn-sm btn-outline-secondary position-absolute';
                    button.style.top = '8px';
                    button.style.right = '8px';
                    button.innerHTML = '<i class="bi bi-clipboard"></i>';
                    button.title = '复制代码';
                    
                    pre.style.position = 'relative';
                    pre.appendChild(button);
                    
                    button.addEventListener('click', () => {
                        const code = pre.querySelector('code')?.textContent || pre.textContent;
                        navigator.clipboard.writeText(code).then(() => {
                            button.innerHTML = '<i class="bi bi-check"></i>';
                            button.className = 'btn btn-sm btn-success position-absolute';
                            setTimeout(() => {
                                button.innerHTML = '<i class="bi bi-clipboard"></i>';
                                button.className = 'btn btn-sm btn-outline-secondary position-absolute';
                            }, 2000);
                        });
                    });
                });
                
                // 平滑滚动到锚点
                document.querySelectorAll('#help-modal-body a[href^="#"]').forEach(anchor => {
                    anchor.addEventListener('click', function (e) {
                        e.preventDefault();
                        const targetId = this.getAttribute('href').substring(1);
                        const targetElement = document.getElementById(targetId);
                        if (targetElement) {
                            targetElement.scrollIntoView({
                                behavior: 'smooth',
                                block: 'start'
                            });
                        }
                    });
                });
            }

            // 显示任务JSON数据
            window.showTaskJsonModal = function(mainTask, subTasks) {
                const jsonData = {
                    code: 1000,
                    desc: "success",
                    data: {
                        mainTask: mainTask,
                        subTasks: subTasks,
                        fullResponse: {
                            main: mainTask,
                            subs: subTasks
                        }
                    }
                };
                
                const jsonContent = document.getElementById('json-content');
                jsonContent.textContent = JSON.stringify(jsonData, null, 2);
                
                const jsonModal = new bootstrap.Modal(document.getElementById('json-modal'));
                jsonModal.show();
            };

            // 复制JSON到剪贴板
            window.copyJsonToClipboard = function() {
                const jsonContent = document.getElementById('json-content');
                const text = jsonContent.textContent;
                
                navigator.clipboard.writeText(text).then(() => {
                    const originalText = jsonContent.textContent;
                    jsonContent.textContent = '✅ JSON已复制到剪贴板！\n\n' + originalText;
                    setTimeout(() => {
                        jsonContent.textContent = originalText;
                    }, 2000);
                }).catch(err => {
                    console.error('复制失败:', err);
                    alert('复制失败，请手动选择并复制文本');
                });
            };

            // ── 高级选项折叠/展开 ──
            window.toggleAdvancedOptions = function() {
                const opts = document.getElementById('advanced-options');
                const chevron = document.getElementById('advanced-chevron');
                if (!opts) return;
                if (opts.style.display === 'none' || !opts.style.display) {
                    opts.style.display = 'block';
                    if (chevron) chevron.className = 'bi bi-chevron-up ms-1 small';
                } else {
                    opts.style.display = 'none';
                    if (chevron) chevron.className = 'bi bi-chevron-down ms-1 small';
                }
            };

            // 监听设备输入变化，更新高级选项徽标
            const _deviceInput = document.getElementById('device-input');
            if (_deviceInput) {
                _deviceInput.addEventListener('input', () => {
                    const badge = document.getElementById('advanced-badge');
                    if (!badge) return;
                    if (_deviceInput.value.trim()) {
                        badge.style.display = 'inline';
                        badge.textContent = '已设: ' + _deviceInput.value.trim();
                    } else {
                        badge.style.display = 'none';
                    }
                });
                // 处理设备清空按钮
                const clearBtn = document.getElementById('device-clear-btn');
                if (clearBtn) {
                    const observer = new MutationObserver(() => {
                        const badge = document.getElementById('advanced-badge');
                        if (badge && !_deviceInput.value.trim()) badge.style.display = 'none';
                    });
                    clearBtn.addEventListener('click', () => {
                        setTimeout(() => {
                            const badge = document.getElementById('advanced-badge');
                            if (badge) badge.style.display = 'none';
                        }, 50);
                    });
                }
            }

            document.addEventListener('DOMContentLoaded', initPage);
        })();
