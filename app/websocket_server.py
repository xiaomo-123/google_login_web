"""
WebSocket服务模块 - 实现实时任务日志推送
"""
import json
import asyncio
import redis.asyncio as redis
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class WebSocketLogManager:
    """WebSocket日志管理器"""

    def __init__(self):
        # 存储活跃的WebSocket连接: {task_id: Set[WebSocket]}
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # 存储WebSocket到task_id的映射: {WebSocket: task_id}
        self.connection_task_map: Dict[WebSocket, int] = {}
        # Redis订阅者
        self.redis_subscriber = None
        # 订阅任务
        self.subscribe_task = None
        # 是否正在运行
        self.is_running = False

    async def connect(self, websocket: WebSocket, task_id: int):
        """接受WebSocket连接"""
        await websocket.accept()

        # 添加到连接管理
        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()
        self.active_connections[task_id].add(websocket)
        self.connection_task_map[websocket] = task_id



        # 发送连接成功消息
        await websocket.send_json({
            "type": "connected",
            "task_id": task_id,
            "message": "日志连接已建立"
        })

    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        # 获取task_id
        task_id = self.connection_task_map.get(websocket)

        if task_id and task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)
            # 如果该任务没有其他连接，清理任务
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]

        # 移除映射
        if websocket in self.connection_task_map:
            del self.connection_task_map[websocket]



    async def broadcast_to_task(self, task_id: int, message: dict):
        """向特定任务的所有连接广播消息"""
        if task_id not in self.active_connections:
            return

        # 向该任务的所有连接发送消息
        disconnected = set()
        for connection in self.active_connections[task_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"发送消息失败: {e}")
                disconnected.add(connection)

        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)

    async def start_redis_subscriber(self):
        """启动Redis订阅者"""
        if self.is_running:
            return

        try:
            # 创建Redis连接
            self.redis_subscriber = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )

            # 创建PubSub
            pubsub = self.redis_subscriber.pubsub()

            # 订阅所有任务日志频道 (使用模式匹配)
            await pubsub.psubscribe("task_logs:*")

            self.is_running = True


            # 持续监听消息
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    try:
                        # 解析频道名称获取task_id
                        channel = message["channel"]
                        task_id = int(channel.split(":")[1])

                        # 解析消息内容
                        data = json.loads(message["data"])

                        # 广播到该任务的WebSocket连接
                        await self.broadcast_to_task(task_id, data)
                    except Exception as e:
                        logger.error(f"处理Redis消息失败: {e}")

        except Exception as e:
            logger.error(f"Redis订阅者启动失败: {e}")
            self.is_running = False

    async def stop_redis_subscriber(self):
        """停止Redis订阅者"""
        if self.redis_subscriber:
            await self.redis_subscriber.close()
            self.is_running = False



# 创建全局日志管理器实例
log_manager = WebSocketLogManager()


class LogPublisher:
    """日志发布器 - 用于业务代码发布日志"""

    def __init__(self):
        # 使用同步Redis客户端
        import redis
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )

    def publish_log(self, task_id: int, level: str, message: str, **extra):
        """发布日志到Redis

        Args:
            task_id: 任务ID
            level: 日志级别 (info, warning, error, debug)
            message: 日志消息
            **extra: 额外字段
        """
        try:
            # 构造日志数据
            log_data = {
                "type": "log",
                "task_id": task_id,
                "level": level,
                "message": message,
                "timestamp": asyncio.get_event_loop().time(),
                **extra
            }

            # 发布到Redis频道
            channel = f"task_logs:{task_id}"
            self.redis_client.publish(channel, json.dumps(log_data))



        except Exception as e:
            logger.error(f"发布日志失败: {e}")


# 创建全局日志发布器实例
log_publisher = LogPublisher()
