from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.auth_url import AuthUrl
from pydantic import BaseModel, field_serializer

router = APIRouter(prefix="/api/auth-urls", tags=["授权地址管理"])

# Pydantic模型
class AuthUrlBase(BaseModel):
    name: str
    url: str
    description: Optional[str] = None
    status: int = 1

class AuthUrlCreate(AuthUrlBase):
    pass

class AuthUrlUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    status: Optional[int] = None

class AuthUrlResponse(BaseModel):
    id: int
    name: str
    url: str
    description: Optional[str] = None
    status: int
    created_at: Optional[datetime] = None

    @field_serializer('created_at')
    def serialize_created_at(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    class Config:
        from_attributes = True

# API路由
@router.get("/", response_model=List[AuthUrlResponse])
async def get_auth_urls(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取授权地址列表"""
    auth_urls = db.query(AuthUrl).offset(skip).limit(limit).all()
    return auth_urls

@router.get("/{auth_url_id}", response_model=AuthUrlResponse)
async def get_auth_url(auth_url_id: int, db: Session = Depends(get_db)):
    """获取单个授权地址信息"""
    auth_url = db.query(AuthUrl).filter(AuthUrl.id == auth_url_id).first()
    if not auth_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"授权地址ID {auth_url_id} 不存在"
        )
    return auth_url

@router.post("/", response_model=AuthUrlResponse, status_code=status.HTTP_201_CREATED)
async def create_auth_url(auth_url: AuthUrlCreate, db: Session = Depends(get_db)):
    """创建新授权地址"""
    new_auth_url = AuthUrl(**auth_url.model_dump())
    db.add(new_auth_url)
    db.commit()
    db.refresh(new_auth_url)
    return new_auth_url

@router.put("/{auth_url_id}", response_model=AuthUrlResponse)
async def update_auth_url(auth_url_id: int, auth_url_update: AuthUrlUpdate, db: Session = Depends(get_db)):
    """更新授权地址信息"""
    db_auth_url = db.query(AuthUrl).filter(AuthUrl.id == auth_url_id).first()
    if not db_auth_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"授权地址ID {auth_url_id} 不存在"
        )

    # 更新授权地址信息
    update_data = auth_url_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_auth_url, key, value)

    db.commit()
    db.refresh(db_auth_url)
    return db_auth_url

@router.delete("/{auth_url_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auth_url(auth_url_id: int, db: Session = Depends(get_db)):
    """删除授权地址"""
    db_auth_url = db.query(AuthUrl).filter(AuthUrl.id == auth_url_id).first()
    if not db_auth_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"授权地址ID {auth_url_id} 不存在"
        )

    db.delete(db_auth_url)
    db.commit()
    return None
