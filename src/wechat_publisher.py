"""微信公众号发布模块

将微信公众号 Markdown 文章转换为可直接发布的富文本 HTML，
并通过微信公众号 API 将图片上传到素材库、发布草稿。

发布流程：
1. 获取 access_token（WECHAT_APP_ID + WECHAT_APP_SECRET）
2. 上传封面图 → thumb_media_id（永久素材）
3. 上传正文图片 → 微信 CDN URL（uploadimg 接口）
4. Markdown → 微信富文本 HTML（替换图片 src 为微信 CDN URL）
5. 新增草稿（draft.add）→ 返回 media_id
"""

import re
import os
import json
import time
from pathlib import Path
from typing import Optional

import httpx


# ──────────────────────────────────────────────────────────────────────────────
# 微信 API 常量
# ──────────────────────────────────────────────────────────────────────────────

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"

# access_token 缓存（同一进程内复用）
_TOKEN_CACHE: dict = {"token": "", "expires_at": 0.0}


# ──────────────────────────────────────────────────────────────────────────────
# Markdown → 微信富文本 HTML
# ──────────────────────────────────────────────────────────────────────────────

# 微信公众号文章的内联样式（不支持 <style> 标签，需内联）
_ARTICLE_STYLE = (
    "font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', "
    "'Helvetica Neue', Arial, sans-serif; "
    "font-size: 16px; line-height: 1.8; color: #333; "
    "max-width: 100%; word-break: break-word;"
)

_H1_STYLE = (
    "font-size: 22px; font-weight: bold; color: #1a1a1a; "
    "margin: 24px 0 12px; padding-bottom: 8px; "
    "border-bottom: 2px solid #4a90e2;"
)
_H2_STYLE = (
    "font-size: 18px; font-weight: bold; color: #2c2c2c; "
    "margin: 20px 0 10px; padding-left: 10px; "
    "border-left: 4px solid #4a90e2;"
)
_H3_STYLE = (
    "font-size: 16px; font-weight: bold; color: #333; "
    "margin: 16px 0 8px;"
)
_P_STYLE = "margin: 10px 0; line-height: 1.8;"
_IMG_STYLE = (
    "max-width: 100%; height: auto; display: block; "
    "margin: 16px auto; border-radius: 4px;"
)
_BLOCKQUOTE_STYLE = (
    "border-left: 4px solid #ddd; margin: 12px 0; "
    "padding: 8px 16px; color: #666; background: #f9f9f9;"
)
_CODE_STYLE = (
    "background: #f4f4f4; border-radius: 3px; "
    "padding: 2px 6px; font-family: monospace; font-size: 14px;"
)
_PRE_STYLE = (
    "background: #f4f4f4; border-radius: 4px; "
    "padding: 12px 16px; overflow-x: auto; "
    "font-family: monospace; font-size: 13px; line-height: 1.6;"
)
_UL_STYLE = "margin: 8px 0 8px 20px; padding: 0;"
_LI_STYLE = "margin: 4px 0; line-height: 1.8;"
_HR_STYLE = "border: none; border-top: 1px solid #eee; margin: 20px 0;"
_STRONG_STYLE = "font-weight: bold; color: #1a1a1a;"
_EM_STYLE = "font-style: italic; color: #555;"


