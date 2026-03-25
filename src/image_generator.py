"""图片生成模块 - 生成小红书和微信公众号封面图"""

import base64
from typing import Optional
from pathlib import Path
import httpx
from openai import OpenAI

from .config import Config


# 图片生成提示词
XIAOHONGSHU_COVER_PROMPT = """Create a modern, eye-catching vertical cover image for a tech/AI newsletter.
Style: Minimalist, clean design with soft gradients.
Elements: Abstract AI/technology motifs (circuits, neural networks, data streams).
Colors: Professional blue and purple gradient tones.
No text in the image.
Aspect ratio: 3:4 portrait format.
The image should be suitable for a social media cover about AI and technology news."""

WECHAT_COVER_PROMPT = """Create a modern, professional horizontal cover image for a tech/AI newsletter.
Style: Clean, minimalist design with subtle tech elements.
Elements: Abstract geometric shapes representing AI and data.
Colors: Professional blue tones with white accents.
No text in the image.
Aspect ratio: 2.35:1 landscape format.
The image should be suitable for a WeChat Official Account article about AI and technology."""


class ImageGenerator:
    """图片生成器 - 生成小红书和微信公众号封面图"""

    def __init__(self):
        # 图片生成可能使用不同的 API 配置
        api_key = Config.IMAGE_API_KEY or Config.AI_API_KEY
        base_url = Config.IMAGE_BASE_URL or Config.AI_BASE_URL

        http_client = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=30.0)
        )
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client
        )
        self.model = Config.IMAGE_MODEL or "dall-e-3"

    def _generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        platform: str = "unknown"
    ) -> Optional[bytes]:
        """
        生成图片的通用方法

        Args:
            prompt: 图片生成提示词
            size: 图片尺寸
            platform: 平台名称（用于日志）

        Returns:
            图片字节数据，失败返回 None
        """
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.client.images.generate(
                    model=self.model,
                    prompt=prompt,
                    size=size,
                    quality="standard",
                    n=1,
                    response_format="b64_json"  # 返回 base64 编码
                )

                if response.data and len(response.data) > 0:
                    image_b64 = response.data[0].b64_json
                    if image_b64:
                        return base64.b64decode(image_b64)

                return None

            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"{platform}封面图生成失败，重试中... ({attempt + 1}/{max_retries})")
                    continue
                print(f"{platform}封面图生成失败: {type(e).__name__}: {e}")
                return None

        return None

    def generate_xiaohongshu_cover(
        self,
        title: str,
        date_str: str
    ) -> Optional[Path]:
        """
        生成小红书封面图

        Args:
            title: 文章标题（用于生成提示词）
            date_str: 日期字符串

        Returns:
            图片文件路径，失败返回 None
        """
        print("  生成小红书封面图...")

        # 根据标题定制提示词
        custom_prompt = f"{XIAOHONGSHU_COVER_PROMPT}\n\nTheme hint: {title[:50] if title else 'AI and technology'}"

        # DALL-E 3 支持 1024x1792 (接近 3:4)
        image_data = self._generate_image(
            prompt=custom_prompt,
            size="1024x1792",  # 接近 3:4 比例
            platform="小红书"
        )

        if image_data:
            output_path = Config.OUTPUT_DIR / f"{date_str}-xiaohongshu-cover.png"
            with open(output_path, "wb") as f:
                f.write(image_data)
            print(f"    小红书封面图: {output_path}")
            return output_path

        return None

    def generate_wechat_cover(
        self,
        title: str,
        date_str: str
    ) -> Optional[Path]:
        """
        生成微信公众号封面图

        Args:
            title: 文章标题（用于生成提示词）
            date_str: 日期字符串

        Returns:
            图片文件路径，失败返回 None
        """
        print("  生成微信公众号封面图...")

        # 根据标题定制提示词
        custom_prompt = f"{WECHAT_COVER_PROMPT}\n\nTheme hint: {title[:50] if title else 'AI and technology'}"

        # DALL-E 3 支持 1792x1024 (接近 16:9)
        image_data = self._generate_image(
            prompt=custom_prompt,
            size="1792x1024",  # 接近 2.35:1 比例
            platform="微信公众号"
        )

        if image_data:
            output_path = Config.OUTPUT_DIR / f"{date_str}-wechat-cover.png"
            with open(output_path, "wb") as f:
                f.write(image_data)
            print(f"    微信公众号封面图: {output_path}")
            return output_path

        return None