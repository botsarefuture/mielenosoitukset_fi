from flask_caching import Cache

cache = Cache(config={
        "CACHE_TYPE": "RedisCache",
        "CACHE_REDIS_HOST": "localhost",   # or your Redis host
        "CACHE_REDIS_PORT": 6379,          # default Redis port
        "CACHE_REDIS_DB": 0,               # default DB
        "CACHE_DEFAULT_TIMEOUT": 600       # 10 minutes
    })