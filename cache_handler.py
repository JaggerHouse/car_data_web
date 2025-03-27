import redis
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

class CacheHandler:
    def __init__(self):
        self.memory_cache: Dict[str, Any] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=True
            )
            logging.info("Redis连接成功")
        except Exception as e:
            logging.warning(f"Redis连接失败，使用内存缓存: {e}")
            self.redis_client = None

    def get_cached_data(self, key: str, ttl: int = 3600) -> Optional[Any]:
        """获取缓存数据"""
        # 如果Redis可用，优先使用Redis
        if self.redis_client:
            try:
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logging.error(f"Redis获取缓存失败: {e}")
        
        # 使用内存缓存
        if key in self.memory_cache:
            if key in self.cache_timestamps:
                if datetime.now() - self.cache_timestamps[key] < timedelta(seconds=ttl):
                    return self.memory_cache[key]
                else:
                    del self.memory_cache[key]
                    del self.cache_timestamps[key]
        return None

    def set_cached_data(self, key: str, data: Any, ttl: int = 3600) -> bool:
        """设置缓存数据"""
        # 如果Redis可用，优先使用Redis
        if self.redis_client:
            try:
                self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(data)
                )
                return True
            except Exception as e:
                logging.error(f"Redis设置缓存失败: {e}")
        
        # 使用内存缓存
        try:
            self.memory_cache[key] = data
            self.cache_timestamps[key] = datetime.now()
            return True
        except Exception as e:
            logging.error(f"内存缓存设置失败: {e}")
            return False

    def generate_cache_key(self, country: str, brand: str, model: str, data_type: str, trend: str) -> str:
        """生成缓存键"""
        return f"car_data:{country}:{brand}:{model}:{data_type}:{trend}"

    def get_brands_models_cache(self, country: str) -> Optional[Dict[str, Any]]:
        """获取品牌和型号缓存"""
        key = f"brands_models:{country}"
        return self.get_cached_data(key, ttl=86400)  # 24小时缓存

    def set_brands_models_cache(self, country: str, data: Dict[str, Any]) -> bool:
        """设置品牌和型号缓存"""
        key = f"brands_models:{country}"
        return self.set_cached_data(key, data, ttl=86400)

    def get_trend_cache(self, country: str, brand: str, model: str, data_type: str, trend: str) -> Optional[Dict[str, Any]]:
        """获取趋势数据缓存"""
        key = self.generate_cache_key(country, brand, model, data_type, trend)
        ttl = 3600 if data_type == "当日" else 86400  # 当日数据1小时缓存，历史数据24小时缓存
        return self.get_cached_data(key, ttl=ttl)

    def set_trend_cache(self, country: str, brand: str, model: str, data_type: str, trend: str, data: Dict[str, Any]) -> bool:
        """设置趋势数据缓存"""
        key = self.generate_cache_key(country, brand, model, data_type, trend)
        ttl = 3600 if data_type == "当日" else 86400
        return self.set_cached_data(key, data, ttl=ttl) 