// 授权地址管理模块
const AuthUrlManager = {
    load() {
        AuthUrlAPI.list()
            .then(authUrls => this.render(authUrls))
            .catch(error => UI.showAlert('加载失败: ' + error.message, 'error'));
    },

    render(authUrls) {
        const tbody = document.querySelector('#authUrlsTable tbody');
        if (!tbody) return;

        tbody.innerHTML = authUrls.length === 0
            ? '<tr><td colspan="6" style="text-align: center; padding: 20px;">暂无数据</td></tr>'
            : authUrls.map(url => `
                <tr>
                    <td>${url.id}</td>
                    <td>${this.escapeHtml(url.name)}</td>
                    <td>${this.escapeHtml(url.url)}</td>
                    <td>${url.description ? this.escapeHtml(url.description) : '-'}</td>
                    <td>${UI.getStatusBadge(url.status === 1 ? 'active' : 'inactive')}</td>
                    <td>
                        <button class="btn btn-warning btn-sm" onclick="AuthUrlManager.edit(${url.id})">编辑</button>
                        <button class="btn btn-danger btn-sm" onclick="AuthUrlManager.delete(${url.id})">删除</button>
                    </td>
                </tr>
            `).join('');
    },

    showAddModal() {
        const form = document.getElementById('addAuthUrlForm');
        form.reset();
        document.getElementById('authUrlModalTitle').textContent = '添加授权地址';
        document.getElementById('authUrlId').value = '';
        UI.showModal('addAuthUrlModal');
    },

    async showEditModal(id) {
        const authUrl = await AuthUrlAPI.get(id);
        const form = document.getElementById('addAuthUrlForm');
        form.reset();
        document.getElementById('authUrlModalTitle').textContent = '编辑授权地址';
        document.getElementById('authUrlId').value = authUrl.id;
        form.name.value = authUrl.name;
        form.url.value = authUrl.url;
        form.description.value = authUrl.description || '';
        form.status.value = authUrl.status;
        UI.showModal('addAuthUrlModal');
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
        const id = document.getElementById('authUrlId').value;
        const data = {
            name: form.name.value.trim(),
            url: form.url.value.trim(),
            description: form.description.value.trim(),
            status: parseInt(form.status.value)
        };

        if (!data.name || !data.url) {
            UI.showAlert('请填写完整信息', 'error');
            this.isSubmitting = false;
            return;
        }

        try {
            new URL(data.url);
        } catch {
            UI.showAlert('URL格式错误', 'error');
            this.isSubmitting = false;
            return;
        }

        try {
            if (id) {
                await AuthUrlAPI.update(parseInt(id), data);
            } else {
                await AuthUrlAPI.create(data);
            }
            UI.hideModal('addAuthUrlModal');
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
            await AuthUrlAPI.delete(id);
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
    document.getElementById('addAuthUrlForm')?.addEventListener('submit', (e) => AuthUrlManager.save(e));
});
