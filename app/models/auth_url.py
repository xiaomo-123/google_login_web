from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class AuthUrl(Base):
    __tablename__ = "auth_urls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="授权地址名称")
    url = Column(String(500), nullable=False, comment="授权URL")
    description = Column(Text, nullable=True, comment="描述")
    status = Column(Integer, default=1, nullable=False, comment="状态：1-正常，0-禁用")
    created_at = Column(DateTime, default=lambda: datetime.now(), comment="创建时间")
    updated_at = Column(DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now(), comment="更新时间")

    # 关联任务
    tasks = relationship("Task", back_populates="auth_url")

    def __repr__(self):
        return f"<AuthUrl(id={self.id}, name={self.name}, url={self.url})>"
