"""Tests for RemoteFS metadata cache."""

import time
from remotefs.cache import MetadataCache, CacheEntry


def test_cache_set_get():
    """Test basic set and get."""
    cache = MetadataCache(ttl=5)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"


def test_cache_missing_key():
    """Test getting missing key returns None."""
    cache = MetadataCache()
    assert cache.get("nonexistent") is None


def test_cache_expiration():
    """Test cache entry expires after TTL."""
    cache = MetadataCache(ttl=1)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"
    time.sleep(1.1)
    assert cache.get("key1") is None


def test_cache_delete():
    """Test deleting a key."""
    cache = MetadataCache()
    cache.set("key1", "value1")
    cache.delete("key1")
    assert cache.get("key1") is None


def test_cache_delete_prefix():
    """Test deleting keys by prefix."""
    cache = MetadataCache()
    cache.set("/src/file1.py", "content1")
    cache.set("/src/file2.py", "content2")
    cache.set("/tests/test.py", "content3")

    cache.delete_prefix("/src/")

    assert cache.get("/src/file1.py") is None
    assert cache.get("/src/file2.py") is None
    assert cache.get("/tests/test.py") == "content3"


def test_cache_clear():
    """Test clearing all cache entries."""
    cache = MetadataCache()
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.clear()
    assert cache.get("key1") is None
    assert cache.get("key2") is None


def test_cache_exists():
    """Test checking if key exists."""
    cache = MetadataCache(ttl=1)
    cache.set("key1", "value1")
    assert cache.exists("key1") is True
    time.sleep(1.1)
    assert cache.exists("key1") is False