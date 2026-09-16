"""Shared fixed-window quotas. Cache errors fail closed rather than allowing paid calls."""
import hashlib
import hmac
import time
from django.conf import settings
from django.core.cache import cache

class QuotaUnavailable(RuntimeError):
    pass

def hit(bucket: str, limit: int, window: int) -> bool:
    key = f'foodlabel:{bucket}:{int(time.time()) // window}'
    try:
        if cache.add(key, 1, timeout=window + 5):
            return True
        try:
            return cache.incr(key) <= limit
        except ValueError:
            return False
    except Exception as exc:
        raise QuotaUnavailable('Quota service unavailable. Scanning is temporarily paused.') from exc

def client_id(request) -> str:
    # Do not trust client-supplied forwarded-IP headers. Configure your proxy properly.
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    return hmac.new(settings.SECRET_KEY.encode(), ip.encode(), hashlib.sha256).hexdigest()[:24]
