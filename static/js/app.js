// API 基础 URL - 使用相对路径避免跨域问题
const API_BASE_URL = '/api';

// 统一的 API 请求处理
async function request(url, options = {}) {
    const response = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || '请求失败');
    }

    return response.json();
}

// 账号管理 API
const AccountAPI = {
    list(skip = 0, limit = 100) {
        return request(`${API_BASE_URL}/accounts?skip=${skip}&limit=${limit}`);
    },

    get(id) {
        return request(`${API_BASE_URL}/accounts/${id}`);
    },

    create(account) {
        return request(`${API_BASE_URL}/accounts`, {
            method: 'POST',
            body: JSON.stringify(account)
        });
    },

    update(id, account) {
        return request(`${API_BASE_URL}/accounts/${id}`, {
            method: 'PUT',
            body: JSON.stringify(account)
        });
    },

    delete(id) {
        return request(`${API_BASE_URL}/accounts/${id}`, { method: 'DELETE' });
    },

    batchDelete(accountIds) {
        return request(`${API_BASE_URL}/accounts/batch-delete`, {
            method: 'POST',
            body: JSON.stringify(accountIds)
        });
    },

    deleteAll() {
        return request(`${API_BASE_URL}/accounts/all`, { method: 'DELETE' });
    },

    import(file) {
        const formData = new FormData();
        formData.append('file', file);
        return fetch(`${API_BASE_URL}/accounts/import`, { method: 'POST', body: formData })
            .then(r => r.json());
    },

    export() {
        window.location.href = `${API_BASE_URL}/accounts/export`;
    }
};

// 授权地址管理 API
const AuthUrlAPI = {
    list(skip = 0, limit = 100) {
        return request(`${API_BASE_URL}/auth-urls?skip=${skip}&limit=${limit}`);
    },

    get(id) {
        return request(`${API_BASE_URL}/auth-urls/${id}`);
    },

    create(authUrl) {
        return request(`${API_BASE_URL}/auth-urls`, {
            method: 'POST',
            body: JSON.stringify(authUrl)
        });
    },

    update(id, authUrl) {
        return request(`${API_BASE_URL}/auth-urls/${id}`, {
            method: 'PUT',
            body: JSON.stringify(authUrl)
        });
    },

    delete(id) {
        return request(`${API_BASE_URL}/auth-urls/${id}`, { method: 'DELETE' });
    }
};

// 任务管理 API
const TaskAPI = {
    list(skip = 0, limit = 100) {
        return request(`${API_BASE_URL}/tasks?skip=${skip}&limit=${limit}`);
    },

    get(id) {
        return request(`${API_BASE_URL}/tasks/${id}`);
    },

    create(task) {
        return request(`${API_BASE_URL}/tasks`, {
            method: 'POST',
            body: JSON.stringify(task)
        });
    },

    update(id, task) {
        return request(`${API_BASE_URL}/tasks/${id}`, {
            method: 'PUT',
            body: JSON.stringify(task)
        });
    },

    delete(id) {
        return request(`${API_BASE_URL}/tasks/${id}`, { method: 'DELETE' });
    },

    start(id) {
        return request(`${API_BASE_URL}/tasks/${id}/start`, { method: 'POST' });
    },

    stop(id) {
        return request(`${API_BASE_URL}/tasks/${id}/stop`, { method: 'POST' });
    }
};

// 代理管理 API
const ProxyAPI = {
    list(skip = 0, limit = 100) {
        return request(`${API_BASE_URL}/proxies?skip=${skip}&limit=${limit}`);
    },

    get(id) {
        return request(`${API_BASE_URL}/proxies/${id}`);
    },

    create(proxy) {
        return request(`${API_BASE_URL}/proxies`, {
            method: 'POST',
            body: JSON.stringify(proxy)
        });
    },

    update(id, proxy) {
        return request(`${API_BASE_URL}/proxies/${id}`, {
            method: 'PUT',
            body: JSON.stringify(proxy)
        });
    },

    delete(id) {
        return request(`${API_BASE_URL}/proxies/${id}`, { method: 'DELETE' });
    }
};

// UI 工具函数
const UI = {
    showAlert(message, type = 'success') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type}`;
        alertDiv.textContent = message;
        document.body.insertBefore(alertDiv, document.body.firstChild);
        setTimeout(() => alertDiv.remove(), 3000);
    },

    showModal(modalId) {
        document.getElementById(modalId)?.classList.add('active');
    },

    hideModal(modalId) {
        document.getElementById(modalId)?.classList.remove('active');
    },

    getStatusBadge(status) {
        const statusLabels = {
            'active': '正常',
            'inactive': '禁用',
            'pending': '等待',
            'running': '运行中',
            'completed': '完成',
            'error': '错误',
            'stopped': '已停止'
        };
        return `<span class="status-badge status-${status}">${statusLabels[status] || status}</span>`;
    }
};

// 页面初始化
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.nav-links a').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const sectionId = link.getAttribute('data-section');
            showSection(sectionId);
            // 保存当前页面到localStorage
            localStorage.setItem('currentSection', sectionId);
        });
    });

    // 从localStorage恢复上次访问的页面
    const savedSection = localStorage.getItem('currentSection') || 'accounts';
    showSection(savedSection);
});

function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(section => {
        section.style.display = 'none';
    });

    const targetSection = document.getElementById(sectionId);
    if (targetSection) {
        targetSection.style.display = 'block';

        const managers = {
            'accounts': AccountManager,
            'auth-urls': AuthUrlManager,
            'tasks': TaskManager,
            'proxies': ProxyManager
        };

        if (managers[sectionId]) {
            managers[sectionId].load();
        }
    }

    document.querySelectorAll('.nav-links a').forEach(link => {
        link.classList.toggle('active', link.getAttribute('data-section') === sectionId);
    });
}

// 辅助函数
const showAddAccountModal = () => AccountManager.showAddModal();
const showImportAccountModal = () => UI.showModal('importAccountModal');
const showAddAuthUrlModal = () => AuthUrlManager.showAddModal();
const showAddProxyModal = () => ProxyManager.showAddModal();
const showAddTaskModal = () => TaskManager.showAddModal();

// 处理账号文件选择
async function handleAccountFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    const resultDiv = document.getElementById('importResult');
    resultDiv.innerHTML = '<div class="alert alert-warning">正在导入...</div>';

    try {
        const result = await AccountAPI.import(file);
        resultDiv.innerHTML = `
            <div class="alert alert-success">
                <strong>导入成功！</strong><br>
                成功导入 ${result.imported} 个账号
                ${result.errors > 0 ? `<br>失败 ${result.errors} 个` : ''}
            </div>
        `;
        // 清空文件输入框，确保可以再次导入
        event.target.value = '';
        AccountManager.load();
        UI.showAlert(`成功导入 ${result.imported} 个账号`, 'success');
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="alert alert-error">
                <strong>导入失败！</strong><br>
                ${error.message || '未知错误'}
            </div>
        `;
        // 清空文件输入框，确保可以再次导入
        event.target.value = '';
        UI.showAlert('导入失败: ' + (error.message || '未知错误'), 'error');
    }
}

// 文件选择事件
document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('accountFile');
    if (fileInput) {
        fileInput.addEventListener('change', handleAccountFileSelect);
    }
});
