import redis
from app.config import settings
from typing import Optional, Dict, List
import json
from datetime import datetime

# 创建Redis连接池
redis_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    decode_responses=settings.REDIS_DECODE_RESPONSES,
    socket_connect_timeout=5,
    socket_timeout=5
)

# 获取Redis客户端
def get_redis():
    """获取Redis客户端实例"""
    return redis.Redis(connection_pool=redis_pool)

# 账号相关Redis操作
class AccountRedisService:
    """账号Redis服务类"""

    def __init__(self):
        self.redis = get_redis()
        self.account_prefix = "account:"
        self.account_list_key = "accounts:list"

    def _generate_account_key(self, account_id: int) -> str:
        """生成账号的Redis key"""
        return f"{self.account_prefix}{account_id}"

    def _get_next_id(self) -> int:
        """获取下一个账号ID"""
        return self.redis.incr("account:next_id")

    def create_account(self, username: str, password: str, status: int = 1) -> Dict:
        """创建新账号"""
        import traceback
        print(f"开始创建账号: username={username}, status={status}")

        try:
            account_id = self._get_next_id()
            print(f"获取到账号ID: {account_id}")

            account_data = {
                "id": str(account_id),
                "username": username,
                "password": password,
                "status": str(status),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            print(f"账号数据: {account_data}")

            # 将账号数据存储到Redis
            account_key = self._generate_account_key(account_id)
            print(f"Redis key: {account_key}")

            # 使用hset的正确方式，逐个设置字段
            for field, value in account_data.items():
                self.redis.hset(account_key, field, value)
            print(f"账号数据已存储到Redis")

            # 将账号ID添加到列表
            self.redis.sadd(self.account_list_key, str(account_id))
            print(f"账号ID已添加到列表")

            # 返回符合AccountResponse格式的数据
            result = {
                "id": account_id,
                "username": username,
                "status": status,
                "created_at": account_data["created_at"]
            }
            print(f"返回结果: {result}")
            return result
        except Exception as e:
            print(f"创建账号异常: {str(e)}")
            print(f"错误堆栈: {traceback.format_exc()}")
            raise

    def get_account(self, account_id: int) -> Optional[Dict]:
        """获取单个账号"""
        account_key = self._generate_account_key(account_id)
        account_data = self.redis.hgetall(account_key)

        if not account_data:
            return None

        # 转换数据类型，返回完整账号信息
        return {
            "id": int(account_data.get("id", account_id)),
            "username": account_data.get("username", ""),
            "password": account_data.get("password", ""),
            "status": int(account_data.get("status", 1)),
            "created_at": account_data.get("created_at")
        }

    def get_all_accounts(self, skip: int = 0, limit: int = 100, get_all: bool = False, batch_size: int = 100) -> List[Dict]:
        """获取所有账号

        参数:
            skip: 跳过的记录数
            limit: 返回的记录数（默认100）
            get_all: 是否获取所有账号（忽略limit限制）
            batch_size: 分批获取时的每批大小（默认100）
        """
        # 获取所有账号ID
        account_ids = self.redis.smembers(self.account_list_key)
        account_ids = sorted([int(aid) for aid in account_ids])

        # 分页处理
        if get_all:
            # 获取所有账号，分批处理
            accounts = []
            total = len(account_ids)
            processed = 0

            while processed < total:
                # 获取当前批次的账号ID
                batch_ids = account_ids[processed:processed + batch_size]

                # 使用管道批量获取账号数据
                pipe = self.redis.pipeline()
                for account_id in batch_ids:
                    account_key = self._generate_account_key(account_id)
                    pipe.hgetall(account_key)
                batch_data = pipe.execute()

                # 处理批次数据
                for account_id, account_data in zip(batch_ids, batch_data):
                    if account_data:
                        accounts.append({
                            "id": int(account_data.get("id", account_id)),
                            "username": account_data.get("username", ""),
                            "password": account_data.get("password", ""),
                            "status": int(account_data.get("status", 1)),
                            "created_at": account_data.get("created_at")
                        })

                processed += len(batch_ids)
                print(f"已处理 {processed}/{total} 个账号")

            return accounts
        else:
            # 普通分页
            account_ids = account_ids[skip:skip + limit]

            # 获取账号详情
            accounts = []
            for account_id in account_ids:
                account_key = self._generate_account_key(account_id)
                account_data = self.redis.hgetall(account_key)

                if account_data:
                    accounts.append({
                        "id": int(account_data.get("id", account_id)),
                        "username": account_data.get("username", ""),
                        "password": account_data.get("password", ""),
                        "status": int(account_data.get("status", 1)),
                        "created_at": account_data.get("created_at")
                    })

            return accounts

    def get_total_count(self) -> int:
        """获取账号总数"""
        return self.redis.scard(self.account_list_key)

    def update_account(self, account_id: int, update_data: Dict) -> Optional[Dict]:
        """更新账号"""
        account_key = self._generate_account_key(account_id)

        # 检查账号是否存在
        if not self.redis.exists(account_key):
            return None

        # 获取当前账号数据
        current_data = self.redis.hgetall(account_key)

        # 合并更新数据，只更新提供的字段，确保所有值都是字符串
        merged_data = {**current_data, **update_data}
        merged_data["updated_at"] = datetime.now().isoformat()

        # 确保数值字段转换为字符串
        for key in ["id", "status"]:
            if key in merged_data:
                merged_data[key] = str(merged_data[key])

        # 更新账号数据
        # 使用hset的正确方式，逐个设置字段
        for field, value in merged_data.items():
            self.redis.hset(account_key, field, value)

        # 返回符合AccountResponse格式的数据
        return {
            "id": int(merged_data["id"]),
            "username": merged_data["username"],
            "status": int(merged_data["status"]),
            "created_at": merged_data.get("created_at")
        }

    def delete_account(self, account_id: int) -> bool:
        """删除账号"""
        account_key = self._generate_account_key(account_id)

        # 删除账号数据
        result = self.redis.delete(account_key)

        # 从列表中移除
        self.redis.srem(self.account_list_key, account_id)

        return result > 0

    def delete_all_accounts(self) -> int:
        """删除所有账号"""
        # 获取所有账号ID
        account_ids = self.redis.smembers(self.account_list_key)
        count = len(account_ids)

        # 删除所有账号数据
        for account_id in account_ids:
            account_key = self._generate_account_key(account_id)
            self.redis.delete(account_key)

        # 清空列表
        self.redis.delete(self.account_list_key)

        return count

    def batch_delete_accounts(self, account_ids: List[int]) -> int:
        """批量删除账号"""
        deleted_count = 0
        for account_id in account_ids:
            if self.delete_account(account_id):
                deleted_count += 1

        return deleted_count

    def get_account_by_username(self, username: str) -> Optional[Dict]:
        """根据用户名获取账号"""
        # 获取所有账号ID
        account_ids = self.redis.smembers(self.account_list_key)

        for account_id in account_ids:
            account = self.get_account(int(account_id))
            if account and account["username"] == username:
                return account

        return None

    def batch_check_usernames(self, usernames: set) -> set:
        """批量检查用户名是否已存在"""
        existing_usernames = set()
        # 获取所有账号ID
        account_ids = self.redis.smembers(self.account_list_key)

        # 批量获取所有账号数据
        accounts = []
        for account_id in account_ids:
            account_key = self._generate_account_key(int(account_id))
            account_data = self.redis.hgetall(account_key)
            if account_data:
                accounts.append(account_data)

        # 检查用户名是否在待检查列表中
        for account in accounts:
            username = account.get("username")
            if username in usernames:
                existing_usernames.add(username)

        return existing_usernames

    def batch_create_accounts(self, accounts: List[tuple]) -> Dict:
        """批量创建账号"""
        imported = 0
        errors = 0
        error_details = []

        try:
            # 使用Redis管道进行批量操作
            pipe = self.redis.pipeline()

            for username, password in accounts:
                try:
                    account_id = self._get_next_id()
                    account_data = {
                        "id": str(account_id),
                        "username": username,
                        "password": password,
                        "status": "1",
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }

                    account_key = self._generate_account_key(account_id)

                    # 使用管道批量设置字段
                    for field, value in account_data.items():
                        pipe.hset(account_key, field, value)

                    # 将账号ID添加到列表
                    pipe.sadd(self.account_list_key, str(account_id))

                    imported += 1
                except Exception as e:
                    errors += 1
                    error_details.append(f"创建账号 {username} 失败: {str(e)}")

            # 执行所有管道命令
            pipe.execute()

        except Exception as e:
            errors += imported
            imported = 0
            error_details.append(f"批量创建账号失败: {str(e)}")

        return {
            "imported": imported,
            "errors": errors,
            "error_details": error_details
        }

# 创建全局实例
account_redis_service = AccountRedisService()
