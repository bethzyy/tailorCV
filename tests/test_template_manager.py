"""
模板管理器单元测试

测试 core/template_manager.py — 模板提取哈希去重、缓存清理、边界条件、
上传模板、默认模板管理。
使用 mock 隔离文件系统和 python-docx，不依赖真实文件或网络。
"""

import pytest
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# ==================== Fixtures ====================

@pytest.fixture
def tmp_template_dirs(tmp_path):
    """创建临时模板目录结构"""
    dirs = {
        'builtin': tmp_path / 'templates' / 'builtin',
        'uploaded': tmp_path / 'templates' / 'uploaded',
        'extracted': tmp_path / 'templates' / 'extracted',
        'preprocessed': tmp_path / 'templates' / 'preprocessed',
        'previews': tmp_path / 'templates' / 'previews',
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return tmp_path / 'templates', dirs

@pytest.fixture
def mock_db():
    """创建 mock 数据库"""
    return MagicMock()

@pytest.fixture
def mock_detector():
    """创建 mock 结构检测器"""
    return MagicMock()

@pytest.fixture
def tm(tmp_template_dirs, mock_db, mock_detector):
    """工厂 fixture"""
    base_dir, dirs = tmp_template_dirs
    from core.template_manager import TemplateManager

    # Store patches to keep them active
    patches = []
    patches.append(patch('core.template_manager.config'))
    patches.append(patch('core.template_manager.db', mock_db))
    patches.append(patch('core.template_manager.StructureDetector', return_value=mock_detector))
    patches.append(patch.object(TemplateManager, '_init_builtin_templates'))
    patches.append(patch.object(TemplateManager, '_recover_user_templates'))
    for p in patches:
        p.start()

    import core.template_manager as tm_mod
    tm_mod.config.BASE_DIR = base_dir
    tm = TemplateManager()

    yield tm

    for p in patches:
        p.stop()

def _fake_doc():
    """创建 mock Document 对象"""
    doc = MagicMock()
    doc.paragraphs = []
    doc.tables = []
    return doc

# ==================== 1. 模板提取 - 哈希去重测试 ====================

@pytest.mark.unit
class TestExtractHashDedup:
    """extract_template_from_resume 哈希去重逻辑"""

    def test_same_file_same_name_returns_existing(self, tm, mock_db):
        """同文件同名称（不传 name）返回已有模板"""
        content = b'same content for dedup'
        content_hash = hashlib.md5(content).hexdigest()
        existing_tid = content_hash[:16]

        mock_db.get_template_by_hash.return_value = {
            'template_id': existing_tid,
            'name': '',
        }

        tid, msg = tm.extract_template_from_resume(content, 'resume.docx')

        assert tid == existing_tid
        assert '已存在' in msg
        mock_db.delete_template.assert_not_called()

    def test_same_file_different_name_deletes_old(self, tm, mock_db):
        """同文件不同名称：删除旧模板并重新提取"""
        content = b'same content but rename'
        content_hash = hashlib.md5(content).hexdigest()
        old_tid = content_hash[:16]

        mock_db.get_template_by_hash.return_value = {
            'template_id': old_tid,
            'name': '旧名称',
        }

        with patch('core.template_manager.Document', return_value=_fake_doc()), \
             patch('core.template_processor.TemplateProcessor') as mock_tp_cls, \
             patch.object(tm, '_detect_template_structure_from_doc', return_value=(['education'], 0.8)), \
             patch('builtins.open', create=True) as mock_open:

            mock_tp = MagicMock()
            mock_tp.preprocess.return_value = MagicMock(
                success=True,
                template_path='/tmp/preprocessed.docx',
                metadata=MagicMock(variables=['basic_info']),
            )
            mock_tp_cls.return_value = mock_tp

            tid, msg = tm.extract_template_from_resume(content, 'resume.docx', name='新名称')

        mock_db.delete_template.assert_called_once_with(old_tid)
        assert tid == old_tid
        assert msg == ''

    def test_different_file_normal_extract(self, tm, mock_db):
        """不同文件正常提取"""
        content = b'brand new resume content'
        content_hash = hashlib.md5(content).hexdigest()
        new_tid = content_hash[:16]

        mock_db.get_template_by_hash.return_value = None

        with patch('core.template_manager.Document', return_value=_fake_doc()), \
             patch('core.template_processor.TemplateProcessor') as mock_tp_cls, \
             patch.object(tm, '_detect_template_structure_from_doc', return_value=(['work_experience'], 0.85)), \
             patch('builtins.open', create=True) as mock_open:

            mock_tp = MagicMock()
            mock_tp.preprocess.return_value = MagicMock(
                success=True,
                template_path='/tmp/preprocessed.docx',
                metadata=MagicMock(variables=['work_experience']),
            )
            mock_tp_cls.return_value = mock_tp

            tid, msg = tm.extract_template_from_resume(content, 'new_resume.docx')

        mock_db.delete_template.assert_not_called()
        assert tid == new_tid
        assert msg == ''
        mock_db.save_template.assert_called_once()
        saved_data = mock_db.save_template.call_args[0][0]
        assert saved_data['source'] == 'extracted'
        assert saved_data['content_hash'] == content_hash

# ==================== 2. 模板提取 - 缓存清理测试 ====================

@pytest.mark.unit
class TestExtractCacheCleanup:
    """删除旧模板时 preprocessed 文件被清理"""

    def test_preprocessed_file_deleted_on_reextract(self, tm, mock_db):
        """重新提取时，旧 preprocessed 文件被删除"""
        content = b'content for cache cleanup'
        content_hash = hashlib.md5(content).hexdigest()
        old_tid = content_hash[:16]

        mock_db.get_template_by_hash.return_value = {
            'template_id': old_tid,
            'name': '',
        }

        # Create the preprocessed file at the relative path the code uses
        pp_rel = Path('templates/preprocessed') / f'{old_tid}.docx'
        pp_rel.parent.mkdir(parents=True, exist_ok=True)
        pp_rel.write_bytes(b'preprocessed content')
        assert pp_rel.exists()

        try:
            with patch('core.template_manager.Document', return_value=_fake_doc()), \
                 patch('core.template_processor.TemplateProcessor') as mock_tp_cls, \
                 patch.object(tm, '_detect_template_structure_from_doc', return_value=(['education'], 0.8)), \
                 patch('builtins.open', create=True):

                mock_tp = MagicMock()
                mock_tp.preprocess.return_value = MagicMock(
                    success=True,
                    template_path='/tmp/proc.docx',
                    metadata=MagicMock(variables=[]),
                )
                mock_tp_cls.return_value = mock_tp

                tm.extract_template_from_resume(content, 'resume.docx', name='新名称')

            assert not pp_rel.exists()
        finally:
            # Cleanup
            if pp_rel.exists():
                pp_rel.unlink()
class TestExtractBoundaryConditions:
    """extract_template_from_resume 边界条件"""

    def test_empty_filename(self, tm, mock_db):
        """空文件名无扩展名，应被格式检查拒绝"""
        tid, msg = tm.extract_template_from_resume(b'content', '')
        assert tid is None
        assert '.docx' in msg
    def test_unsupported_format_pdf(self, tm, mock_db):
        """不支持的文件格式 PDF"""
        tid, msg = tm.extract_template_from_resume(b'content', 'resume.pdf')
        assert tid is None
        assert '.docx' in msg

    def test_unsupported_format_doc(self, tm, mock_db):
        """不支持的 .txt 格式"""
        tid, msg = tm.extract_template_from_resume(b'content', 'resume.txt')
        assert tid is None
        assert '.docx' in msg

    def test_large_file_extract_no_limit(self, tm, mock_db):
        """extract 不限制文件大小，大文件应正常处理"""
        large_content = b'x' * (6 * 1024 * 1024)
        mock_db.get_template_by_hash.return_value = None
        with patch('core.template_manager.Document', return_value=_fake_doc()), \
             patch('core.template_processor.TemplateProcessor') as mock_tp_cls, \
             patch.object(tm, '_detect_template_structure_from_doc', return_value=(['education'], 0.8)), \
             patch('builtins.open', create=True):
            mock_tp = MagicMock()
            mock_tp.preprocess.return_value = MagicMock(success=True, template_path='/tmp/proc.docx', metadata=MagicMock(variables=[]))
            mock_tp_cls.return_value = mock_tp
            tid, msg = tm.extract_template_from_resume(large_content, 'large.docx')
            assert tid is not None

    def test_low_structure_confidence(self, tm, mock_db):
        """结构置信度过低，返回错误"""
        content = b'poorly structured resume'
        mock_db.get_template_by_hash.return_value = None
        with patch('core.template_manager.Document', return_value=_fake_doc()), \
             patch.object(tm, '_detect_template_structure_from_doc', return_value=(['unknown'], 0.2)):
            tid, msg = tm.extract_template_from_resume(content, 'bad_resume.docx')
        assert tid is None
        assert '置信度' in msg or '结构不清晰' in msg
        mock_db.save_template.assert_not_called()

    def test_confidence_at_threshold(self, tm, mock_db):
        """置信度刚好 0.3（边界值），应允许提取"""
        content = b'borderline confidence'
        mock_db.get_template_by_hash.return_value = None
        with patch('core.template_manager.Document', return_value=_fake_doc()), \
             patch('core.template_processor.TemplateProcessor') as mock_tp_cls, \
             patch.object(tm, '_detect_template_structure_from_doc', return_value=(['education'], 0.3)), \
             patch('builtins.open', create=True):
            mock_tp = MagicMock()
            mock_tp.preprocess.return_value = MagicMock(success=True, template_path='/tmp/proc.docx', metadata=MagicMock(variables=[]))
            mock_tp_cls.return_value = mock_tp
            tid, msg = tm.extract_template_from_resume(content, 'borderline.docx')
        assert tid is not None
        assert msg == ''

# ==================== 4. 模板管理 - 上传模板测试 ====================

@pytest.mark.unit
class TestUploadTemplate:
    """upload_template 测试"""

    def test_normal_upload(self, tm, mock_db):
        """正常上传模板"""
        content = b'valid docx upload content'
        content_hash = hashlib.md5(content).hexdigest()
        expected_tid = content_hash[:16]
        mock_db.get_template_by_hash.return_value = None
        with patch('core.template_manager.Document', return_value=_fake_doc()), \
             patch('core.template_processor.TemplateProcessor') as mock_tp_cls, \
             patch.object(tm, '_detect_template_structure_from_doc', return_value=(['education', 'work_experience'], 0.9)), \
             patch('builtins.open', create=True):
            mock_tp = MagicMock()
            mock_tp.preprocess.return_value = MagicMock(success=True, template_path='/tmp/proc.docx', metadata=MagicMock(variables=['basic_info', 'education']))
            mock_tp_cls.return_value = mock_tp
            tid, msg = tm.upload_template(content, 'my_template.docx', name='我的模板')
        assert tid == expected_tid
        assert msg == ''
        mock_db.save_template.assert_called_once()
        saved = mock_db.save_template.call_args[0][0]
        assert saved['source'] == 'uploaded'
        assert saved['name'] == '我的模板'

    def test_duplicate_upload_returns_existing(self, tm, mock_db):
        """重复上传返回已有模板"""
        content = b'duplicate upload content'
        content_hash = hashlib.md5(content).hexdigest()
        existing_tid = content_hash[:16]
        mock_db.get_template_by_hash.return_value = {'template_id': existing_tid, 'name': '已上传模板'}
        tid, msg = tm.upload_template(content, 'dup_template.docx')
        assert tid == existing_tid
        assert '已存在' in msg
        mock_db.save_template.assert_not_called()

    def test_upload_unsupported_format(self, tm, mock_db):
        """上传不支持的格式"""
        tid, msg = tm.upload_template(b'content', 'template.pdf')
        assert tid is None
        assert '.docx' in msg

    def test_upload_large_file_rejected(self, tm, mock_db):
        """上传超大文件被拒绝"""
        large_content = b'x' * (5 * 1024 * 1024 + 1)
        tid, msg = tm.upload_template(large_content, 'large.docx')
        assert tid is None
        assert '5MB' in msg or '大小' in msg
        mock_db.save_template.assert_not_called()

    def test_upload_5mb_exactly_allowed(self, tm, mock_db):
        """刚好 5MB 应被允许"""
        content = b'x' * (5 * 1024 * 1024)
        mock_db.get_template_by_hash.return_value = None
        with patch('core.template_manager.Document', return_value=_fake_doc()), \
             patch('core.template_processor.TemplateProcessor') as mock_tp_cls, \
             patch.object(tm, '_detect_template_structure_from_doc', return_value=(['education'], 0.8)), \
             patch('builtins.open', create=True):
            mock_tp = MagicMock()
            mock_tp.preprocess.return_value = MagicMock(success=True, template_path='/tmp/proc.docx', metadata=MagicMock(variables=[]))
            mock_tp_cls.return_value = mock_tp
            tid, msg = tm.upload_template(content, 'exactly5mb.docx')
        assert tid is not None

    def test_upload_default_name_from_filename(self, tm, mock_db):
        """不传 name 时使用文件名"""
        content = b'name from filename'
        mock_db.get_template_by_hash.return_value = None
        with patch('core.template_manager.Document', return_value=_fake_doc()), \
             patch('core.template_processor.TemplateProcessor') as mock_tp_cls, \
             patch.object(tm, '_detect_template_structure_from_doc', return_value=(['education'], 0.8)), \
             patch('builtins.open', create=True):
            mock_tp = MagicMock()
            mock_tp.preprocess.return_value = MagicMock(success=True, template_path='/tmp/proc.docx', metadata=MagicMock(variables=[]))
            mock_tp_cls.return_value = mock_tp
            tid, msg = tm.upload_template(content, 'my_resume_template.docx')
        saved = mock_db.save_template.call_args[0][0]
        assert saved['name'] == 'my_resume_template'

    def test_upload_preprocess_failure_fallback(self, tm, mock_db):
        """预处理失败时降级保存"""
        content = b'preprocess will fail'
        content_hash = hashlib.md5(content).hexdigest()
        expected_tid = content_hash[:16]
        mock_db.get_template_by_hash.return_value = None
        with patch('core.template_manager.Document', return_value=_fake_doc()), \
             patch('core.template_processor.TemplateProcessor') as mock_tp_cls, \
             patch.object(tm, '_detect_template_structure_from_doc', return_value=(['education'], 0.7)), \
             patch.object(tm, '_get_template_variables_from_doc', return_value=['basic_info']), \
             patch('builtins.open', create=True):
            mock_tp = MagicMock()
            mock_tp.preprocess.return_value = MagicMock(success=False, error_message='预处理失败')
            mock_tp_cls.return_value = mock_tp
            tid, msg = tm.upload_template(content, 'fallback.docx')
        assert tid == expected_tid
        assert msg == ''
        mock_db.save_template.assert_called_once()
        saved = mock_db.save_template.call_args[0][0]
        assert saved['source'] == 'uploaded'

# ==================== 5. 模板管理 - 默认模板测试 ====================

@pytest.mark.unit
class TestDefaultTemplate:
    """默认模板管理"""

    def test_set_default_template_success(self, tm, mock_db):
        """设置默认模板成功"""
        mock_db.get_template.return_value = {'template_id': 'test_tpl', 'name': '测试模板'}
        mock_db.set_default_template.return_value = True
        result = tm.set_default_template('test_tpl')
        assert result is True
        mock_db.set_default_template.assert_called_once_with('test_tpl')

    def test_set_default_nonexistent_template(self, tm, mock_db):
        """设置不存在的模板返回 False"""
        mock_db.get_template.return_value = None
        result = tm.set_default_template('nonexistent')
        assert result is False
        mock_db.set_default_template.assert_not_called()

    def test_get_default_template(self, tm, mock_db):
        """获取默认模板"""
        expected = {'template_id': 'default_tpl', 'name': '默认模板', 'is_default': True}
        mock_db.get_default_template.return_value = expected
        result = tm.get_default_template()
        assert result == expected
        assert result['is_default'] is True

    def test_get_default_template_none(self, tm, mock_db):
        """没有默认模板时返回 None"""
        mock_db.get_default_template.return_value = None
        result = tm.get_default_template()
        assert result is None

    def test_set_default_clears_previous(self, tm, mock_db):
        """设置新默认模板时清除旧的默认"""
        mock_db.get_template.return_value = {'template_id': 'new_default', 'name': '新默认'}
        mock_db.set_default_template.return_value = True
        tm.set_default_template('new_default')
        mock_db.set_default_template.assert_called_once_with('new_default')

# ==================== 6. 辅助方法测试 ====================

@pytest.mark.unit
class TestHelperMethods:
    """辅助方法测试"""

    def test_get_stats(self, tm, mock_db):
        """get_stats 统计模板数量"""
        mock_db.get_templates.return_value = [
            {'source': 'builtin', 'use_count': 10, 'is_default': True},
            {'source': 'builtin', 'use_count': 5, 'is_default': False},
            {'source': 'uploaded', 'use_count': 3, 'is_default': False},
            {'source': 'extracted', 'use_count': 2, 'is_default': False},
        ]
        stats = tm.get_stats()
        assert stats['total_count'] == 4
        assert stats['builtin_count'] == 2
        assert stats['uploaded_count'] == 1
        assert stats['extracted_count'] == 1
        assert stats['total_use_count'] == 20

    def test_check_compatibility_missing_critical(self, tm, mock_db):
        """兼容性检查：缺少关键章节"""
        mock_db.get_template.return_value = {'template_id': 'tpl1', 'sections': ['basic_info', 'work_experience', 'education']}
        compatible, missing = tm.check_compatibility('tpl1', {'basic_info': {}})
        assert compatible is False
        assert 'work_experience' in missing
        assert 'education' in missing

    def test_check_compatibility_all_present(self, tm, mock_db):
        """兼容性检查：全部关键章节都有"""
        mock_db.get_template.return_value = {'template_id': 'tpl1', 'sections': ['basic_info', 'work_experience', 'education']}
        resume_data = {'basic_info': {'name': 'Test'}, 'work_experience': [{'company': 'Test'}], 'education': [{'school': 'THU'}]}
        compatible, missing = tm.check_compatibility('tpl1', resume_data)
        assert compatible is True
        assert missing == []

    def test_check_compatibility_nonexistent_template(self, tm, mock_db):
        """兼容性检查：模板不存在"""
        mock_db.get_template.return_value = None
        compatible, missing = tm.check_compatibility('nonexistent', {})
        assert compatible is False
        assert '模板不存在' in missing

    def test_delete_template_success(self, tm, mock_db):
        """删除用户上传的模板"""
        mock_db.get_template.return_value = {'template_id': 'user_tpl', 'source': 'uploaded', 'file_path': '/nonexistent/path.docx', 'preview_image': ''}
        mock_db.delete_template.return_value = True
        success, msg = tm.delete_template('user_tpl')
        assert success is True
        assert msg == ''
        mock_db.delete_template.assert_called_once_with('user_tpl')

    def test_delete_builtin_template_rejected(self, tm, mock_db):
        """不能删除内置模板"""
        mock_db.get_template.return_value = {'template_id': 'classic_professional', 'source': 'builtin'}
        success, msg = tm.delete_template('classic_professional')
        assert success is False
        assert '内置' in msg
        mock_db.delete_template.assert_not_called()

    def test_delete_nonexistent_template(self, tm, mock_db):
        """删除不存在的模板"""
        mock_db.get_template.return_value = None
        success, msg = tm.delete_template('ghost')
        assert success is False
        assert '不存在' in msg

    def test_increment_use_count(self, tm, mock_db):
        """增加使用次数"""
        mock_db.increment_template_use_count.return_value = True
        tm.increment_use_count('tpl1')
        mock_db.increment_template_use_count.assert_called_once_with('tpl1')

    def test_get_template(self, tm, mock_db):
        """获取指定模板"""
        expected = {'template_id': 'tpl1', 'name': 'Test'}
        mock_db.get_template.return_value = expected
        result = tm.get_template('tpl1')
        assert result == expected

    def test_get_templates_all(self, tm, mock_db):
        """获取所有模板"""
        mock_db.get_templates.return_value = [{'template_id': 'tpl1'}, {'template_id': 'tpl2'}]
        result = tm.get_templates()
        assert len(result) == 2

    def test_get_templates_by_source(self, tm, mock_db):
        """按来源获取模板"""
        mock_db.get_templates.return_value = [{'template_id': 'builtin_tpl'}]
        result = tm.get_templates(source='builtin')
        mock_db.get_templates.assert_called_once_with(source='builtin')

    def test_get_template_file_success(self, tm, mock_db, tmp_path):
        """获取模板文件内容"""
        test_file = tmp_path / 'test_template.docx'
        test_file.write_bytes(b'template file content')
        mock_db.get_template.return_value = {'template_id': 'tpl1', 'file_path': str(test_file)}
        result = tm.get_template_file('tpl1')
        assert result == b'template file content'

    def test_get_template_file_not_found(self, tm, mock_db):
        """模板文件不存在返回 None"""
        mock_db.get_template.return_value = {'template_id': 'tpl1', 'file_path': '/nonexistent/file.docx'}
        result = tm.get_template_file('tpl1')
        assert result is None

# ==================== 7. TemplateInfo 数据类测试 ====================

@pytest.mark.unit
class TestTemplateInfo:
    """TemplateInfo 数据类"""

    def test_to_dict(self):
        """to_dict 返回完整字典"""
        from core.template_manager import TemplateInfo
        info = TemplateInfo(
            template_id='test_id',
            name='Test Template',
            source='uploaded',
            file_path='/path/to/template.docx',
            content_hash='abc123',
            structure_confidence=0.85,
            sections=['education', 'work_experience'],
            variables=['basic_info'],
            description='A test template',
            tags=['test',],
            use_count=5,
            is_default=False,
        )
        d = info.to_dict()
        assert d['template_id'] == 'test_id'
        assert d['name'] == 'Test Template'
        assert d['source'] == 'uploaded'
        assert d['structure_confidence'] == 0.85
        assert d['sections'] == ['education', 'work_experience']
        assert d['is_default'] is False

    def test_default_values(self):
        """默认值正确"""
        from core.template_manager import TemplateInfo
        info = TemplateInfo(
            template_id='id1',
            name='Name',
            source='builtin',
            file_path='/path.docx',
        )
        assert info.content_hash == ""
        assert info.structure_confidence == 0.0
        assert info.sections == []
        assert info.variables == []
        assert info.description == ""
        assert info.tags == []
        assert info.preview_image == ""
        assert info.use_count == 0
        assert info.is_default is False