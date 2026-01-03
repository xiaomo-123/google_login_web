from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.task import Task
from app.models.auth_url import AuthUrl
from app.models.proxy import Proxy
from pydantic import BaseModel, field_serializer

router = APIRouter(prefix="/api/tasks", tags=["任务管理"])

# Pydantic模型
class TaskBase(BaseModel):
    name: str
    account_type: int = 1
    auth_url_id: int
    proxy_id: Optional[int] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    name: Optional[str] = None
    account_type: Optional[int] = None
    auth_url_id: Optional[int] = None
    proxy_id: Optional[int] = None
    status: Optional[str] = None
    result: Optional[str] = None
    error_message: Optional[str] = None

class TaskResponse(BaseModel):
    id: int
    name: str
    account_type: int
    auth_url_id: int
    proxy_id: Optional[int] = None
    status: str
    result: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    @field_serializer('created_at')
    def serialize_created_at(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    class Config:
        from_attributes = True

# API路由
@router.get("/", response_model=List[TaskResponse])
async def get_tasks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取任务列表"""
    tasks = db.query(Task).offset(skip).limit(limit).all()
    return tasks

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    """获取单个任务信息"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务ID {task_id} 不存在"
        )
    return task

@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    """创建新任务"""
    # 检查授权地址是否存在
    auth_url = db.query(AuthUrl).filter(AuthUrl.id == task.auth_url_id).first()
    if not auth_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"授权地址ID {task.auth_url_id} 不存在"
        )

    # 如果指定了代理，检查代理是否存在
    if task.proxy_id is not None:
        proxy = db.query(Proxy).filter(Proxy.id == task.proxy_id).first()
        if not proxy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"代理ID {task.proxy_id} 不存在"
            )

    new_task = Task(**task.model_dump())
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db)):
    """更新任务信息"""
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务ID {task_id} 不存在"
        )

    # 如果要更新授权地址ID，检查是否存在
    if task_update.auth_url_id is not None and task_update.auth_url_id != db_task.auth_url_id:
        auth_url = db.query(AuthUrl).filter(AuthUrl.id == task_update.auth_url_id).first()
        if not auth_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"授权地址ID {task_update.auth_url_id} 不存在"
            )

    # 如果要更新代理ID，检查是否存在
    if task_update.proxy_id is not None and task_update.proxy_id != db_task.proxy_id:
        # 如果proxy_id不为None，检查代理是否存在
        if task_update.proxy_id != 0:  # 0表示不使用代理
            proxy = db.query(Proxy).filter(Proxy.id == task_update.proxy_id).first()
            if not proxy:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"代理ID {task_update.proxy_id} 不存在"
                )

    # 更新任务信息
    update_data = task_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_task, key, value)

    # 如果更新了状态，记录时间
    if "status" in update_data:
        if update_data["status"] == "running" and db_task.started_at is None:  # 开始运行
            db_task.started_at = datetime.now()
        elif update_data["status"] in ["completed", "error", "stopped"]:  # 完成、错误或停止
            db_task.completed_at = datetime.now()

    db.commit()
    db.refresh(db_task)
    return db_task

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    """删除任务"""
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务ID {task_id} 不存在"
        )

    db.delete(db_task)
    db.commit()
    return None

@router.post("/{task_id}/start", response_model=TaskResponse)
async def start_task(task_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """启动任务"""
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务ID {task_id} 不存在"
        )

    if db_task.status == "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已在运行中"
        )

    # 更新任务状态为运行中
    db_task.status = "running"
    db_task.started_at = datetime.now()
    db.commit()

    # 添加后台任务
    from app.services.google_login_service import run_google_login_task
    background_tasks.add_task(run_google_login_task, task_id)

    db.refresh(db_task)
    return db_task

@router.post("/{task_id}/stop", response_model=TaskResponse)
async def stop_task(task_id: int, db: Session = Depends(get_db)):
    """停止任务"""
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务ID {task_id} 不存在"
        )

    if db_task.status != "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务未在运行中"
        )

    # 更新任务状态为已停止
    db_task.status = "stopped"
    db_task.completed_at = datetime.now()
    db.commit()
    db.refresh(db_task)
    return db_task
