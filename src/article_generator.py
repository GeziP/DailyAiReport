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
（改写后的内容，emoji丰富，段落短小。注意：保留原文所有重要信息，不要遗漏或过度精简）

## 标签
（5-8个话题标签，如 #AI #科技资讯 #干货分享）

重要：必须保留原文的所有核心信息、观点和细节，只改变表达风格，不减少内容量。"""


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
（按主题分块，每块有小标题。注意：保留原文所有重要信息、观点和细节，不要遗漏或过度精简）

## 结语
（总结与展望）

## 参考来源
（列出原文中的所有重要链接，使用脚注格式）

**重要链接格式规则：**
- 微信公众号不支持 markdown 链接语法 `[文字](URL)`
- 正文中的引用用数字标记，如「观点来源[1]」「详见[2]」
- 末尾「参考来源」部分格式如下（注意换行）：

  [1] 标题或描述文字
  https://完整链接地址

  [2] 标题或描述文字
  https://完整链接地址

- 每条链接占两行：第一行编号+标题，第二行完整 URL
- 不同链接之间空一行分隔
- URL 不要有缩进，直接从行首开始（方便复制）

重要：必须保留原文的所有核心信息、观点和细节，只改变表达风格，不减少内容量。"""


class ArticleGenerator:
    """文章生成器 - 生成小红书和微信公众号格式"""

    def __init__(self):
        http_client = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=30.0)  # 增加超时到 2 分钟
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

重要：保留原文所有信息，只改变表达风格，不要精简或遗漏内容。"""

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    # 不限制 max_tokens，让 AI 输出完整内容
                    temperature=0.8
                )
                return response.choices[0].message.content
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"{platform}文章生成失败，重试中... ({attempt + 1}/{max_retries})")
                    continue
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
                for link in links:  # 不限制链接数量
                    parts.append(f"- {link['title']}: {link['url']}\n")

        return "".join(parts)

    def generate_xiaohongshu_from_content(
        self,
        content: str,
        title_prefix: str = "AI 动态"
    ) -> Optional[str]:
        """
        从任意内容生成小红书风格文章

        Args:
            content: 原始内容
            title_prefix: 标题前缀

        Returns:
            小红书风格文章内容
        """
        if not content or len(content.strip()) < 50:
            return None

        print(f"  生成{title_prefix}小红书文章...")
        article = self._generate_article(
            content,
            XIAOHONGSHU_SYSTEM_PROMPT,
            "小红书"
        )

        return article

    def generate_wechat_from_content(
        self,
        content: str,
        title_prefix: str = "AI 动态"
    ) -> Optional[str]:
        """
        从任意内容生成微信公众号风格文章

        Args:
            content: 原始内容
            title_prefix: 标题前缀

        Returns:
            微信公众号风格文章内容
        """
        if not content or len(content.strip()) < 50:
            return None

        print(f"  生成{title_prefix}微信公众号文章...")
        article = self._generate_article(
            content,
            WECHAT_SYSTEM_PROMPT,
            "微信公众号"
        )

        return article