from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False, comment="用户名/邮箱")
    password = Column(String(255), nullable=False, comment="密码")
    status = Column(Integer, default=1, nullable=False, comment="状态：1-正常，0-禁用")
    created_at = Column(DateTime, default=lambda: datetime.now(), comment="创建时间")
    updated_at = Column(DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now(), comment="更新时间")

    def __repr__(self):
        return f"<Account(id={self.id}, username={self.username}, status={self.status})>"
