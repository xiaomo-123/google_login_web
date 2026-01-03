// 账号导入专用模块
const AccountImport = {
    // 显示导入模态框
    showImportModal() {
        document.getElementById('importResult').innerHTML = '';
        UI.showModal('importAccountModal');
    },

    // 隐藏导入模态框
    hideImportModal() {
        UI.hideModal('importAccountModal');
        document.getElementById('accountFile').value = '';
        document.getElementById('importResult').innerHTML = '';
    },

    // 处理文件选择
    async handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file) return;

        // 防止重复提交
        if (this.isImporting) {
            UI.showAlert('正在导入中，请稍候...', 'error');
            return;
        }
        this.isImporting = true;

        // 验证文件类型
        if (!file.name.endsWith('.txt')) {
            UI.showAlert('请选择 TXT 文件', 'error');
            this.isImporting = false;
            return;
        }

        // 显示加载状态
        const resultDiv = document.getElementById('importResult');
        resultDiv.innerHTML = '<div class="alert alert-warning"><span class="loading"></span> 正在导入...</div>';

        try {
            // 调用导入 API
            const result = await AccountAPI.import(file);

            // 显示导入结果
            if (result.errors === 0) {
                resultDiv.innerHTML = `
                    <div class="alert alert-success">
                        <strong>导入成功！</strong><br>
                        成功导入 ${result.imported} 个账号
                    </div>
                `;
                UI.showAlert(`成功导入 ${result.imported} 个账号`, 'success');
            } else {
                resultDiv.innerHTML = `
                    <div class="alert alert-warning">
                        <strong>导入完成</strong><br>
                        成功导入 ${result.imported} 个账号<br>
                        失败 ${result.errors} 个账号
                        ${result.error_details && result.error_details.length > 0 ? 
                            `<br><br><strong>错误详情：</strong><br>${result.error_details.join('<br>')}` : ''}
                    </div>
                `;
                UI.showAlert(`导入完成：成功 ${result.imported} 个，失败 ${result.errors} 个`, 'warning');
            }

            // 刷新账号列表
            await AccountManager.load();

            // 3秒后自动关闭模态框
            setTimeout(() => {
                this.hideImportModal();
            }, 3000);

        } catch (error) {
            console.error('导入失败:', error);
            resultDiv.innerHTML = `
                <div class="alert alert-error">
                    <strong>导入失败！</strong><br>
                    ${error.message || '未知错误'}
                </div>
            `;
            UI.showAlert('导入失败: ' + (error.message || '未知错误'), 'error');
        } finally {
            this.isImporting = false;
        }
    },

    // 验证文件格式
    validateFileContent(content) {
        const lines = content.split('\n');
        const errors = [];
        let validCount = 0;

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;

            // 检查格式1：空格分隔
            if (line.includes(' ') && !line.includes('|') && !line.includes('密码')) {
                const parts = line.split(/\s+/);
                if (parts.length >= 2) {
                    validCount++;
                    continue;
                }
            }

            // 检查格式2：|分隔
            if (line.includes('|')) {
                const parts = line.split('|');
                if (parts.length >= 2) {
                    validCount++;
                    continue;
                }
            }

            // 检查格式3：密码分隔
            if (line.includes('密码')) {
                const parts = line.split('密码');
                if (parts.length >= 2) {
                    validCount++;
                    continue;
                }
            }

            errors.push(`第 ${i + 1} 行格式不正确: ${line.substring(0, 50)}...`);
        }

        return {
            valid: validCount,
            errors: errors,
            total: lines.length
        };
    },

    // 预览文件内容
    previewFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const content = e.target.result;
            const validation = this.validateFileContent(content);

            const previewDiv = document.getElementById('importPreview');
            if (previewDiv) {
                previewDiv.innerHTML = `
                    <div class="preview-info">
                        <p><strong>文件预览：</strong></p>
                        <p>总行数: ${validation.total}</p>
                        <p>有效账号: ${validation.valid}</p>
                        <p>错误行数: ${validation.errors.length}</p>
                        ${validation.errors.length > 0 ? 
                            `<p class="error-details"><strong>错误详情：</strong><br>${validation.errors.join('<br>')}</p>` : ''}
                    </div>
                `;
            }
        };
        reader.readAsText(file);
    }
};

// 文件上传区域拖拽支持
document.addEventListener('DOMContentLoaded', () => {
    const uploadArea = document.querySelector('.file-upload');
    const fileInput = document.getElementById('accountFile');

    if (uploadArea && fileInput) {
        // 点击上传区域触发文件选择
        uploadArea.addEventListener('click', () => {
            fileInput.click();
        });

        // 拖拽事件处理
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.style.borderColor = '#3498db';
            uploadArea.style.backgroundColor = '#f0f8ff';
        });

        uploadArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            uploadArea.style.borderColor = '#ddd';
            uploadArea.style.backgroundColor = 'transparent';
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.style.borderColor = '#ddd';
            uploadArea.style.backgroundColor = 'transparent';

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                fileInput.files = files;
                AccountImport.handleFileSelect({ target: { files: files } });
            }
        });

        // 文件选择事件
        fileInput.addEventListener('change', (e) => {
            AccountImport.handleFileSelect(e);
        });
    }
});
