"""
简历构建器模块

用于引导输入模式，将用户填写的表单数据转换为结构化简历。
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class GuidedInputData:
    """引导输入数据结构"""
    # 基本信息
    name: str = ""
    gender: str = ""
    age: Optional[int] = None
    phone: str = ""
    email: str = ""
    location: str = ""
    political_status: str = ""  # 政治面貌

    # 教育背景
    education: List[Dict[str, Any]] = field(default_factory=list)

    # 工作经历
    work_experience: List[Dict[str, Any]] = field(default_factory=list)

    # 项目经历
    projects: List[Dict[str, Any]] = field(default_factory=list)

    # 专业技能
    skills: List[str] = field(default_factory=list)

    # 奖项荣誉
    awards: List[str] = field(default_factory=list)

    # 证书资质
    certificates: List[str] = field(default_factory=list)

    # 自我评价
    self_evaluation: str = ""


class ResumeBuilder:
    """简历构建器 - 引导输入模式"""

    def __init__(self):
        pass

    def build_from_form(self, form_data: Dict[str, Any]) -> str:
        """
        从表单数据构建简历文本

        Args:
            form_data: 表单数据

        Returns:
            str: 简历文本
        """
        data = self._parse_form_data(form_data)
        resume_text = self._build_resume_text(data)
        logger.info(f"简历构建完成: {len(resume_text)} 字符")
        return resume_text

    def build_structured(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从表单数据构建结构化简历

        Args:
            form_data: 表单数据

        Returns:
            Dict: 结构化简历数据
        """
        data = self._parse_form_data(form_data)
        return {
            'basic_info': {
                'name': data.name,
                'gender': data.gender,
                'age': data.age,
                'phone': data.phone,
                'email': data.email,
                'location': data.location,
                'political_status': data.political_status
            },
            'education': data.education,
            'work_experience': data.work_experience,
            'projects': data.projects,
            'skills': data.skills,
            'awards': data.awards,
            'certificates': data.certificates,
            'self_evaluation': data.self_evaluation
        }

    def _parse_form_data(self, form_data: Dict[str, Any]) -> GuidedInputData:
        """解析表单数据"""
        data = GuidedInputData()

        # 基本信息
        data.name = form_data.get('name', '')
        data.gender = form_data.get('gender', '')
        data.age = form_data.get('age')
        data.phone = form_data.get('phone', '')
        data.email = form_data.get('email', '')
        data.location = form_data.get('location', '')
        data.political_status = form_data.get('political_status', '')

        # 教育背景
        self._parse_education(form_data, data)

        # 工作经历
        self._parse_work_experience(form_data, data)

        # 项目经历
        self._parse_projects(form_data, data)

        # 技能
        self._parse_skills(form_data, data)

        # 奖项
        self._parse_awards(form_data, data)

        # 证书
        self._parse_certificates(form_data, data)

        # 自我评价
        data.self_evaluation = form_data.get('self_evaluation', '')

        return data

    def _parse_education(self, form_data: Dict[str, Any], data: GuidedInputData):
        """解析教育背景"""
        edu_count = int(form_data.get('edu_count', 0))
        for i in range(edu_count):
            edu = {
                'school': form_data.get(f'edu_school_{i}', ''),
                'major': form_data.get(f'edu_major_{i}', ''),
                'degree': form_data.get(f'edu_degree_{i}', ''),
                'time': form_data.get(f'edu_time_{i}', '')
            }
            if edu['school']:
                data.education.append(edu)

        if not data.education:
            edu = {
                'school': form_data.get('school', ''),
                'major': form_data.get('major', ''),
                'degree': form_data.get('degree', ''),
                'time': form_data.get('edu_time', '')
            }
            if edu['school']:
                data.education.append(edu)

    def _parse_work_experience(self, form_data: Dict[str, Any], data: GuidedInputData):
        """解析工作经历"""
        work_count = int(form_data.get('work_count', 0))
        for i in range(work_count):
            work = {
                'company': form_data.get(f'work_company_{i}', ''),
                'position': form_data.get(f'work_position_{i}', ''),
                'time': form_data.get(f'work_time_{i}', ''),
                'content': form_data.get(f'work_content_{i}', '')
            }
            if work['company']:
                data.work_experience.append(work)

        if not data.work_experience:
            work = {
                'company': form_data.get('company', ''),
                'position': form_data.get('position', ''),
                'time': form_data.get('work_time', ''),
                'content': form_data.get('work_content', '')
            }
            if work['company']:
                data.work_experience.append(work)

    def _parse_projects(self, form_data: Dict[str, Any], data: GuidedInputData):
        """解析项目经历"""
        proj_count = int(form_data.get('proj_count', 0))
        for i in range(proj_count):
            proj = {
                'name': form_data.get(f'proj_name_{i}', ''),
                'role': form_data.get(f'proj_role_{i}', ''),
                'time': form_data.get(f'proj_time_{i}', ''),
                'content': form_data.get(f'proj_content_{i}', '')
            }
            if proj['name']:
                data.projects.append(proj)

    def _parse_skills(self, form_data: Dict[str, Any], data: GuidedInputData):
        """解析技能"""
        skills_str = form_data.get('skills', '')
        if skills_str:
            for sep in ['\n', '、', '，', ',']:
                if sep in skills_str:
                    data.skills = [s.strip() for s in skills_str.split(sep) if s.strip()]
                    break
            if not data.skills:
                data.skills = [skills_str]

    def _parse_awards(self, form_data: Dict[str, Any], data: GuidedInputData):
        """解析奖项"""
        awards_str = form_data.get('awards', '')
        if awards_str:
            for sep in ['\n', '、', '，', ',']:
                if sep in awards_str:
                    data.awards = [s.strip() for s in awards_str.split(sep) if s.strip()]
                    break
            if not data.awards:
                data.awards = [awards_str]

    def _parse_certificates(self, form_data: Dict[str, Any], data: GuidedInputData):
        """解析证书"""
        cert_str = form_data.get('certificates', '')
        if cert_str:
            for sep in ['\n', '、', '，', ',']:
                if sep in cert_str:
                    data.certificates = [s.strip() for s in cert_str.split(sep) if s.strip()]
                    break
            if not data.certificates:
                data.certificates = [cert_str]

    def _build_resume_text(self, data: GuidedInputData) -> str:
        """构建简历文本"""
        sections = []

        # 基本信息
        sections.append(self._build_basic_info(data))

        # 教育背景
        sections.append(self._build_education(data))

        # 工作经历
        sections.append(self._build_work_experience(data))

        # 项目经历
        sections.append(self._build_projects(data))

        # 专业技能
        sections.append(self._build_skills(data))

        # 奖项荣誉
        sections.append(self._build_awards(data))

        # 证书资质
        sections.append(self._build_certificates(data))

        # 自我评价
        sections.append(self._build_self_evaluation(data))

        return '\n'.join(sections)

    def _build_basic_info(self, data: GuidedInputData) -> str:
        """构建基本信息部分"""
        basic_parts = [data.name]
        if data.gender:
            basic_parts.append(f"性别: {data.gender}")
        if data.age:
            basic_parts.append(f"年龄: {data.age}岁")
        if data.phone:
            basic_parts.append(f"电话: {data.phone}")
        if data.email:
            basic_parts.append(f"邮箱: {data.email}")
        if data.location:
            basic_parts.append(f"现居: {data.location}")
        if data.political_status:
            basic_parts.append(f"政治面貌: {data.political_status}")

        return '\n'.join(basic_parts)

    def _build_education(self, data: GuidedInputData) -> str:
        """构建教育背景部分"""
        if not data.education:
            return ""

        edu_lines = ['\n【教育背景】']
        for edu in data.education:
            line_parts = []
            if edu.get('time'):
                line_parts.append(edu['time'])
            if edu.get('school'):
                line_parts.append(edu['school'])
            if edu.get('major'):
                line_parts.append(edu['major'])
            if edu.get('degree'):
                line_parts.append(f"[{edu['degree']}]")
            edu_lines.append(' | '.join(line_parts))
        return '\n'.join(edu_lines)

    def _build_work_experience(self, data: GuidedInputData) -> str:
        """构建工作经历部分"""
        if not data.work_experience:
            return ""

        work_lines = ['\n【工作经历】']
        for work in data.work_experience:
            header_parts = []
            if work.get('time'):
                header_parts.append(work['time'])
            if work.get('company'):
                header_parts.append(work['company'])
            if work.get('position'):
                header_parts.append(work['position'])
            work_lines.append(' | '.join(header_parts))
            if work.get('content'):
                work_lines.append(work['content'])
        return '\n'.join(work_lines)

    def _build_projects(self, data: GuidedInputData) -> str:
        """构建项目经历部分"""
        if not data.projects:
            return ""

        proj_lines = ['\n【项目经历】']
        for proj in data.projects:
            header_parts = []
            if proj.get('time'):
                header_parts.append(proj['time'])
            if proj.get('name'):
                header_parts.append(proj['name'])
            if proj.get('role'):
                header_parts.append(proj['role'])
            proj_lines.append(' | '.join(header_parts))
            if proj.get('content'):
                proj_lines.append(proj['content'])
        return '\n'.join(proj_lines)

    def _build_skills(self, data: GuidedInputData) -> str:
        """构建专业技能部分"""
        if not data.skills:
            return ""

        return '\n【专业技能】\n' + '、'.join(data.skills)

    def _build_awards(self, data: GuidedInputData) -> str:
        """构建奖项荣誉部分"""
        if not data.awards:
            return ""

        return '\n【奖项荣誉】\n' + '\n'.join(data.awards)

    def _build_certificates(self, data: GuidedInputData) -> str:
        """构建证书资质部分"""
        if not data.certificates:
            return ""

        return '\n【证书资质】\n' + '\n'.join(data.certificates)

    def _build_self_evaluation(self, data: GuidedInputData) -> str:
        """构建自我评价部分"""
        if not data.self_evaluation:
            return ""

        return '\n【自我评价】\n' + data.self_evaluation