def markdown_to_wechat_html(markdown_content: str) -> str:
    """
    将 Markdown 转换为微信公众号富文本 HTML。

    特点：
    - 所有样式内联（微信不支持 <style> 标签）
    - 图片保留原 src（后续由 WeChatPublisher 替换为微信 CDN URL）
    - 链接转为纯文本（微信公众号正文不支持外链跳转）
    - 不包含 <html>/<head>/<body> 包装（微信 content 字段只要正文 HTML）
    """
    text = markdown_content

    # ── 预处理：统一换行 ──
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # ── 代码块（先处理，避免内部内容被其他规则误处理）──
    def replace_code_block(m):
        code = m.group(2).strip()
        # HTML 转义
        code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'<pre style="{_PRE_STYLE}"><code>{code}</code></pre>'

    text = re.sub(r"```(\w*)\n?([\s\S]*?)```", replace_code_block, text)

    # ── 行内代码 ──
    text = re.sub(
        r"`([^`]+)`",
        lambda m: f'<code style="{_CODE_STYLE}">{m.group(1)}</code>',
        text,
    )

    # ── 图片（先于链接处理）──
    # ![alt](url) → <img> 保留 src，后续替换
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}" style="{_IMG_STYLE}"/>',
        text,
    )

    # ── 链接转纯文本（微信不支持外链）──
    # [text](url) → text（url）
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f"{m.group(1)}（{m.group(2)}）",
        text,
    )

    # ── 粗体 / 斜体 ──
    text = re.sub(
        r"\*\*\*(.+?)\*\*\*",
        lambda m: f'<strong style="{_STRONG_STYLE}"><em style="{_EM_STYLE}">{m.group(1)}</em></strong>',
        text,
    )
    text = re.sub(
        r"\*\*(.+?)\*\*",
        lambda m: f'<strong style="{_STRONG_STYLE}">{m.group(1)}</strong>',
        text,
    )
    text = re.sub(
        r"\*(.+?)\*",
        lambda m: f'<em style="{_EM_STYLE}">{m.group(1)}</em>',
        text,
    )

    # ── 分割线 ──
    text = re.sub(r"^---+$", f'<hr style="{_HR_STYLE}"/>', text, flags=re.MULTILINE)

    # ── 标题（按级别从高到低处理）──
    text = re.sub(
        r"^### (.+)$",
        lambda m: f'<h3 style="{_H3_STYLE}">{m.group(1).strip()}</h3>',
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"^## (.+)$",
        lambda m: f'<h2 style="{_H2_STYLE}">{m.group(1).strip()}</h2>',
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"^# (.+)$",
        lambda m: f'<h1 style="{_H1_STYLE}">{m.group(1).strip()}</h1>',
        text,
        flags=re.MULTILINE,
    )

    # ── 引用块 ──
    def replace_blockquote(m):
        inner = m.group(1).strip().lstrip("> ").strip()
        return f'<blockquote style="{_BLOCKQUOTE_STYLE}">{inner}</blockquote>'

    text = re.sub(r"^> (.+)$", replace_blockquote, text, flags=re.MULTILINE)

    # ── 无序列表 ──
    # 将连续的 "- item" 行合并为 <ul>
    def replace_list_block(m):
        items_text = m.group(0)
        items = re.findall(r"^[-*] (.+)$", items_text, re.MULTILINE)
        li_tags = "".join(f'<li style="{_LI_STYLE}">{item.strip()}</li>' for item in items)
        return f'<ul style="{_UL_STYLE}">{li_tags}</ul>'

    text = re.sub(r"(^[-*] .+\n?)+", replace_list_block, text, flags=re.MULTILINE)

    # ── 段落：将连续非空行包裹为 <p> ──
    # 先将已有 HTML 块标签之间的空行标记，避免被包裹
    lines = text.split("\n")
    result_lines = []
    para_buffer = []

    block_tags = re.compile(
        r"^<(h[1-6]|ul|ol|li|blockquote|pre|hr|img|p)[^>]*[>/]",
        re.IGNORECASE,
    )

    def flush_para():
        if para_buffer:
            content = " ".join(para_buffer).strip()
            if content:
                result_lines.append(f'<p style="{_P_STYLE}">{content}</p>')
            para_buffer.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_para()
        elif block_tags.match(stripped):
            flush_para()
            result_lines.append(stripped)
        else:
            para_buffer.append(stripped)

    flush_para()

    html_body = "\n".join(result_lines)

    # ── 包装为带样式的 section ──
    return f'<section style="{_ARTICLE_STYLE}">\n{html_body}\n</section>'


# ──────────────────────────────────────────────────────────────────────────────
# 微信公众号 API 客户端
# ──────────────────────────────────────────────────────────────────────────────

class WeChatAPIError(Exception):
    pass


