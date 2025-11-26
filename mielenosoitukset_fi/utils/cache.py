from flask_caching import Cache

from config import Config

cache = Cache(config={
        "CACHE_TYPE": Config.CACHE_TYPE,
        "CACHE_REDIS_HOST": Config.CACHE_REDIS_HOST,
        "CACHE_REDIS_PORT": Config.CACHE_REDIS_PORT,
        "CACHE_REDIS_DB": Config.CACHE_REDIS_DB,
        "CACHE_DEFAULT_TIMEOUT": Config.CACHE_DEFAULT_TIMEOUT
    })