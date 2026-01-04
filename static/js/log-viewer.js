/**
 * 实时任务日志查看器
 * 使用原生WebSocket实现实时日志接收和渲染
 */
const LogViewer = {
    // WebSocket连接
    ws: null,
    // 任务ID
    taskId: null,
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
     * @param {number} taskId - 任务ID
     * @param {HTMLElement} container - 日志容器元素
     */
    init(taskId, container) {
        this.taskId = taskId;
        this.container = container;

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
            <div class="log-title">任务日志 #${this.taskId}</div>
            <div class="log-controls">
                <button class="btn btn-sm btn-secondary" onclick="LogViewer.clearLogs()">清空日志</button>
                <button class="btn btn-sm btn-secondary" onclick="LogViewer.exportLogs()">导出日志</button>
            </div>
        `;
        this.container.appendChild(header);

        // 添加日志内容区域
        const content = document.createElement('div');
        content.className = 'log-content';
        content.id = `log-content-${this.taskId}`;
        this.container.appendChild(content);

        // 添加状态栏
        const status = document.createElement('div');
        status.className = 'log-status';
        status.id = `log-status-${this.taskId}`;
        status.innerHTML = '<span class="status-indicator connecting"></span> 正在连接...';
        this.container.appendChild(status);

        // 监听滚动事件，检测用户是否在查看历史日志
        const logContent = document.getElementById(`log-content-${this.taskId}`);
        if (logContent) {
            logContent.addEventListener('scroll', () => {
                const { scrollTop, scrollHeight, clientHeight } = logContent;
                // 如果距离底部超过100像素，认为用户在查看历史日志
                this.isViewingHistory = (scrollHeight - scrollTop - clientHeight) > 100;
            });
        }
    },

    /**
     * 连接WebSocket
     */
    connect() {
        try {
            // 构建WebSocket URL
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/ws/logs/${this.taskId}`;

            // 创建WebSocket连接
            this.ws = new WebSocket(wsUrl);

            // 连接打开事件
            this.ws.onopen = () => {
                console.log('WebSocket连接已建立');
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
                console.log('WebSocket连接已关闭');
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
        const { type, level, message, timestamp, extra } = data;

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
        const logContent = document.getElementById(`log-content-${this.taskId}`);
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
        const statusElement = document.getElementById(`log-status-${this.taskId}`);
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
        const logContent = document.getElementById(`log-content-${this.taskId}`);
        if (logContent) {
            logContent.innerHTML = '';
        }
    },

    /**
     * 导出日志
     */
    exportLogs() {
        const logContent = document.getElementById(`log-content-${this.taskId}`);
        if (!logContent) return;

        const logs = logContent.querySelectorAll('.log-entry');
        let exportText = `任务日志 #${this.taskId}\n`;
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
        a.download = `task_${this.taskId}_logs_${new Date().getTime()}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
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