class WeChatClient:
    """微信公众号 API 客户端"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.http = httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0))

    # ── access_token ──────────────────────────────────────────────────────────

    def get_access_token(self) -> str:
        """获取 access_token，优先使用稳定版接口（无需 IP 白名单）"""
        global _TOKEN_CACHE
        if _TOKEN_CACHE["token"] and time.time() < _TOKEN_CACHE["expires_at"] - 60:
            return _TOKEN_CACHE["token"]

        # 优先尝试稳定版接口（POST /cgi-bin/stable_token）
        # 稳定版接口不受 IP 白名单限制，适合 GitHub Actions 等动态 IP 场景
        token, expires_in = self._get_stable_token()
        if not token:
            # 降级到普通接口（需要 IP 白名单）
            token, expires_in = self._get_legacy_token()

        _TOKEN_CACHE["token"] = token
        _TOKEN_CACHE["expires_at"] = time.time() + expires_in
        print(f"  [微信] access_token 已获取（有效期 {expires_in}s）")
        return token

    def _get_stable_token(self) -> tuple[str, int]:
        """稳定版接口获取 access_token（不需要 IP 白名单）"""
        try:
            url = f"{WECHAT_API_BASE}/stable_token"
            resp = self.http.post(url, json={
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
                "force_refresh": False,
            })
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode", 0) == 0 and data.get("access_token"):
                print("  [微信] 使用稳定版接口获取 access_token（无需 IP 白名单）")
                return data["access_token"], data.get("expires_in", 7200)
            print(f"  [微信] 稳定版接口返回错误: {data.get('errcode')} {data.get('errmsg')}，降级到普通接口")
        except Exception as e:
            print(f"  [微信] 稳定版接口调用失败: {e}，降级到普通接口")
        return "", 0

    def _get_legacy_token(self) -> tuple[str, int]:
        """普通接口获取 access_token（需要 IP 白名单）"""
        url = f"{WECHAT_API_BASE}/token"
        resp = self.http.get(url, params={
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret,
        })
        resp.raise_for_status()
        data = resp.json()
        if "errcode" in data and data["errcode"] != 0:
            raise WeChatAPIError(
                f"获取 access_token 失败: errcode={data['errcode']} errmsg={data.get('errmsg')}"
            )
        return data["access_token"], data.get("expires_in", 7200)

    # ── 上传正文图片（uploadimg）────────────────────────────────────────────────

    def upload_article_image(self, image_path: Path) -> str:
        """
        上传正文图片，返回微信 CDN URL。

        使用 /cgi-bin/media/uploadimg 接口：
        - 不占用素材库 100000 张限制
        - 仅支持 jpg/png，大小 < 1MB
        - 返回永久可访问的 mmbiz.qpic.cn URL
        """
        token = self.get_access_token()
        url = f"{WECHAT_API_BASE}/media/uploadimg"

        # 读取图片，如果超过 1MB 需要压缩
        image_data = image_path.read_bytes()
        if len(image_data) > 1024 * 1024:
            image_data = self._compress_image(image_path)

        suffix = image_path.suffix.lower()
        mime_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

        resp = self.http.post(
            url,
            params={"access_token": token},
            files={"media": (image_path.name, image_data, mime_type)},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("errcode", 0) != 0:
            raise WeChatAPIError(
                f"上传正文图片失败: errcode={data['errcode']} errmsg={data.get('errmsg')}"
            )

        cdn_url = data["url"]
        print(f"  [微信] 正文图片已上传: {image_path.name} → {cdn_url}")
        return cdn_url

    def _compress_image(self, image_path: Path) -> bytes:
        """将图片压缩到 1MB 以下（需要 Pillow）"""
        try:
            from PIL import Image
            import io

            img = Image.open(image_path)
            # 转换为 RGB（避免 RGBA 保存为 JPEG 报错）
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            quality = 85
            while quality >= 40:
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality)
                data = buf.getvalue()
                if len(data) <= 1024 * 1024:
                    print(f"  [微信] 图片已压缩（quality={quality}）: {image_path.name}")
                    return data
                quality -= 10

            # 最后尝试缩小尺寸
            w, h = img.size
            img = img.resize((w // 2, h // 2), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70)
            return buf.getvalue()

        except ImportError:
            print("  [微信] Pillow 未安装，无法压缩图片，直接使用原始文件")
            return image_path.read_bytes()

    # ── 上传封面图（永久素材）────────────────────────────────────────────────────

    def upload_thumb_image(self, image_path: Path) -> str:
        """
        上传封面图为永久素材，返回 thumb_media_id。

        使用 /cgi-bin/material/add_material 接口（type=image）。
        """
        token = self.get_access_token()
        url = f"{WECHAT_API_BASE}/material/add_material"

        image_data = image_path.read_bytes()
        if len(image_data) > 1024 * 1024:
            image_data = self._compress_image(image_path)

        suffix = image_path.suffix.lower()
        mime_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

        resp = self.http.post(
            url,
            params={"access_token": token, "type": "image"},
            files={"media": (image_path.name, image_data, mime_type)},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("errcode", 0) != 0:
            raise WeChatAPIError(
                f"上传封面图失败: errcode={data['errcode']} errmsg={data.get('errmsg')}"
            )

        media_id = data["media_id"]
        print(f"  [微信] 封面图已上传: {image_path.name} → media_id={media_id}")
        return media_id

    # ── 新增草稿 ──────────────────────────────────────────────────────────────

    def add_draft(
        self,
        title: str,
        content_html: str,
        thumb_media_id: str,
        author: str = "",
        digest: str = "",
    ) -> str:
        """
        新增草稿，返回 media_id。

        Args:
            title: 文章标题
            content_html: 正文 HTML（图片 src 必须是微信 CDN URL）
            thumb_media_id: 封面图的永久素材 media_id
            author: 作者（可选）
            digest: 摘要（可选，不超过 120 字）

        Returns:
            草稿 media_id
        """
        token = self.get_access_token()
        url = f"{WECHAT_API_BASE}/draft/add"

        body = {
            "articles": [{
                "title": title,
                "author": author,
                "digest": digest[:120] if digest else "",
                "content": content_html,
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }]
        }

        resp = self.http.post(
            url,
            params={"access_token": token},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("errcode", 0) != 0:
            raise WeChatAPIError(
                f"新增草稿失败: errcode={data['errcode']} errmsg={data.get('errmsg')}"
            )

        media_id = data["media_id"]
        print(f"  [微信] 草稿已创建: media_id={media_id}")
        return media_id


# ──────────────────────────────────────────────────────────────────────────────
# 发布器（整合流程）
# ──────────────────────────────────────────────────────────────────────────────

class WeChatPublisher:
    """
    微信公众号发布器。

    完整流程：
    1. Markdown → 微信富文本 HTML
    2. 扫描 HTML 中的本地图片路径，上传到微信素材库，替换为 CDN URL
    3. 上传封面图，获取 thumb_media_id
    4. 调用草稿 API 创建草稿
    """

    def __init__(self):
        app_id = os.environ.get("WECHAT_APP_ID", "")
        app_secret = os.environ.get("WECHAT_APP_SECRET", "")
        if not app_id or not app_secret:
            raise ValueError(
                "未找到微信公众号配置，请设置 WECHAT_APP_ID 和 WECHAT_APP_SECRET"
            )
        self.client = WeChatClient(app_id, app_secret)

    def _extract_title(self, markdown_content: str, date_str: str) -> str:
        """从 Markdown 提取文章标题（第一个 # 标题）"""
        for line in markdown_content.split("\n"):
            m = re.match(r"^#\s+(.+)$", line)
            if m:
                return m.group(1).strip()
        return f"AI 日报 {date_str}"

    def _extract_digest(self, markdown_content: str) -> str:
        """提取摘要（导语部分的前 120 字）"""
        lines = markdown_content.split("\n")
        digest_lines = []
        in_digest = False
        for line in lines:
            stripped = line.strip()
            if re.match(r"^##\s+导语", stripped):
                in_digest = True
                continue
            if in_digest:
                if re.match(r"^##", stripped):
                    break
                if stripped and not stripped.startswith("#"):
                    digest_lines.append(stripped)
        digest = " ".join(digest_lines)
        return digest[:120] if digest else ""

    def _replace_local_images_in_html(
        self,
        html_content: str,
        output_dir: Path,
    ) -> str:
        """
        扫描 HTML 中的 <img src="./xxx.png"> 本地图片引用，
        上传到微信素材库，替换为微信 CDN URL。
        """
        # 匹配本地路径（./xxx 或 相对路径）
        img_pattern = re.compile(r'<img([^>]*?)src="(\./[^"]+|(?!https?://)[^"]+\.(png|jpg|jpeg|webp))"([^>]*?)/?>', re.IGNORECASE)

        upload_cache: dict[str, str] = {}  # 本地路径 → CDN URL

        def replace_img(m):
            prefix_attrs = m.group(1)
            src = m.group(2)
            suffix_attrs = m.group(4)

            # 规范化路径
            clean_src = src.lstrip("./")
            image_path = output_dir / clean_src

            if not image_path.exists():
                print(f"  [微信] 图片文件不存在，跳过: {image_path}")
                return m.group(0)

            # 避免重复上传
            cache_key = str(image_path)
            if cache_key in upload_cache:
                cdn_url = upload_cache[cache_key]
            else:
                try:
                    cdn_url = self.client.upload_article_image(image_path)
                    upload_cache[cache_key] = cdn_url
                except Exception as e:
                    print(f"  [微信] 图片上传失败（{image_path.name}）: {e}，保留原路径")
                    return m.group(0)

            return f'<img{prefix_attrs}src="{cdn_url}"{suffix_attrs}/>'

        return img_pattern.sub(replace_img, html_content)

    def publish_to_draft(
        self,
        markdown_content: str,
        date_str: str,
        output_dir: Path,
        cover_image_path: Optional[Path] = None,
    ) -> Optional[str]:
        """
        将微信公众号 Markdown 文章发布为草稿。

        Args:
            markdown_content: 含配图引用的 Markdown 内容
            date_str: 日期字符串（用于标题）
            output_dir: 输出目录（用于定位本地图片文件）
            cover_image_path: 封面图路径（可选）

        Returns:
            草稿 media_id（失败返回 None）
        """
        print("\n[微信发布] 开始将日报发布为微信公众号草稿…")

        # 1. 提取标题和摘要
        title = self._extract_title(markdown_content, date_str)
        digest = self._extract_digest(markdown_content)
        print(f"  [微信发布] 标题: {title}")

        # 2. Markdown → 微信富文本 HTML
        print("  [微信发布] 转换 Markdown → 微信富文本 HTML…")
        html_content = markdown_to_wechat_html(markdown_content)

        # 3. 上传正文图片，替换为微信 CDN URL
        print("  [微信发布] 上传正文图片到微信素材库…")
        html_content = self._replace_local_images_in_html(html_content, output_dir)

        # 4. 上传封面图
        thumb_media_id = ""
        if cover_image_path and cover_image_path.exists():
            try:
                thumb_media_id = self.client.upload_thumb_image(cover_image_path)
            except Exception as e:
                print(f"  [微信发布] 封面图上传失败: {e}，将使用默认封面")

        if not thumb_media_id:
            # 尝试在 output_dir 中找封面图
            cover_candidates = list(output_dir.glob(f"{date_str}-wechat-cover.*"))
            if cover_candidates:
                try:
                    thumb_media_id = self.client.upload_thumb_image(cover_candidates[0])
                except Exception as e:
                    print(f"  [微信发布] 备用封面图上传失败: {e}")

        if not thumb_media_id:
            print("  [微信发布] 警告：未能获取封面图 media_id，草稿可能无封面")
            # 微信草稿 API 要求 thumb_media_id 必填，无法跳过
            # 此处用占位符，实际会报错，用户需手动配置
            thumb_media_id = "PLACEHOLDER_THUMB_MEDIA_ID"

        # 5. 新增草稿
        try:
            media_id = self.client.add_draft(
                title=title,
                content_html=html_content,
                thumb_media_id=thumb_media_id,
                digest=digest,
            )
            print(f"[微信发布] 草稿发布成功！media_id={media_id}")
            return media_id
        except WeChatAPIError as e:
            print(f"[微信发布] 草稿发布失败: {e}")
            return None
