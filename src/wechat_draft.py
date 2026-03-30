"""微信公众号草稿箱模块"""

import os
import time
import httpx
from pathlib import Path
from typing import Optional

from .config import Config


class WechatDraftClient:
    """微信公众号草稿箱客户端"""

    def __init__(self):
        self.app_id = Config.WECHAT_APP_ID
        self.app_secret = Config.WECHAT_APP_SECRET
        self._access_token: Optional[str] = None
        self._token_expire_time: float = 0

    def is_configured(self) -> bool:
        """检查是否已配置微信 AppID 和 Secret"""
        return bool(self.app_id and self.app_secret)

    def should_publish(self) -> bool:
        """检查是否应该发布草稿（只在本地环境发布，GitHub Actions IP 不在白名单）"""
        # GitHub Actions 环境变量存在时不自动发布
        if os.getenv('GITHUB_ACTIONS') == 'true':
            return False
        return self.is_configured()

    def _get_access_token(self) -> Optional[str]:
        """获取 access_token（自动缓存和刷新）"""
        if not self.is_configured():
            return None

        # 如果 token 还有效（提前 5 分钟刷新）
        if self._access_token and time.time() < self._token_expire_time - 300:
            return self._access_token

        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params)
                data = response.json()

                if "access_token" in data:
                    self._access_token = data["access_token"]
                    self._token_expire_time = time.time() + data.get("expires_in", 7200)
                    return self._access_token
                else:
                    print(f"获取 access_token 失败: {data.get('errmsg', data)}")
                    return None
        except Exception as e:
            print(f"获取 access_token 异常: {e}")
            return None

    def upload_image(self, image_path: Path) -> Optional[str]:
        """
        上传图片到微信素材库

        Args:
            image_path: 图片文件路径

        Returns:
            媒体 ID（media_id），用于草稿封面
        """
        access_token = self._get_access_token()
        if not access_token:
            return None

        if not image_path.exists():
            print(f"图片文件不存在: {image_path}")
            return None

        url = "https://api.weixin.qq.com/cgi-bin/material/add_material"
        params = {"access_token": access_token, "type": "image"}

        try:
            with httpx.Client(timeout=60.0) as client:
                with open(image_path, "rb") as f:
                    files = {"media": (image_path.name, f, "image/png")}
                    response = client.post(url, params=params, files=files)
                    data = response.json()

                if "media_id" in data:
                    print(f"  图片上传成功: {data['media_id']}")
                    return data["media_id"]
                else:
                    print(f"  图片上传失败: {data.get('errmsg', data)}")
                    return None
        except Exception as e:
            print(f"  图片上传异常: {e}")
            return None

    def create_draft(
        self,
        title: str,
        content: str,
        cover_media_id: Optional[str] = None,
        author: str = "",
        digest: str = "",
    ) -> Optional[str]:
        """
        创建微信公众号草稿

        Args:
            title: 文章标题
            content: 文章内容（HTML 格式）
            cover_media_id: 封面图片的媒体 ID
            author: 作者
            digest: 摘要（可选，不填则自动截取内容前部分）

        Returns:
            草稿的 media_id
        """
        access_token = self._get_access_token()
        if not access_token:
            return None

        # 将 markdown 内容转换为简单 HTML
        html_content = self._markdown_to_html(content)

        url = "https://api.weixin.qq.com/cgi-bin/draft/add"
        params = {"access_token": access_token}

        # 构建草稿数据
        articles = [{
            "title": title,
            "author": author,
            "content": html_content,
            "thumb_media_id": cover_media_id or "",
            "digest": digest or self._extract_digest(content),
            "content_source_url": "",  # 原文链接（可选）
            "need_open_comment": 0,  # 是否开启评论
        }]

        payload = {"articles": articles}

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, params=params, json=payload)
                data = response.json()

                if "media_id" in data:
                    print(f"  草稿创建成功: {data['media_id']}")
                    return data["media_id"]
                else:
                    print(f"  草稿创建失败: {data.get('errmsg', data)}")
                    return None
        except Exception as e:
            print(f"  草稿创建异常: {e}")
            return None

    def _markdown_to_html(self, content: str) -> str:
        """
        将 markdown 内容转换为微信公众号兼容的 HTML

        微信公众号支持的 HTML 标签有限：
        - 支持: p, br, strong, em, h1-h6, section, blockquote, ul, ol, li
        - 不支持: a（链接）、code、pre 等
        """
        import re

        lines = content.split("\n")
        html_lines = []

        for line in lines:
            # 标题转换
            if line.startswith("## "):
                html_lines.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("### "):
                html_lines.append(f"<h3>{line[4:]}</h3>")
            elif line.startswith("# "):
                html_lines.append(f"<h1>{line[2:]}</h1>")
            # 分隔线
            elif line.strip() == "---":
                html_lines.append("<hr/>")
            # 列表项
            elif line.startswith("- ") or line.startswith("* "):
                html_lines.append(f"<li>{line[2:]}</li>")
            elif re.match(r"^\d+\.\s", line):
                text = re.sub(r"^\d+\.\s", "", line)
                html_lines.append(f"<li>{text}</li>")
            # 空行
            elif not line.strip():
                html_lines.append("<br/>")
            # 引用
            elif line.startswith("> "):
                html_lines.append(f"<blockquote>{line[2:]}</blockquote>")
            # 普通段落
            else:
                # 处理加粗 **text**
                line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
                # 处理斜体 *text* 或 _text_
                line = re.sub(r"\*(.+?)\*", r"<em>\1</em>", line)
                line = re.sub(r"_(.+?)_", r"<em>\1</em>", line)
                # 链接不转换，直接显示为纯文本（微信不支持超链接）
                line = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1: \2", line)
                html_lines.append(f"<p>{line}</p>")

        return "\n".join(html_lines)

    def _extract_digest(self, content: str, max_length: int = 120) -> str:
        """从内容中提取摘要"""
        # 移除 markdown 标记
        text = content.replace("#", "").replace("*", "").replace("-", "")
        text = text.replace("\n", " ").strip()

        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def publish_draft(self, file_path: Path, cover_path: Optional[Path] = None) -> Optional[str]:
        """
        从文件创建草稿的完整流程

        Args:
            file_path: markdown 文件路径
            cover_path: 封面图片路径（可选）

        Returns:
            草稿的 media_id
        """
        if not file_path.exists():
            print(f"文件不存在: {file_path}")
            return None

        # 读取文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 提取标题（第一个 # 标题）
        title = self._extract_title(content)

        # 上传封面图片
        cover_media_id = None
        if cover_path and cover_path.exists():
            cover_media_id = self.upload_image(cover_path)

        # 创建草稿
        return self.create_draft(
            title=title,
            content=content,
            cover_media_id=cover_media_id,
        )

    def _extract_title(self, content: str) -> str:
        """从内容中提取标题"""
        import re
        match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
        if match:
            title = match.group(1).strip()
            # 移除标题中可能的 markdown 标记
            title = title.replace("##", "").strip()
            return title
        return "AI 资讯日报"  # 默认标题