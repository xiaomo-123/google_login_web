
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.proxy import Proxy
from pydantic import BaseModel, field_serializer

router = APIRouter(prefix="/api/proxies", tags=["代理管理"])

# Pydantic模型
class ProxyBase(BaseModel):
    url: str
    proxy_type: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    status: int = 1

class ProxyCreate(ProxyBase):
    pass

class ProxyUpdate(BaseModel):
    url: Optional[str] = None
    proxy_type: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    status: Optional[int] = None

class ProxyResponse(BaseModel):
    id: int
    url: str
    proxy_type: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    status: int
    created_at: Optional[datetime] = None

    @field_serializer('created_at')
    def serialize_created_at(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    class Config:
        from_attributes = True

# API路由
@router.get("/", response_model=List[ProxyResponse])
async def get_proxies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取代理列表"""
    proxies = db.query(Proxy).offset(skip).limit(limit).all()
    return proxies

@router.get("/{proxy_id}", response_model=ProxyResponse)
async def get_proxy(proxy_id: int, db: Session = Depends(get_db)):
    """获取单个代理信息"""
    proxy = db.query(Proxy).filter(Proxy.id == proxy_id).first()
    if not proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"代理ID {proxy_id} 不存在"
        )
    return proxy

@router.post("/", response_model=ProxyResponse, status_code=status.HTTP_201_CREATED)
async def create_proxy(proxy: ProxyCreate, db: Session = Depends(get_db)):
    """创建新代理"""
    new_proxy = Proxy(**proxy.model_dump())
    db.add(new_proxy)
    db.commit()
    db.refresh(new_proxy)
    return new_proxy

@router.put("/{proxy_id}", response_model=ProxyResponse)
async def update_proxy(proxy_id: int, proxy_update: ProxyUpdate, db: Session = Depends(get_db)):
    """更新代理信息"""
    db_proxy = db.query(Proxy).filter(Proxy.id == proxy_id).first()
    if not db_proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"代理ID {proxy_id} 不存在"
        )

    # 更新代理信息
    update_data = proxy_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_proxy, key, value)

    db.commit()
    db.refresh(db_proxy)
    return db_proxy

@router.delete("/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy(proxy_id: int, db: Session = Depends(get_db)):
    """删除代理"""
    db_proxy = db.query(Proxy).filter(Proxy.id == proxy_id).first()
    if not db_proxy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"代理ID {proxy_id} 不存在"
        )

    db.delete(db_proxy)
    db.commit()
    return None
