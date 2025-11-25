import os
from flask_caching import Cache

cache = Cache(
    config={
        "CACHE_TYPE": "RedisCache",
        "CACHE_REDIS_HOST": os.getenv("REDIS_HOST", "localhost"),
        "CACHE_REDIS_PORT": int(os.getenv("REDIS_PORT", "6379")),
        "CACHE_REDIS_DB": int(os.getenv("REDIS_DB", "0")),
        "CACHE_DEFAULT_TIMEOUT": int(os.getenv("CACHE_DEFAULT_TIMEOUT", "600")),
    }
)
