"""配置管理模块"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """应用配置"""

    # 项目根目录
    BASE_DIR = Path(__file__).parent.parent

    # 通用邮箱配置（支持任意 IMAP 邮箱）
    IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.qq.com")
    IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
    IMAP_USER = os.getenv("IMAP_USER", "")  # 邮箱地址
    IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")  # 密码或授权码

    # 通用 AI API 配置（OpenAI 兼容接口）
    AI_API_KEY = os.getenv("AI_API_KEY", "")
    AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
    AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")

    # 向后兼容：旧变量名作为 fallback
    @classmethod
    def _apply_backward_compatibility(cls):
        """处理旧环境变量名的向后兼容"""
        if not cls.IMAP_USER:
            cls.IMAP_USER = os.getenv("QQ_EMAIL", "")
        if not cls.IMAP_PASSWORD:
            cls.IMAP_PASSWORD = os.getenv("QQ_EMAIL_AUTH_CODE", "")
        if not cls.AI_API_KEY:
            cls.AI_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        # AI_BASE_URL 和 AI_MODEL 仅在使用默认值时才 fallback
        old_base_url = os.getenv("ANTHROPIC_BASE_URL", "")
        if old_base_url:
            cls.AI_BASE_URL = old_base_url
        old_model = os.getenv("ANTHROPIC_MODEL", "")
        if old_model:
            cls.AI_MODEL = old_model

    # 输出目录
    OUTPUT_DIR = BASE_DIR / "output"

    # Newsletter 配置文件
    NEWSLETTERS_CONFIG = BASE_DIR / "config" / "newsletters.yaml"

    # 模板目录
    TEMPLATES_DIR = BASE_DIR / "templates"

    @classmethod
    def validate(cls) -> bool:
        """验证必要配置是否存在"""
        cls._apply_backward_compatibility()
        required = ["IMAP_USER", "IMAP_PASSWORD", "AI_API_KEY"]
        missing = [key for key in required if not getattr(cls, key)]
        if missing:
            raise ValueError(f"缺少必要配置: {', '.join(missing)}")
        return True