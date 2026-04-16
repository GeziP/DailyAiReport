"""微信公众号日报配图模块

解析微信公众号 Markdown 文章的章节结构，
为每个主要章节生成配图，并将图片引用插入到对应位置。
"""

import re
import base64
from typing import Optional
from pathlib import Path
import httpx
from openai import OpenAI

from .config import Config


# ──────────────────────────────────────────────────────────────────────────────
# 配图提示词模板
# ──────────────────────────────────────────────────────────────────────────────

# 通用 AI 科技风格基底
_BASE_STYLE = (
    "Minimalist flat-design illustration, clean lines, "
    "soft gradient background in deep blue and purple tones, "
    "no text, no watermark, no UI elements, "
    "suitable for WeChat Official Account article."
)

# 各章节专属提示词（按章节关键词匹配）
SECTION_IMAGE_PROMPTS: dict[str, str] = {
    # 今日概览 / 导语
    "overview": (
        "Abstract technology landscape: glowing neural network nodes "
        "connected by light beams, floating data particles, "
        "deep space background. " + _BASE_STYLE
    ),
    # AI Newsletter 精选
    "newsletter": (
        "Open digital newspaper or magazine floating in cyberspace, "
        "pages made of glowing circuits, AI chip in the center, "
        "soft blue light rays. " + _BASE_STYLE
    ),
    # AI Builders 动态
    "builders": (
        "Group of abstract human silhouettes building a glowing AI structure, "
        "gears and code fragments orbiting around them, "
        "warm amber and blue gradient. " + _BASE_STYLE
    ),
    # 新发现的优质来源 / 推荐
    "recommendations": (
        "Glowing compass pointing toward a constellation of stars, "
        "each star representing a knowledge source, "
        "teal and gold color palette. " + _BASE_STYLE
    ),
    # 模型发布 / 技术突破
    "model": (
        "Futuristic AI brain made of interconnected hexagons, "
        "electric sparks, deep blue and cyan gradient. " + _BASE_STYLE
    ),
    # 产品动态 / 商业
    "product": (
        "Abstract product launch: rocket ascending from a circuit board, "
        "colorful light trails, purple and orange gradient. " + _BASE_STYLE
    ),
    # 行业观点 / 分析
    "insight": (
        "Magnifying glass over a glowing data landscape, "
        "bar charts and trend lines made of light, "
        "navy blue and silver tones. " + _BASE_STYLE
    ),
    # 安全 / 风险
    "safety": (
        "Digital shield with lock icon, surrounded by binary code rain, "
        "red and blue warning lights, dark background. " + _BASE_STYLE
    ),
    # 默认通用
    "default": (
        "Abstract AI technology scene: floating geometric shapes, "
        "glowing data streams, soft gradient background. " + _BASE_STYLE
    ),
}

# 章节关键词 → 提示词类别映射
_KEYWORD_MAP: list[tuple[list[str], str]] = [
    (["概览", "导语", "overview", "introduction"], "overview"),
    (["newsletter", "资讯", "精选", "邮件"], "newsletter"),
    (["builder", "动态", "创业", "开发者", "builders"], "builders"),
    (["推荐", "来源", "发现", "recommendation"], "recommendations"),
    (["模型", "model", "发布", "技术", "突破", "research"], "model"),
    (["产品", "product", "商业", "融资", "投资"], "product"),
    (["观点", "分析", "洞察", "insight", "opinion"], "insight"),
    (["安全", "风险", "safety", "risk", "警示"], "safety"),
]


