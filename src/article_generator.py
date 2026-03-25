"""文章生成模块 - 生成小红书和微信公众号格式文章"""

from typing import Optional
import httpx
from openai import OpenAI

from .config import Config


# 小红书风格提示词
XIAOHONGSHU_SYSTEM_PROMPT = """你是一个专业的小红书内容创作者。你的任务是将 Newsletter 总结改写为小红书风格的文章。

小红书文章特点：
1. 标题：吸睛、带数字、带情绪词（如"必看"、"干货"、"宝藏"）
2. 内容：emoji 丰富、短段落、重点用【】或加粗标记
3. 结尾：引导互动（点赞、收藏、评论）+ 话题标签

输出格式要求：
## 标题
（一个吸睛的标题，不超过20字）

## 正文
（改写后的内容，emoji丰富，段落短小）

## 标签
（5-8个话题标签，如 #AI #科技资讯 #干货分享）

注意：保持原文核心信息，但用更活泼、更吸引人的方式表达。"""


# 微信公众号风格提示词
WECHAT_SYSTEM_PROMPT = """你是一个专业的微信公众号内容创作者。你的任务是将 Newsletter 总结改写为公众号风格的文章。

公众号文章特点：
1. 标题：专业、信息量大、有深度感
2. 导语：简短概括全文要点
3. 正文：段落适中、排版规范、逻辑清晰
4. 结语：总结升华、引导关注

输出格式要求：
## 标题
（一个专业的标题，可带副标题）

## 导语
（2-3句话概括今日要点）

## 正文
（按主题分块，每块有小标题）

## 结语
（总结与展望）

## 推荐阅读
（列出原文中的重要链接）

注意：保持专业性和可读性的平衡，适合职场人士阅读。"""


class ArticleGenerator:
    """文章生成器 - 生成小红书和微信公众号格式"""

    def __init__(self):
        http_client = httpx.Client(
            timeout=httpx.Timeout(60.0, connect=30.0)
        )
        self.client = OpenAI(
            api_key=Config.AI_API_KEY,
            base_url=Config.AI_BASE_URL,
            http_client=http_client
        )
        self.model = Config.AI_MODEL

    def _generate_article(
        self,
        content: str,
        system_prompt: str,
        platform: str
    ) -> Optional[str]:
        """生成文章的通用方法"""
        if not content or len(content.strip()) < 50:
            return None

        user_prompt = f"""请将以下 Newsletter 总结改写为{platform}风格的文章：

---
{content}
---

请按照要求改写，保持核心信息完整。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=3000,
                temperature=0.8
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"{platform}文章生成失败: {type(e).__name__}: {e}")
            return None

    def generate_xiaohongshu(
        self,
        summaries: list[dict],
        date_str: str
    ) -> Optional[str]:
        """
        生成小红书风格文章

        Args:
            summaries: Newsletter 总结列表
            date_str: 日期字符串

        Returns:
            小红书风格文章内容
        """
        # 合并所有总结
        combined_content = self._combine_summaries(summaries, date_str)
        if not combined_content:
            return None

        print("  生成小红书文章...")
        article = self._generate_article(
            combined_content,
            XIAOHONGSHU_SYSTEM_PROMPT,
            "小红书"
        )

        return article

    def generate_wechat(
        self,
        summaries: list[dict],
        date_str: str
    ) -> Optional[str]:
        """
        生成微信公众号风格文章

        Args:
            summaries: Newsletter 总结列表
            date_str: 日期字符串

        Returns:
            微信公众号风格文章内容
        """
        # 合并所有总结
        combined_content = self._combine_summaries(summaries, date_str)
        if not combined_content:
            return None

        print("  生成微信公众号文章...")
        article = self._generate_article(
            combined_content,
            WECHAT_SYSTEM_PROMPT,
            "微信公众号"
        )

        return article

    def _combine_summaries(
        self,
        summaries: list[dict],
        date_str: str
    ) -> Optional[str]:
        """合并多个 Newsletter 总结"""
        if not summaries:
            return None

        parts = [f"# {date_str} AI Newsletter 每日资讯\n"]

        for summary in summaries:
            parts.append(f"\n## {summary['name']}\n")
            parts.append(summary.get('summary', '（无内容）'))

            # 添加链接
            links = summary.get('links', [])
            if links:
                parts.append("\n相关链接：\n")
                for link in links[:5]:
                    parts.append(f"- {link['title']}: {link['url']}\n")

        return "".join(parts)