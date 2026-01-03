// 账号管理模块
const AccountManager = {
    currentPage: 1,
    pageSize: 100,

    load() {
        const skip = (this.currentPage - 1) * this.pageSize;
        AccountAPI.list(skip, this.pageSize)
            .then(accounts => this.render(accounts))
            .catch(error => UI.showAlert('加载失败: ' + error.message, 'error'));
    },

    render(accounts) {
        const tbody = document.querySelector('#accountsTable tbody');
        if (!tbody) return;

        tbody.innerHTML = accounts.length === 0
            ? '<tr><td colspan="7" style="text-align: center; padding: 20px;">暂无数据</td></tr>'
            : accounts.map(account => `
                <tr>
                    <td><input type="checkbox" class="account-checkbox" value="${account.id}"></td>
                    <td>${account.id}</td>
                    <td>${this.escapeHtml(account.username)}</td>
                    <td>${this.escapeHtml(account.password)}</td>
                    <td>${UI.getStatusBadge(account.status === 1 ? 'active' : 'inactive')}</td>
                    <td>${account.created_at}</td>
                    <td>
                        <button class="btn btn-warning btn-sm" onclick="AccountManager.edit(${account.id})">编辑</button>
                        <button class="btn btn-danger btn-sm" onclick="AccountManager.delete(${account.id})">删除</button>
                    </td>
                </tr>
            `).join('');

        this.updatePagination(accounts.length);
    },

    updatePagination(count) {
        const hasMore = count >= this.pageSize;
        const html = `
            <div class="pagination">
                <button class="btn btn-sm" onclick="AccountManager.goToPage(1)" ${this.currentPage === 1 ? 'disabled' : ''}>首页</button>
                <button class="btn btn-sm" onclick="AccountManager.prev()" ${this.currentPage === 1 ? 'disabled' : ''}>上一页</button>
                <span>第 ${this.currentPage} 页</span>
                <button class="btn btn-sm" onclick="AccountManager.next()" ${!hasMore ? 'disabled' : ''}>下一页</button>
            </div>
        `;

        let div = document.getElementById('accountPagination');
        if (!div) {
            div = document.createElement('div');
            div.id = 'accountPagination';
            document.querySelector('#accounts .card').appendChild(div);
        }
        div.innerHTML = html;
    },

    prev() {
        if (this.currentPage > 1) {
            this.currentPage--;
            this.load();
        }
    },

    next() {
        this.currentPage++;
        this.load();
    },

    goToPage(page) {
        this.currentPage = page;
        this.load();
    },

    toggleSelectAll() {
        const checked = document.getElementById('selectAllAccounts').checked;
        document.querySelectorAll('.account-checkbox').forEach(cb => cb.checked = checked);
    },

    getSelectedIds() {
        return Array.from(document.querySelectorAll('.account-checkbox:checked')).map(cb => parseInt(cb.value));
    },

    async batchDelete() {
        const ids = this.getSelectedIds();
        if (ids.length === 0) {
            UI.showAlert('请先选择', 'warning');
            return;
        }

        if (!confirm(`确定删除 ${ids.length} 个账号?`)) return;

        try {
            await AccountAPI.batchDelete(ids);
            this.currentPage = 1;
            this.load();
            document.getElementById('selectAllAccounts').checked = false;
        } catch (error) {
            UI.showAlert('删除失败: ' + error.message, 'error');
        }
    },

    async deleteAll() {
        if (!confirm('确定删除全部?')) return;
        if (!confirm('再次确认?')) return;

        try {
            await AccountAPI.deleteAll();
            this.currentPage = 1;
            this.load();
            document.getElementById('selectAllAccounts').checked = false;
        } catch (error) {
            UI.showAlert('删除失败: ' + error.message, 'error');
        }
    },

    showAddModal() {
        const form = document.getElementById('addAccountForm');
        form.reset();
        document.getElementById('accountModalTitle').textContent = '添加账号';
        document.getElementById('accountId').value = '';
        UI.showModal('addAccountModal');
    },

    async showEditModal(id) {
        const account = await AccountAPI.get(id);
        const form = document.getElementById('addAccountForm');
        form.reset();
        document.getElementById('accountModalTitle').textContent = '编辑账号';
        document.getElementById('accountId').value = account.id;
        form.username.value = account.username;
        form.password.value = account.password;
        form.status.value = account.status;
        UI.showModal('addAccountModal');
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
        const id = document.getElementById('accountId').value;
        const data = {
            username: form.username.value.trim(),
            password: form.password.value.trim(),
            status: parseInt(form.status.value)
        };

        if (!data.username || !data.password) {
            UI.showAlert('请填写完整信息', 'error');
            this.isSubmitting = false;
            return;
        }

        try {
            if (id) {
                await AccountAPI.update(parseInt(id), data);
            } else {
                await AccountAPI.create(data);
            }
            UI.hideModal('addAccountModal');
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
            await AccountAPI.delete(id);
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
    document.getElementById('addAccountForm')?.addEventListener('submit', (e) => AccountManager.save(e));
});