def _select_prompt_for_section(section_title: str) -> str:
    """根据章节标题选择最合适的配图提示词"""
    title_lower = section_title.lower()
    for keywords, category in _KEYWORD_MAP:
        if any(kw in title_lower for kw in keywords):
            return SECTION_IMAGE_PROMPTS[category]
    return SECTION_IMAGE_PROMPTS["default"]


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
        # 匹配 ## 或 ### 标题（排除 #### 及更深层级）
        m = re.match(r"^(#{2,3})\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            # 跳过"参考来源"章节（通常在末尾，不需要配图）
            if any(kw in title for kw in ["参考来源", "reference", "来源"]):
                continue
            sections.append({
                "title": title,
                "level": level,
                "line_index": i,
            })
    return sections


# ──────────────────────────────────────────────────────────────────────────────
# 图片生成
# ──────────────────────────────────────────────────────────────────────────────

class WeChatImageInserter:
    """
    微信公众号日报配图器。

    职责：
    1. 解析微信公众号 Markdown 文章的章节结构
    2. 为每个主要章节（## 级别）生成一张配图
    3. 将图片以 Markdown 语法插入到章节标题下方
    """

    def __init__(self):
        api_key = Config.IMAGE_API_KEY or Config.AI_API_KEY
        base_url = Config.IMAGE_BASE_URL or Config.AI_BASE_URL

        http_client = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=30.0)
        )
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
        )
        self.model = Config.IMAGE_MODEL or "dall-e-3"

    def _generate_image(
        self,
        prompt: str,
        section_title: str,
    ) -> Optional[bytes]:
        """调用图片 API 生成一张图片，返回字节数据。"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.client.images.generate(
                    model=self.model,
                    prompt=prompt,
                    size="1792x1024",   # 微信公众号横版配图
                    quality="standard",
                    n=1,
                    response_format="b64_json",
                )
                if response.data and response.data[0].b64_json:
                    return base64.b64decode(response.data[0].b64_json)
                return None
            except Exception as e:
                if attempt < max_retries - 1:
                    print(
                        f"  [配图] 章节「{section_title}」生成失败，重试 "
                        f"({attempt + 1}/{max_retries})…"
                    )
                    continue
                print(f"  [配图] 章节「{section_title}」生成失败: {type(e).__name__}: {e}")
                return None
        return None

    def generate_section_images(
        self,
        wechat_content: str,
        date_str: str,
        output_dir: Path,
    ) -> dict[int, Path]:
        """
        为微信公众号文章的各主要章节生成配图。

        Args:
            wechat_content: 微信公众号 Markdown 文章内容
            date_str: 日期字符串（用于文件命名）
            output_dir: 图片保存目录

        Returns:
            {line_index: image_path} 映射
        """
        sections = _extract_sections(wechat_content)
        # 只为 ## 级别（level=2）的主要章节配图，避免图片过多
        main_sections = [s for s in sections if s["level"] == 2]

        if not main_sections:
            print("  [配图] 未找到主要章节（## 级别），跳过配图")
            return {}

        print(f"  [配图] 发现 {len(main_sections)} 个主要章节，开始生成配图…")
        result: dict[int, Path] = {}

        for idx, section in enumerate(main_sections, start=1):
            title = section["title"]
            line_index = section["line_index"]

            print(f"  [配图] ({idx}/{len(main_sections)}) 章节：{title}")

            prompt = _select_prompt_for_section(title)
            image_data = self._generate_image(prompt, title)

            if image_data:
                # 文件名：日期-wechat-section-序号.png
                safe_title = re.sub(r"[^\w\u4e00-\u9fff]", "-", title)[:20]
                filename = f"{date_str}-wechat-section-{idx:02d}-{safe_title}.png"
                image_path = output_dir / filename
                with open(image_path, "wb") as f:
                    f.write(image_data)
                result[line_index] = image_path
                print(f"    ✓ 已保存: {filename}")
            else:
                print(f"    ✗ 配图失败，跳过该章节")

        return result

    def insert_images_into_content(
        self,
        wechat_content: str,
        image_map: dict[int, Path],
        output_dir: Path,
    ) -> str:
        """
        将配图以 Markdown 语法插入到对应章节标题下方。

        图片路径使用相对路径（相对于 output 目录），
        便于 Artifact 下载后直接使用。

        Args:
            wechat_content: 原始微信公众号 Markdown 内容
            image_map: {line_index: image_path}
            output_dir: 输出目录（用于计算相对路径）

        Returns:
            插入图片后的 Markdown 内容
        """
        if not image_map:
            return wechat_content

        lines = wechat_content.split("\n")
        # 从后往前插入，避免行号偏移
        for line_index in sorted(image_map.keys(), reverse=True):
            image_path = image_map[line_index]
            # 使用相对路径（仅文件名），因为图片与 md 文件在同一 output 目录
            rel_path = f"./{image_path.name}"
            # 在标题行之后插入：空行 + 图片 + 空行（确保 Markdown 渲染正确）
            insert_lines = [
                "",
                f"![配图]({rel_path})",
                "",
            ]
            # 插入到标题行的下一行（如果下一行已是空行，则跳过空行再插入）
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
        完整处理流程：生成配图并插入到微信公众号文章中。

        Args:
            wechat_content: 原始微信公众号 Markdown 文章内容
            date_str: 日期字符串
            output_dir: 输出目录

        Returns:
            插入配图后的 Markdown 内容（失败时返回原始内容）
        """
        print("\n[配图] 开始为微信公众号日报配图…")

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

            print(
                f"[配图] 完成，共插入 {len(image_map)} 张配图"
            )
            return enriched_content

        except Exception as e:
            print(f"[配图] 处理失败: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return wechat_content
