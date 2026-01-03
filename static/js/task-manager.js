// 任务管理模块
const TaskManager = {
    load() {
        TaskAPI.list()
            .then(tasks => this.render(tasks))
            .catch(error => UI.showAlert('加载失败: ' + error.message, 'error'));
    },

    render(tasks) {
        const tbody = document.querySelector('#tasksTable tbody');
        if (!tbody) return;

        tbody.innerHTML = tasks.length === 0
            ? '<tr><td colspan="10" style="text-align: center; padding: 20px;">暂无数据</td></tr>'
            : tasks.map(task => `
                <tr>
                    <td><input type="checkbox" class="task-checkbox" value="${task.id}"></td>
                    <td>${task.id}</td>
                    <td>${this.escapeHtml(task.name)}</td>
                    <td>${task.account_type}</td>
                    <td>${task.auth_url_id}</td>
                    <td>${task.proxy_id || '-'}</td>
                    <td>${UI.getStatusBadge(task.status)}</td>
                    <td>${task.created_at}</td>
                    <td>${this.getButtons(task)}</td>
                </tr>
            `).join('');
    },

    getButtons(task) {
        const actionBtn = task.status === 'running'
            ? `<button class="btn btn-danger btn-sm" onclick="TaskManager.stop(${task.id})">停止</button>`
            : `<button class="btn btn-success btn-sm" onclick="TaskManager.start(${task.id})">启动</button>`;
        return `${actionBtn}
                <button class="btn btn-warning btn-sm" onclick="TaskManager.edit(${task.id})">编辑</button>
                <button class="btn btn-danger btn-sm" onclick="TaskManager.delete(${task.id})">删除</button>`;
    },

    // 显示添加任务模态框
    async showAddModal() {
        const authUrls = await AuthUrlAPI.list();
            const authUrlSelect = document.getElementById('authUrlSelect');
            if (authUrlSelect) {
                authUrlSelect.innerHTML = authUrls.map(url =>
                    `<option value="${url.id}">${this.escapeHtml(url.name)}</option>`
                ).join('');
            }

            // 加载代理列表
            const proxies = await ProxyAPI.list();
            const proxySelect = document.getElementById('proxySelect');
            if (proxySelect) {
                proxySelect.innerHTML = '<option value="">不使用代理</option>' + 
                    proxies.map(proxy =>
                        `<option value="${proxy.id}">${this.escapeHtml(proxy.url)} (${proxy.proxy_type}:${proxy.port})</option>`
                    ).join('');
            }

            // 重置表单
            const form = document.getElementById('addTaskForm');
            if (form) {
                form.reset();
                
                const taskTitle = document.getElementById('taskModalTitle');
                if (taskTitle) {
                    taskTitle.textContent = '创建任务';
                }
                
                const taskIdInput = document.getElementById('taskId');
                if (taskIdInput) {
                    taskIdInput.value = '';
                }
            }
            
        UI.showModal('addTaskModal');
    },

    // 显示编辑任务模态框
    async showEditModal(taskId) {
        try {
            const task = await TaskAPI.get(taskId);
            
            // 加载授权地址列表
            const authUrls = await AuthUrlAPI.list();
            const authUrlSelect = document.getElementById('authUrlSelect');
            if (authUrlSelect) {
                authUrlSelect.innerHTML = authUrls.map(url =>
                    `<option value="${url.id}" ${url.id === task.auth_url_id ? 'selected' : ''}>${this.escapeHtml(url.name)}</option>`
                ).join('');
            }

            // 加载代理列表
            const proxies = await ProxyAPI.list();
            const proxySelect = document.getElementById('proxySelect');
            if (proxySelect) {
                proxySelect.innerHTML = '<option value="">不使用代理</option>' + 
                    proxies.map(proxy =>
                        `<option value="${proxy.id}" ${proxy.id === task.proxy_id ? 'selected' : ''}>${this.escapeHtml(proxy.url)} (${proxy.proxy_type}:${proxy.port})</option>`
                    ).join('');
            }

            // 重置表单并设置值
            const form = document.getElementById('addTaskForm');
            form.reset();
                
                document.getElementById('taskModalTitle').textContent = '编辑任务';
                
                document.getElementById('taskId').value = task.id;
                
                form.name.value = task.name;
                document.querySelector('[name="account_type"]').value = task.account_type || 1;
                

                

                
                document.querySelector('[name="auth_url_id"]').value = task.auth_url_id;
                
                document.querySelector('[name="proxy_id"]').value = task.proxy_id || '';
            
        UI.showModal('addTaskModal');
        } catch (error) {
            console.error('加载任务信息失败:', error);
            UI.showAlert('加载任务信息失败: ' + error.message, 'error');
        }
    },

    async save(event) {
        event.preventDefault();

        // 防止重复提交
        if (this.isSubmitting) {
            UI.showAlert('正在提交中，请稍候...', 'error');
            return;
        }
        this.isSubmitting = true;

        const form = event.target;
        const taskIdElement = document.getElementById('taskId');
        const taskId = taskIdElement ? taskIdElement.value : null;
        
        // 构建任务数据
        const taskData = {
            name: form.name.value.trim(),
            account_type: parseInt(form.account_type.value) || 1,
            auth_url_id: parseInt(form.auth_url_id.value),
            proxy_id: null  // 默认为null，表示不使用代理
        };

        // 如果选择了代理，更新proxy_id
        const proxyId = form.proxy_id.value;
        if (proxyId && proxyId.trim() !== "") {
            taskData.proxy_id = parseInt(proxyId);
        }

        // 验证
        if (!taskData.name || !taskData.auth_url_id) {
            UI.showAlert('请填写任务名称和授权地址', 'error');
            this.isSubmitting = false;
            return;
        }

        try {
            if (taskId) {
                // 更新任务
                await TaskAPI.update(parseInt(taskId), taskData);
                UI.showAlert('任务更新成功', 'success');
            } else {
                // 创建任务
                await TaskAPI.create(taskData);
                UI.showAlert('任务创建成功', 'success');
            }

            UI.hideModal('addTaskModal');
            this.load();
        } catch (error) {
            console.error('保存任务失败:', error);
            UI.showAlert('保存任务失败: ' + error.message, 'error');
        } finally {
            this.isSubmitting = false;
        }
    },

    async start(taskId) {
        try {
            await TaskAPI.start(taskId);
            UI.showAlert('任务已启动', 'success');
            this.load();
        } catch (error) {
            console.error('启动任务失败:', error);
            UI.showAlert('启动任务失败: ' + error.message, 'error');
        }
    },

    async stop(taskId) {
        if (!confirm('确定停止?')) {
            return;
        }

        try {
            await TaskAPI.stop(taskId);
            UI.showAlert('任务已停止', 'success');
            this.load();
        } catch (error) {
            console.error('停止任务失败:', error);
            UI.showAlert('停止任务失败: ' + error.message, 'error');
        }
    },

    edit(id) {
        this.showEditModal(id);
    },

    async delete(taskId) {
        if (!confirm('确定删除?')) {
            return;
        }

        try {
            await TaskAPI.delete(taskId);
            UI.showAlert('任务删除成功', 'success');
            this.load();
        } catch (error) {
            console.error('删除任务失败:', error);
            UI.showAlert('删除任务失败: ' + error.message, 'error');
        }
    },

    // HTML 转义
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    // 绑定表单提交事件
    const form = document.getElementById('addTaskForm');
    if (form) {
        form.addEventListener('submit', (e) => TaskManager.save(e));
    }

    // 定时刷新任务列表（每5秒）
    setInterval(() => {
        if (document.getElementById('tasks').style.display !== 'none') {
            TaskManager.load();
        }
    }, 5000);
});
