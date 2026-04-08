"""
缓存管理器单元测试

测试 core/cache_manager.py — 缓存读写、过期、清理逻辑。
使用 tmpdir 作为缓存目录，无外部依赖。
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from core.cache_manager import CacheManager


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / 'cache'


@pytest.fixture
def cm(cache_dir):
    return CacheManager(cache_dir=str(cache_dir))


@pytest.fixture
def sample_key():
    return '简历内容', '职位描述'


@pytest.fixture
def sample_result():
    return {'status': 'completed', 'score': 85, 'data': [1, 2, 3]}


class TestCacheBasicOperations:
    """缓存基本读写"""

    def test_set_and_get(self, cm, sample_key, sample_result):
        """写入后读取应返回相同值"""
        cm.set(*sample_key, sample_result)
        cached = cm.get(*sample_key)
        assert cached == sample_result

    def test_cache_miss(self, cm, sample_key):
        """未命中的 key 应返回 None"""
        result = cm.get(*sample_key)
        assert result is None
        assert cm.stats['misses'] == 1

    def test_cache_hit(self, cm, sample_key, sample_result):
        """命中后 stats.hits 应增加"""
        cm.set(*sample_key, sample_result)
        cm.get(*sample_key)
        assert cm.stats['hits'] == 1

    def test_overwrite_same_key(self, cm, sample_key):
        """相同 key 覆盖"""
        cm.set(*sample_key, {'v': 1})
        cm.set(*sample_key, {'v': 2})
        result = cm.get(*sample_key)
        assert result == {'v': 2}

    def test_different_keys_independent(self, cm):
        """不同 key 互不影响"""
        cm.set('resume_a', 'jd_a', {'result': 'a'})
        cm.set('resume_b', 'jd_b', {'result': 'b'})
        assert cm.get('resume_a', 'jd_a') == {'result': 'a'}
        assert cm.get('resume_b', 'jd_b') == {'result': 'b'}


class TestCacheDeletion:
    """缓存删除"""

    def test_delete_existing(self, cm, sample_key, sample_result):
        """删除已存在的缓存"""
        cm.set(*sample_key, sample_result)
        assert cm.delete(*sample_key) is True
        assert cm.get(*sample_key) is None

    def test_delete_nonexistent(self, cm, sample_key):
        """删除不存在的缓存"""
        assert cm.delete(*sample_key) is False


class TestCacheExpiry:
    """缓存过期"""

    def test_expired_cache_returns_none(self, cm, sample_key, sample_result):
        """过期缓存应返回 None"""
        cm.set(*sample_key, sample_result)

        # 手动修改缓存文件的时间戳为过期
        cache_key = cm.get_cache_key(*sample_key)
        cache_file = cm.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['timestamp'] = (datetime.now() - timedelta(days=999)).isoformat()
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        result = cm.get(*sample_key)
        assert result is None
        assert cm.stats['evictions'] >= 1


class TestCacheClear:
    """缓存清理"""

    def test_clear_expired(self, cm, cache_dir):
        """clear_expired 只清理过期的"""
        # 创建一个过期缓存
        expired_key = cm.get_cache_key('old_resume', 'old_jd')
        expired_file = cm.cache_dir / f"{expired_key}.json"
        expired_data = {
            'cache_key': expired_key,
            'timestamp': (datetime.now() - timedelta(days=999)).isoformat(),
            'result': {'status': 'old'}
        }
        expired_file.write_text(json.dumps(expired_data), encoding='utf-8')

        # 创建一个未过期缓存
        cm.set('new_resume', 'new_jd', {'status': 'new'})

        cleared = cm.clear_expired()
        assert cleared >= 1
        assert cm.get('new_resume', 'new_jd') is not None  # 未过期的还在

    def test_clear_all(self, cm):
        """clear_all 清空所有缓存"""
        cm.set('a', 'b', {'v': 1})
        cm.set('c', 'd', {'v': 2})
        cm.set('e', 'f', {'v': 3})

        cleared = cm.clear_all()
        assert cleared == 3
        assert cm.get('a', 'b') is None
        assert cm.get('c', 'd') is None
        assert cm.get('e', 'f') is None


class TestCacheStats:
    """缓存统计"""

    def test_stats_after_operations(self, cm):
        """多次操作后统计信息正确"""
        cm.set('r1', 'j1', {'v': 1})  # miss on get
        cm.get('r1', 'j1')            # hit
        cm.get('r2', 'j2')            # miss

        stats = cm.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1  # only the r2/j2 miss (r1/j1 was set, not gotten first)
        assert stats['cache_count'] == 1
        assert stats['hit_rate'] == 0.5

    def test_stats_empty_cache(self, cm):
        """空缓存的统计"""
        stats = cm.get_stats()
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        assert stats['hit_rate'] == 0
        assert stats['cache_count'] == 0


class TestCacheKeyGeneration:
    """缓存键生成"""

    def test_same_input_same_key(self, cm):
        """相同输入生成相同的 key"""
        k1 = cm.get_cache_key('resume', 'jd')
        k2 = cm.get_cache_key('resume', 'jd')
        assert k1 == k2

    def test_different_input_different_key(self, cm):
        """不同输入生成不同的 key"""
        k1 = cm.get_cache_key('resume_a', 'jd_a')
        k2 = cm.get_cache_key('resume_b', 'jd_b')
        assert k1 != k2

    def test_key_is_md5_hex(self, cm):
        """key 应该是 32 位十六进制字符串"""
        key = cm.get_cache_key('test', 'test')
        assert len(key) == 32
        assert all(c in '0123456789abcdef' for c in key)
