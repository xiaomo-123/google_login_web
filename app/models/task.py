from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

# 注意：账号信息已迁移到Redis中，Task模型不再直接处理账号信息
# account_type用于标识任务使用的账号类型，初始值为1-6
# 具体的账号信息（username、password）在google_login_service.py中从Redis读取
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="任务名称")
    account_type = Column(Integer, default=1, nullable=False, comment="账号类型：1-6，用于标识从Redis中读取的账号类型")
    auth_url_id = Column(Integer, ForeignKey("auth_urls.id"), nullable=False, comment="授权地址ID")
    proxy_id = Column(Integer, ForeignKey("proxies.id"), nullable=True, comment="代理ID")
    status = Column(String(50), default="pending", nullable=False, comment="状态：pending-等待，running-运行中，completed-完成，error-错误，stopped-已停止")
    result = Column(Text, nullable=True, comment="执行结果")
    error_message = Column(Text, nullable=True, comment="错误信息")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    created_at = Column(DateTime, default=lambda: datetime.now(), comment="创建时间")
    updated_at = Column(DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now(), comment="更新时间")

    # 关联授权地址
    auth_url = relationship("AuthUrl", back_populates="tasks")
    # 关联代理
    proxy = relationship("Proxy", back_populates="tasks")

    def __repr__(self):
        return f"<Task(id={self.id}, name={self.name}, status={self.status})>"
