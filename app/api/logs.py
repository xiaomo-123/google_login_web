"""
日志API路由 - 提供日志发布接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.websocket_server import log_publisher

router = APIRouter(prefix="/api/logs", tags=["日志管理"])


class LogRequest(BaseModel):
    """日志请求模型"""
    task_id: int
    level: str = "info"  # info, warning, error, debug
    message: str
    extra: Optional[dict] = None


@router.post("/publish")
async def publish_log(request: LogRequest):
    """发布日志

    Args:
        request: 日志请求

    Returns:
        发布结果
    """
    try:
        # 验证日志级别
        valid_levels = ["info", "warning", "error", "debug"]
        if request.level not in valid_levels:
            raise HTTPException(
                status_code=400,
                detail=f"无效的日志级别: {request.level}。有效级别: {', '.join(valid_levels)}"
            )

        # 发布日志
        extra = request.extra or {}
        log_publisher.publish_log(
            task_id=request.task_id,
            level=request.level,
            message=request.message,
            **extra
        )

        return {
            "success": True,
            "message": "日志发布成功",
            "task_id": request.task_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发布日志失败: {str(e)}")


@router.get("/simulate")
async def simulate_logs(task_id: int, count: int = 10):
    """模拟生成日志

    Args:
        task_id: 任务ID
        count: 生成日志数量

    Returns:
        生成结果
    """
    import time
    import random

    try:
        # 模拟日志消息
        messages = [
            "任务开始执行",
            "正在加载配置",
            "初始化浏览器环境",
            "连接到目标网站",
            "正在执行登录操作",
            "验证用户凭证",
            "处理响应数据",
            "保存执行结果",
            "清理临时文件",
            "任务执行完成"
        ]

        levels = ["info", "warning", "error", "debug"]

        # 生成日志
        for i in range(count):
            level = random.choice(levels)
            message = messages[i % len(messages)]
            if level == "error":
                message = f"错误: {message} - 操作失败"
            elif level == "warning":
                message = f"警告: {message} - 需要注意"
            elif level == "debug":
                message = f"调试: {message} - 详细信息"

            # 添加额外信息
            extra = {
                "step": i + 1,
                "total": count,
                "progress": f"{((i + 1) / count) * 100:.1f}%"
            }

            # 发布日志
            log_publisher.publish_log(
                task_id=task_id,
                level=level,
                message=message,
                **extra
            )

            # 短暂延迟
            time.sleep(0.1)

        return {
            "success": True,
            "message": f"已生成 {count} 条日志",
            "task_id": task_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模拟日志失败: {str(e)}")
