
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Proxy(Base):
    __tablename__ = "proxies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(500), nullable=False, comment="代理URL")
    proxy_type = Column(String(50), nullable=False, comment="代理类型：http, https, socks5")
    port = Column(Integer, nullable=False, comment="端口号")
    username = Column(String(255), nullable=True, comment="用户名")
    password = Column(String(255), nullable=True, comment="密码")
    status = Column(Integer, default=1, nullable=False, comment="状态：1-正常，0-禁用")
    created_at = Column(DateTime, default=lambda: datetime.now(), comment="创建时间")
    updated_at = Column(DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now(), comment="更新时间")

    # 关联任务
    tasks = relationship("Task", back_populates="proxy")

    def __repr__(self):
        return f"<Proxy(id={self.id}, url={self.url}, type={self.proxy_type}, port={self.port})>"
