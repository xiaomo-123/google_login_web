"""
WebSocket API路由 - 提供WebSocket连接端点
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.websocket_server import log_manager

router = APIRouter(prefix="/api")


@router.websocket("/ws/logs/{task_id}")
async def websocket_logs(websocket: WebSocket, task_id: int):
    """WebSocket日志端点

    Args:
        websocket: WebSocket连接
        task_id: 任务ID
    """
    try:
        # 接受连接
        await log_manager.connect(websocket, task_id)

        # 保持连接并接收客户端消息
        while True:
            try:
                # 接收客户端消息（心跳等）
                data = await websocket.receive_text()

                # 处理心跳消息
                if data == "ping":
                    await websocket.send_json({"type": "pong"})

            except WebSocketDisconnect:
                break
            except Exception as e:
                break

    except Exception as e:
        pass

    finally:
        # 断开连接
        log_manager.disconnect(websocket)
