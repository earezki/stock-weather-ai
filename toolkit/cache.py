import os
import json
import time
import functools
import logging

from options import options

from joblib import Memory

memory = Memory(location=options['cache_dir'], verbose=0)
logger = logging.getLogger(__name__)

def timestamp_key(ttl):
    return int(time.time() // ttl)

def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def _load_cache(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None

def _save_cache(path, payload):
    with open(path, "w") as f:
        json.dump(payload, f)

def _is_valid(cache_obj, ttl):
    try:
        ts = time.strptime(cache_obj["timestamp"], "%Y-%m-%d %H:%M:%S")
        return time.time() - time.mktime(ts) < ttl
    except Exception:
        return False

def file_cache(cache_name=None, ttl=None, cache_dir=None):
    """
    Decorator to cache function return value to a JSON file.
    - cache_name: str or callable(args, kwargs) -> str. If None uses func.__name__.
    - ttl: seconds. If None uses options['cache_duration'].
    - cache_dir: directory. If None uses options['cache_dir'].
    Note: cached value must be JSON-serializable.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = cache_name(args, kwargs) if callable(cache_name) else (cache_name or func.__name__)
            dirpath = cache_dir or options.get("cache_dir", ".")
            _ensure_dir(dirpath)
            cache_file = os.path.join(dirpath, f"{name}.json")
            effective_ttl = ttl if ttl is not None else options.get("cache_duration", 3600)

            cached = _load_cache(cache_file)
            if cached and _is_valid(cached, effective_ttl):
                logger.info(f"Using cached data from {cache_file}")
                return cached.get("value")

            result = func(*args, **kwargs)

            try:
                payload = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "value": result}
                _save_cache(cache_file, payload)
            except Exception:
                # fail silently on save errors
                pass

            return result
        return wrapper
    return decorator