// 代理管理模块
const ProxyManager = {
    load() {
        ProxyAPI.list()
            .then(proxies => this.render(proxies))
            .catch(error => UI.showAlert('加载失败: ' + error.message, 'error'));
    },

    render(proxies) {
        const tbody = document.querySelector('#proxiesTable tbody');
        if (!tbody) return;

        tbody.innerHTML = proxies.length === 0
            ? '<tr><td colspan="8" style="text-align: center; padding: 20px;">暂无数据</td></tr>'
            : proxies.map(proxy => `
                <tr>
                    <td>${proxy.id}</td>
                    <td>${this.escapeHtml(proxy.url)}</td>
                    <td>${this.escapeHtml(proxy.proxy_type)}</td>
                    <td>${proxy.port}</td>
                    <td>${this.escapeHtml(proxy.username || '-')}</td>
                    <td>${UI.getStatusBadge(proxy.status === 1 ? 'active' : 'inactive')}</td>
                    <td>${proxy.created_at}</td>
                    <td>
                        <button class="btn btn-warning btn-sm" onclick="ProxyManager.edit(${proxy.id})">编辑</button>
                        <button class="btn btn-danger btn-sm" onclick="ProxyManager.delete(${proxy.id})">删除</button>
                    </td>
                </tr>
            `).join('');
    },

    showAddModal() {
        const form = document.getElementById('addProxyForm');
        form.reset();
        document.getElementById('proxyModalTitle').textContent = '添加代理';
        document.getElementById('proxyId').value = '';
        UI.showModal('addProxyModal');
    },

    async showEditModal(id) {
        const proxy = await ProxyAPI.get(id);
        const form = document.getElementById('addProxyForm');
        form.reset();
        document.getElementById('proxyModalTitle').textContent = '编辑代理';
        document.getElementById('proxyId').value = proxy.id;
        form.url.value = proxy.url;
        form.proxy_type.value = proxy.proxy_type;
        form.port.value = proxy.port;
        form.username.value = proxy.username || '';
        form.password.value = proxy.password || '';
        form.status.value = proxy.status;
        UI.showModal('addProxyModal');
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
        const id = document.getElementById('proxyId').value;
        const data = {
            url: form.url.value.trim(),
            proxy_type: form.proxy_type.value,
            port: parseInt(form.port.value),
            username: form.username.value.trim(),
            password: form.password.value.trim(),
            status: parseInt(form.status.value)
        };

        if (!data.url || !data.proxy_type || !data.port) {
            UI.showAlert('请填写完整信息', 'error');
            this.isSubmitting = false;
            return;
        }

        try {
            if (id) {
                await ProxyAPI.update(parseInt(id), data);
            } else {
                await ProxyAPI.create(data);
            }
            UI.hideModal('addProxyModal');
            this.load();
        } catch (error) {
            UI.showAlert('保存失败: ' + error.message, 'error');
        } finally {
            this.isSubmitting = false;
        }
    },

    edit(id) {
        this.showEditModal(id);
    },

    async delete(id) {
        if (!confirm('确定删除?')) return;
        try {
            await ProxyAPI.delete(id);
            this.load();
        } catch (error) {
            UI.showAlert('删除失败: ' + error.message, 'error');
        }
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

document.addEventListener('DOMContentLoaded', () => {
    ProxyManager.load();
    document.getElementById('addProxyForm')?.addEventListener('submit', (e) => ProxyManager.save(e));
});
