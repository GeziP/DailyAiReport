"""微信公众号日报配图模块（Manus API 版）

解析微信公众号 Markdown 文章的章节结构，
通过 Manus API 为每个主要章节生成配图，
并将图片引用插入到对应位置。

Manus API 调用流程：
1. POST /v2/file.upload  → 获取 upload_url 和 file_id
2. PUT  <upload_url>     → 上传 wechat.md 文件内容
3. POST /v2/task.create  → 创建配图任务，附带 file_id
4. GET  /v2/task.listMessages (轮询) → 等待 stopped 状态
5. 从 assistant_message.attachments 下载图片文件
"""

import re
import time
import json
import os
from typing import Optional
from pathlib import Path

import httpx


# ──────────────────────────────────────────────────────────────────────────────
# Manus API 常量
# ──────────────────────────────────────────────────────────────────────────────

MANUS_API_BASE = "https://api.manus.ai"
MANUS_API_KEY_ENV = "MANUS_API_KEY"

# 轮询间隔（秒）
POLL_INTERVAL = 15
# 最大等待时间（秒）：20 分钟
MAX_WAIT_SECONDS = 1200


# ──────────────────────────────────────────────────────────────────────────────
# 章节解析
# ──────────────────────────────────────────────────────────────────────────────

def _extract_sections(markdown_content: str) -> list[dict]:
    """
    提取 Markdown 文章中的主要章节（## 级别标题）。

    Returns:
        list of {"title": str, "level": int, "line_index": int}
    """
    sections = []
    lines = markdown_content.split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^(#{2,3})\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            # 跳过"参考来源"章节
            if any(kw in title for kw in ["参考来源", "reference", "来源"]):
                continue
            sections.append({
                "title": title,
                "level": level,
                "line_index": i,
            })
    return sections


# ──────────────────────────────────────────────────────────────────────────────
# Manus API 客户端
# ──────────────────────────────────────────────────────────────────────────────

class ManusAPIError(Exception):
    pass


class ManusClient:
    """轻量级 Manus API 客户端"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "x-manus-api-key": api_key,
            "Content-Type": "application/json",
        }
        self.http = httpx.Client(
            timeout=httpx.Timeout(60.0, connect=15.0)
        )

    def _post(self, path: str, body: dict) -> dict:
        url = f"{MANUS_API_BASE}{path}"
        resp = self.http.post(url, headers=self.headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise ManusAPIError(f"API error: {data.get('error', data)}")
        return data

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{MANUS_API_BASE}{path}"
        resp = self.http.get(url, headers=self.headers, params=params or {})
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise ManusAPIError(f"API error: {data.get('error', data)}")
        return data

    def upload_file(self, filename: str, content: bytes) -> str:
        """上传文件，返回 file_id"""
        # 第一步：创建文件记录，获取 upload_url
        data = self._post("/v2/file.upload", {"filename": filename})
        file_id = data["file"]["id"]
        upload_url = data["upload_url"]

        # 第二步：PUT 上传文件内容
        put_resp = self.http.put(
            upload_url,
            content=content,
            headers={"Content-Type": "application/octet-stream"},
        )
        put_resp.raise_for_status()

        print(f"  [Manus] 文件已上传: {filename} (id={file_id})")
        return file_id

    def create_task(self, prompt: str, file_id: str | None = None) -> str:
        """创建任务，返回 task_id"""
        content: list[dict] = [{"type": "text", "text": prompt}]
        if file_id:
            content.append({"type": "file", "file_id": file_id})

        body = {
            "message": {
                "content": content,
            },
            "locale": "zh-CN",
            "interactive_mode": False,
            "hide_in_task_list": True,
        }
        data = self._post("/v2/task.create", body)
        task_id = data["task_id"]
        print(f"  [Manus] 任务已创建: {task_id}")
        return task_id

    def wait_for_completion(self, task_id: str) -> list[dict]:
        """
        轮询任务直到完成，返回所有 assistant_message 中的 attachments。
        """
        elapsed = 0
        while elapsed < MAX_WAIT_SECONDS:
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

            data = self._get(
                "/v2/task.listMessages",
                {"task_id": task_id, "order": "desc", "limit": 50},
            )
            messages = data.get("messages", [])

            # 查找最新的 status_update
            for msg in messages:
                if msg.get("type") == "status_update":
                    status = msg["status_update"]["agent_status"]
                    brief = msg["status_update"].get("brief", "")
                    print(f"  [Manus] 状态: {status} — {brief}")

                    if status == "stopped":
                        # 收集所有 assistant_message 的附件
                        attachments = []
                        for m in messages:
                            if m.get("type") == "assistant_message":
                                attachments.extend(
                                    m["assistant_message"].get("attachments", [])
                                )
                        return attachments

                    elif status == "error":
                        for m in messages:
                            if m.get("type") == "error_message":
                                raise ManusAPIError(
                                    f"任务失败: {m['error_message']['content']}"
                                )
                        raise ManusAPIError("任务失败（未知错误）")

                    break  # 只看最新的 status_update

            print(f"  [Manus] 等待中… ({elapsed}s / {MAX_WAIT_SECONDS}s)")

        raise ManusAPIError(f"任务超时（超过 {MAX_WAIT_SECONDS} 秒）")

    def download_file(self, url: str) -> bytes:
        """下载文件内容"""
        resp = self.http.get(url, timeout=60.0)
        resp.raise_for_status()
        return resp.content


# ──────────────────────────────────────────────────────────────────────────────
# 配图器
# ──────────────────────────────────────────────────────────────────────────────

class WeChatImageInserter:
    """
    微信公众号日报配图器（Manus API 版）。

    职责：
    1. 将微信公众号 Markdown 文章上传给 Manus
    2. 让 Manus 为每个主要章节生成配图
    3. 下载 Manus 生成的图片并保存到 output 目录
    4. 将图片以 Markdown 语法插入到章节标题下方
    """

    def __init__(self):
        api_key = os.environ.get(MANUS_API_KEY_ENV, "")
        if not api_key:
            raise ValueError(
                f"未找到 Manus API Key，请设置环境变量 {MANUS_API_KEY_ENV}"
            )
        self.client = ManusClient(api_key)

    def _build_prompt(self, wechat_content: str, date_str: str) -> str:
        """
        构造发给 Manus 的配图任务提示词。

        Manus 将读取附件中的微信公众号文章，
        识别各主要章节，并为每个章节生成一张横版配图。
        """
        sections = _extract_sections(wechat_content)
        main_sections = [s for s in sections if s["level"] == 2]
        section_list = "\n".join(
            f"  {i+1}. {s['title']}" for i, s in enumerate(main_sections)
        )

        return f"""我附上了一篇 {date_str} 的 AI 日报微信公众号文章（Markdown 格式）。

请为以下 {len(main_sections)} 个主要章节各生成一张配图：

{section_list}

配图要求：
- 风格：简洁的科技感扁平插画，深蓝/紫色渐变背景，无文字水印
- 尺寸：横版（宽:高 ≈ 16:9），适合微信公众号文章插图
- 每张图体现该章节的主题（如"AI 资讯精选"用数字杂志元素，"Builders 动态"用人物构建 AI 的场景等）
- 图片文件按章节顺序命名，如 section-01.png, section-02.png …

请生成所有配图并作为附件返回。"""

    def generate_section_images(
        self,
        wechat_content: str,
        date_str: str,
        output_dir: Path,
    ) -> dict[int, Path]:
        """
        通过 Manus API 为微信公众号文章的各主要章节生成配图。

        Returns:
            {line_index: image_path} 映射
        """
        sections = _extract_sections(wechat_content)
        main_sections = [s for s in sections if s["level"] == 2]

        if not main_sections:
            print("  [配图] 未找到主要章节（## 级别），跳过配图")
            return {}

        print(f"  [配图] 发现 {len(main_sections)} 个主要章节，调用 Manus 生成配图…")

        # 1. 上传 wechat.md 文件
        md_filename = f"{date_str}-wechat.md"
        file_id = self.client.upload_file(
            md_filename,
            wechat_content.encode("utf-8"),
        )

        # 2. 创建配图任务
        prompt = self._build_prompt(wechat_content, date_str)
        task_id = self.client.create_task(prompt, file_id=file_id)

        # 3. 等待任务完成
        print(f"  [配图] 等待 Manus 完成配图（最多 {MAX_WAIT_SECONDS // 60} 分钟）…")
        attachments = self.client.wait_for_completion(task_id)

        # 4. 筛选图片附件
        image_attachments = [
            a for a in attachments
            if a.get("type") == "image" or
               (a.get("content_type", "").startswith("image/")) or
               (a.get("filename", "").lower().endswith((".png", ".jpg", ".jpeg", ".webp")))
        ]

        if not image_attachments:
            print("  [配图] Manus 未返回图片附件")
            return {}

        print(f"  [配图] Manus 返回 {len(image_attachments)} 张图片")

        # 5. 下载并保存图片，按顺序与章节对应
        result: dict[int, Path] = {}
        for idx, (section, attachment) in enumerate(
            zip(main_sections, image_attachments), start=1
        ):
            title = section["title"]
            line_index = section["line_index"]
            url = attachment.get("url", "")

            if not url:
                print(f"    ✗ 章节「{title}」无图片 URL，跳过")
                continue

            try:
                image_data = self.client.download_file(url)
                # 推断扩展名
                orig_name = attachment.get("filename", "")
                ext = Path(orig_name).suffix if orig_name else ".png"
                if not ext:
                    ext = ".png"

                safe_title = re.sub(r"[^\w\u4e00-\u9fff]", "-", title)[:20]
                filename = f"{date_str}-wechat-section-{idx:02d}-{safe_title}{ext}"
                image_path = output_dir / filename

                with open(image_path, "wb") as f:
                    f.write(image_data)

                result[line_index] = image_path
                print(f"    ✓ 已保存: {filename}")
            except Exception as e:
                print(f"    ✗ 章节「{title}」图片下载失败: {e}")

        return result

    def insert_images_into_content(
        self,
        wechat_content: str,
        image_map: dict[int, Path],
        output_dir: Path,
    ) -> str:
        """
        将配图以 Markdown 语法插入到对应章节标题下方。
        """
        if not image_map:
            return wechat_content

        lines = wechat_content.split("\n")
        # 从后往前插入，避免行号偏移
        for line_index in sorted(image_map.keys(), reverse=True):
            image_path = image_map[line_index]
            rel_path = f"./{image_path.name}"
            insert_lines = [
                "",
                f"![配图]({rel_path})",
                "",
            ]
            insert_pos = line_index + 1
            # 跳过已有的空行，避免多余空行
            while insert_pos < len(lines) and lines[insert_pos].strip() == "":
                insert_pos += 1
            lines[insert_pos:insert_pos] = insert_lines

        return "\n".join(lines)

    def process_wechat_article(
        self,
        wechat_content: str,
        date_str: str,
        output_dir: Path,
    ) -> str:
        """
        完整处理流程：通过 Manus 生成配图并插入到微信公众号文章中。

        Args:
            wechat_content: 原始微信公众号 Markdown 文章内容
            date_str: 日期字符串
            output_dir: 输出目录

        Returns:
            插入配图后的 Markdown 内容（失败时返回原始内容）
        """
        print("\n[配图] 开始通过 Manus 为微信公众号日报配图…")

        try:
            image_map = self.generate_section_images(
                wechat_content, date_str, output_dir
            )

            if not image_map:
                print("[配图] 无配图生成，返回原始内容")
                return wechat_content

            enriched_content = self.insert_images_into_content(
                wechat_content, image_map, output_dir
            )

            print(f"[配图] 完成，共插入 {len(image_map)} 张配图")
            return enriched_content

        except Exception as e:
            print(f"[配图] 处理失败: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return wechat_content
