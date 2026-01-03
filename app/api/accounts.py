from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, field_serializer
import re
from app.redis_client import account_redis_service

router = APIRouter(prefix="/api/accounts", tags=["账号管理"])

# Pydantic模型
class AccountBase(BaseModel):
    username: str
    password: str
    status: int = 1

class AccountCreate(AccountBase):
    pass

class AccountUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    status: Optional[int] = None

class AccountResponse(BaseModel):
    id: int
    username: str
    status: int
    created_at: Optional[datetime] = None

    @field_serializer('created_at')
    def serialize_created_at(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    class Config:
        from_attributes = True

# API路由
@router.get("/", response_model=List[AccountResponse])
async def get_accounts(skip: int = 0, limit: int = 100):
    """获取账号列表"""
    accounts = account_redis_service.get_all_accounts(skip=skip, limit=limit)
    return accounts

@router.get("/count")
async def get_account_count():
    """获取账号总数"""
    total = account_redis_service.get_total_count()
    return {"total": total}

@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(account_id: int):
    """获取单个账号信息"""
    account = account_redis_service.get_account(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"账号ID {account_id} 不存在"
        )
    return account

@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(account: AccountCreate):
    """创建新账号"""
    import traceback
    print(f"收到创建账号请求: username={account.username}, status={account.status}")

    try:
        # 检查用户名是否已存在
        existing = account_redis_service.get_account_by_username(account.username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"用户名 {account.username} 已存在"
            )

        print(f"开始创建账号...")
        new_account = account_redis_service.create_account(
            username=account.username,
            password=account.password,
            status=account.status
        )
        print(f"账号创建成功: {new_account}")
        return new_account
    except HTTPException:
        raise
    except Exception as e:
        print(f"创建账号异常: {str(e)}")
        print(f"错误堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建账号失败: {str(e)}"
        )

@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(account_id: int, account_update: AccountUpdate):
    """更新账号信息"""
    # 更新账号信息
    update_data = account_update.model_dump(exclude_unset=True)
    updated_account = account_redis_service.update_account(account_id, update_data)

    if not updated_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"账号ID {account_id} 不存在"
        )

    return updated_account


@router.post("/batch-delete")
async def batch_delete_accounts(account_ids: List[int]):
    """批量删除账号"""
    if not account_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供要删除的账号ID列表"
        )

    deleted_count = account_redis_service.batch_delete_accounts(account_ids)

    return {
        "deleted_count": deleted_count,
        "total_requested": len(account_ids)
    }

@router.delete("/all")
async def delete_all_accounts():
    """删除全部账号"""
    try:
        # 删除所有账号
        total_count = account_redis_service.delete_all_accounts()

        return {
            "deleted_count": total_count,
            "message": f"成功删除 {total_count} 个账号"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除全部账号失败: {str(e)}"
        )

@router.post("/import")
async def import_accounts(file: UploadFile = File(...)):
    """
    导入账号文件
    支持三种格式：
    1. 空格分割账号和密码
    2. 移除"账号："字符，竖线|分割账号和密码
    3. 移除"账号：账号："字符，密码分割账号和密码
    """
    # 检查文件大小（10MB限制）
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件大小超过限制（最大10MB）"
        )
    text_content = content.decode('utf-8')
    lines = text_content.strip().split('\n')

    # 限制导入数量（最多10000个账号）
    MAX_IMPORT_COUNT = 10000
    if len(lines) > MAX_IMPORT_COUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"单次最多导入{MAX_IMPORT_COUNT}个账号"
        )

    imported_count = 0
    error_count = 0
    errors = []

    # 批量导入优化：先收集所有待导入的账号
    accounts_to_import = []
    usernames_to_check = set()

    # 第一步：解析所有行，收集账号信息
    for line in lines:
        line = line.strip()
        if not line:
            continue

        username = None
        password = None

        # 尝试格式1：空格分割
        if ' ' in line and '|' not in line and '密码' not in line:
            parts = line.split(' ')
            if len(parts) >= 2:
                username = parts[0].strip()
                password = parts[1].strip()

        # 尝试格式2：移除"账号："字符，竖线|分割
        elif '|' in line:
            line = line.replace('账号：', '').replace('账号:', '')
            parts = line.split('|')
            if len(parts) >= 2:
                username = parts[0].strip()
                password = parts[1].strip()

        # 尝试格式3：移除"账号：账号："字符，密码分割
        elif '密码' in line:
            line = line.replace('账号：账号：', '').replace('账号:账号:', '')
            parts = line.split('密码')
            if len(parts) >= 2:
                username = parts[0].strip()
                password = parts[1].replace('：', '').replace(':', '').strip()

        # 收集待导入的账号
        if username and password:
            accounts_to_import.append((username, password))
            usernames_to_check.add(username)
        else:
            error_count += 1
            errors.append(f"无法解析行: {line}")

    # 第二步：批量检查已存在的账号
    existing_usernames = set()
    if usernames_to_check:
        existing_usernames = account_redis_service.batch_check_usernames(usernames_to_check)

    # 第三步：使用Redis管道批量导入
    if accounts_to_import:
        batch_result = account_redis_service.batch_create_accounts(
            [(u, p) for u, p in accounts_to_import if u not in existing_usernames]
        )
        imported_count = batch_result['imported']
        error_count += batch_result['errors']
        errors.extend(batch_result['error_details'])

        # 添加已存在的账号到错误列表
        for username in existing_usernames:
            error_count += 1
            errors.append(f"账号已存在: {username}")

    return {
        "imported": imported_count,
        "errors": error_count,
        "error_details": errors[:10]  # 只返回前10个错误
    }
@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: int):
    """删除账号"""
    deleted = account_redis_service.delete_account(account_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"账号ID {account_id} 不存在"
        )
    return None
