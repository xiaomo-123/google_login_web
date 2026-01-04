/**
 * 任务日志查看器 - 集成到任务管理页面
 */
const TaskLogViewer = {
    // WebSocket连接
    ws: null,
    // 当前任务ID
    currentTaskId: null,
    // 是否正在查看历史日志
    isViewingHistory: false,
    // 日志容器
    container: null,
    // 重连尝试次数
    reconnectAttempts: 0,
    // 最大重连次数
    maxReconnectAttempts: 10,
    // 重连延迟（毫秒）
    reconnectDelay: 3000,
    // 重连定时器
    reconnectTimer: null,
    // 心跳定时器
    heartbeatTimer: null,
    // 日志数量限制
    maxLogs: 1000,

    /**
     * 初始化日志查看器
     */
    init() {
        this.container = document.getElementById('logContainer');
    },

    /**
     * 切换任务
     * @param {string} taskId - 任务ID
     */
    switchTask(taskId) {
        // 断开当前连接
        this.disconnect();

        // 更新当前任务ID
        this.currentTaskId = taskId ? parseInt(taskId) : null;

        if (!this.currentTaskId) {
            // 清空容器显示提示
            if (this.container) {
                this.container.innerHTML = `
                    <div class="log-content" style="color: #858585; padding: 20px; text-align: center;">
                        请选择任务以查看实时日志
                    </div>
                `;
            }
            return;
        }

        // 初始化容器
        this.initContainer();

        // 连接WebSocket
        this.connect();
    },

    /**
     * 初始化日志容器
     */
    initContainer() {
        if (!this.container) return;

        // 清空容器
        this.container.innerHTML = '';

        // 添加日志头部
        const header = document.createElement('div');
        header.className = 'log-header';
        header.innerHTML = `
            <div class="log-title">任务日志 #${this.currentTaskId}</div>
        `;
        this.container.appendChild(header);

        // 添加日志内容区域
        const content = document.createElement('div');
        content.className = 'log-content';
        content.id = 'log-content';
        this.container.appendChild(content);

        // 添加状态栏
        const status = document.createElement('div');
        status.className = 'log-status';
        status.id = 'log-status';
        status.innerHTML = '<span class="status-indicator connecting"></span> 正在连接...';
        this.container.appendChild(status);

        // 监听滚动事件
        content.addEventListener('scroll', () => {
            const { scrollTop, scrollHeight, clientHeight } = content;
            this.isViewingHistory = (scrollHeight - scrollTop - clientHeight) > 100;
        });
    },

    /**
     * 连接WebSocket
     */
    connect() {
        try {
            // 构建WebSocket URL
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/ws/logs/${this.currentTaskId}`;

            // 创建WebSocket连接
            this.ws = new WebSocket(wsUrl);

            // 连接打开事件
            this.ws.onopen = () => {
                this.updateStatus('connected');
                this.reconnectAttempts = 0;

                // 启动心跳
                this.startHeartbeat();
            };

            // 接收消息事件
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (e) {
                    console.error('解析消息失败:', e);
                }
            };

            // 连接关闭事件
            this.ws.onclose = () => {
                this.updateStatus('disconnected');
                this.stopHeartbeat();

                // 尝试重连
                this.scheduleReconnect();
            };

            // 连接错误事件
            this.ws.onerror = (error) => {
                console.error('WebSocket错误:', error);
                this.updateStatus('error');
            };

        } catch (e) {
            console.error('创建WebSocket连接失败:', e);
            this.updateStatus('error');
            this.scheduleReconnect();
        }
    },

    /**
     * 处理接收到的消息
     * @param {Object} data - 消息数据
     */
    handleMessage(data) {
        const { type, level, message, extra } = data;

        if (type === 'connected') {
            this.appendLog('info', message);
            return;
        }

        if (type === 'log') {
            this.appendLog(level, message, extra);
        }
    },

    /**
     * 添加日志到容器
     * @param {string} level - 日志级别
     * @param {string} message - 日志消息
     * @param {Object} extra - 额外信息
     */
    appendLog(level, message, extra = {}) {
        const logContent = document.getElementById('log-content');
        if (!logContent) return;

        // 创建日志条目
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${level}`;

        // 格式化时间
        const time = new Date().toLocaleTimeString();

        // 构建日志内容
        let logHtml = `
            <div class="log-time">${time}</div>
            <div class="log-level">${this.getLevelLabel(level)}</div>
            <div class="log-message">${this.escapeHtml(message)}</div>
        `;

        // 添加额外信息
        if (Object.keys(extra).length > 0) {
            logHtml += `<div class="log-extra">${this.escapeHtml(JSON.stringify(extra))}</div>`;
        }

        logEntry.innerHTML = logHtml;
        logContent.appendChild(logEntry);

        // 限制日志数量
        const logs = logContent.querySelectorAll('.log-entry');
        if (logs.length > this.maxLogs) {
            logContent.removeChild(logs[0]);
        }

        // 智能滚动：只有用户不在查看历史日志时才自动滚动
        if (!this.isViewingHistory) {
            logContent.scrollTop = logContent.scrollHeight;
        }
    },

    /**
     * 获取日志级别标签
     * @param {string} level - 日志级别
     * @returns {string} 级别标签
     */
    getLevelLabel(level) {
        const labels = {
            'info': 'INFO',
            'warning': 'WARN',
            'error': 'ERROR',
            'debug': 'DEBUG'
        };
        return labels[level] || level.toUpperCase();
    },

    /**
     * 更新连接状态
     * @param {string} status - 状态 (connected, disconnected, connecting, error)
     */
    updateStatus(status) {
        const statusElement = document.getElementById('log-status');
        if (!statusElement) return;

        const statusTexts = {
            'connected': '<span class="status-indicator connected"></span> 已连接',
            'disconnected': '<span class="status-indicator disconnected"></span> 已断开',
            'connecting': '<span class="status-indicator connecting"></span> 正在连接...',
            'error': '<span class="status-indicator error"></span> 连接错误'
        };

        statusElement.innerHTML = statusTexts[status] || statusTexts['disconnected'];
    },

    /**
     * 安排重连
     */
    scheduleReconnect() {
        // 清除现有定时器
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }

        // 检查是否超过最大重连次数
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('已达到最大重连次数，停止重连');
            this.updateStatus('error');
            return;
        }

        // 增加重连次数
        this.reconnectAttempts++;

        // 显示重连状态
        this.updateStatus('connecting');

        // 安排重连
        this.reconnectTimer = setTimeout(() => {
            console.log(`尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            this.connect();
        }, this.reconnectDelay);
    },

    /**
     * 启动心跳
     */
    startHeartbeat() {
        // 清除现有心跳
        this.stopHeartbeat();

        // 每30秒发送一次心跳
        this.heartbeatTimer = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send('ping');
            }
        }, 30000);
    },

    /**
     * 停止心跳
     */
    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    },

    /**
     * 清空日志
     */
    clearLogs() {
        const logContent = document.getElementById('log-content');
        if (logContent) {
            logContent.innerHTML = '';
        }
    },

    /**
     * 导出日志
     */
    exportLogs() {
        const logContent = document.getElementById('log-content');
        if (!logContent) return;

        const logs = logContent.querySelectorAll('.log-entry');
        let exportText = `任务日志 #${this.currentTaskId}\n`;
        exportText += `导出时间: ${new Date().toLocaleString()}\n`;
        exportText += `${'='.repeat(50)}\n\n`;

        logs.forEach(log => {
            const time = log.querySelector('.log-time').textContent;
            const level = log.querySelector('.log-level').textContent;
            const message = log.querySelector('.log-message').textContent;
            const extra = log.querySelector('.log-extra');

            exportText += `[${time}] [${level}] ${message}\n`;
            if (extra) {
                exportText += `  ${extra.textContent}\n`;
            }
        });

        // 创建下载链接
        const blob = new Blob([exportText], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `task_${this.currentTaskId}_logs_${new Date().getTime()}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    /**
     * 模拟日志
     */
    async simulateLogs() {
        if (!this.currentTaskId) {
            UI.showAlert('请先选择任务', 'error');
            return;
        }

        try {
            const response = await fetch(`/api/logs/simulate?task_id=${this.currentTaskId}&count=20`);
            const result = await response.json();

            if (result.success) {
                UI.showAlert(result.message, 'success');
            } else {
                UI.showAlert('模拟日志失败: ' + result.message, 'error');
            }
        } catch (error) {
            UI.showAlert('模拟日志失败: ' + error.message, 'error');
        }
    },

    /**
     * HTML转义
     * @param {string} text - 要转义的文本
     * @returns {string} 转义后的文本
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * 断开连接
     */
    disconnect() {
        // 清除重连定时器
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        // 停止心跳
        this.stopHeartbeat();

        // 关闭WebSocket
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    // 初始化日志查看器
    TaskLogViewer.init();

    // 延迟扩展TaskManager，确保TaskManager已定义
    setTimeout(() => {
        // 扩展TaskManager，在加载任务后更新任务选择下拉框
        const originalLoad = TaskManager.load;
        TaskManager.load = function() {
            originalLoad.call(this);
            TaskLogViewer.updateTaskSelect();
        };
    }, 100);

    // 监听任务列表更新，更新任务选择下拉框
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.target.id === 'tasksTable') {
                TaskLogViewer.updateTaskSelect();
            }
        });
    });

    // 开始观察任务表格变化
    const tasksTable = document.getElementById('tasksTable');
    if (tasksTable) {
        observer.observe(tasksTable, {
            childList: true,
            subtree: true
        });
    }
});

/**
 * 更新任务选择下拉框
 */
TaskLogViewer.updateTaskSelect = function() {
    const select = document.getElementById('taskLogSelect');
    if (!select) return;

    // 获取当前选中的值
    const currentValue = select.value;

    // 获取所有任务ID
    const taskRows = document.querySelectorAll('#tasksTable tbody tr');
    const taskIds = Array.from(taskRows).map(row => {
        const idCell = row.querySelector('td:nth-child(2)');
        return idCell ? idCell.textContent.trim() : null;
    }).filter(id => id);

    // 重建选项
    select.innerHTML = '<option value="">请选择任务</option>';
    taskIds.forEach(taskId => {
        const option = document.createElement('option');
        option.value = taskId;
        option.textContent = `任务 #${taskId}`;
        select.appendChild(option);
    });

    // 恢复选中值
    if (currentValue && taskIds.includes(currentValue)) {
        select.value = currentValue;
    }
};
