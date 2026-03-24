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

    # QQ 邮箱配置
    QQ_EMAIL = os.getenv("QQ_EMAIL", "")
    QQ_EMAIL_AUTH_CODE = os.getenv("QQ_EMAIL_AUTH_CODE", "")

    # 阿里云通义千问 Anthropic 兼容 API 配置
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://coding.dashscope.aliyuncs.com/apps/anthropic")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "qwen3.5-plus")

    # IMAP 服务器配置
    IMAP_SERVER = "imap.qq.com"
    IMAP_PORT = 993

    # 输出目录
    OUTPUT_DIR = BASE_DIR / "output"

    # Newsletter 配置文件
    NEWSLETTERS_CONFIG = BASE_DIR / "config" / "newsletters.yaml"

    # 模板目录
    TEMPLATES_DIR = BASE_DIR / "templates"

    @classmethod
    def validate(cls) -> bool:
        """验证必要配置是否存在"""
        required = ["QQ_EMAIL", "QQ_EMAIL_AUTH_CODE", "ANTHROPIC_API_KEY"]
        missing = [key for key in required if not getattr(cls, key)]
        if missing:
            raise ValueError(f"缺少必要配置: {', '.join(missing)}")
        return True