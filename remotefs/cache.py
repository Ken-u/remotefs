"""Metadata cache for RemoteFS."""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """A cached metadata entry."""

    value: Any
    expires_at: float

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        return time.time() > self.expires_at


class MetadataCache:
    """TTL-based metadata cache."""

    def __init__(self, ttl: int = 5):
        self._cache: Dict[str, CacheEntry] = {}
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, or None if missing/expired."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.is_expired():
            del self._cache[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        expires_at = time.time() + (ttl or self.ttl)
        self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    def delete(self, key: str) -> None:
        """Delete key from cache."""
        self._cache.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        """Delete all keys with given prefix."""
        to_delete = [k for k in self._cache if k.startswith(prefix)]
        for key in to_delete:
            del self._cache[key]

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None