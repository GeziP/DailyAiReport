"""AI 总结模块（OpenAI 兼容接口）"""

from typing import Optional
import httpx
from openai import OpenAI

from .config import Config
from .newsletter_parser import ParsedContent


# 系统提示词
SYSTEM_PROMPT = """你是一个专业的 AI 新闻和产品通讯总结助手。你的任务是将 Newsletter 内容进行精炼总结。

总结要求：
1. 保持客观，准确传达原文要点
2. 突出最重要的信息
3. 使用清晰的 Markdown 格式
4. 按主题分类整理内容
5. 提取关键链接和资源
6. 过滤广告内容：忽略明显的商业广告，如卖课、推销产品、促销活动等

输出格式：
### 核心要点
- 列出 3-5 个最重要的要点

### 详细内容
按主题分组，每个主题用简短的段落总结

### 推荐阅读
列出值得深入阅读的文章/链接（如有）

注意：如果内容是产品/职业发展相关而非 AI 技术，按内容实际情况总结即可。"""


class AISummarizer:
    """AI 总结器（OpenAI 兼容接口）"""

    def __init__(self):
        # 配置 HTTP 客户端，增加超时时间
        http_client = httpx.Client(
            timeout=httpx.Timeout(60.0, connect=30.0)
        )
        self.client = OpenAI(
            api_key=Config.AI_API_KEY,
            base_url=Config.AI_BASE_URL,
            http_client=http_client
        )
        self.model = Config.AI_MODEL
        print(f"AI 配置: model={self.model}, base_url={Config.AI_BASE_URL}")

    def summarize(
        self,
        content: str,
        newsletter_name: str,
        max_tokens: int = 2000
    ) -> Optional[str]:
        """
        总结 Newsletter 内容

        Args:
            content: 要总结的内容
            newsletter_name: Newsletter 名称
            max_tokens: 最大输出 token 数

        Returns:
            总结文本，失败返回 None
        """
        if not content or len(content.strip()) < 50:
            return None

        # 构建用户提示
        user_prompt = f"""请总结以下来自「{newsletter_name}」的 Newsletter 内容：

---
{content}
---

请用中文进行总结，保持简洁但信息完整。
注意：请忽略内容中的广告部分（如课程推销、产品促销等），只总结有价值的信息。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"AI 总结失败: {type(e).__name__}: {e}")
            # 打印更多调试信息
            import traceback
            traceback.print_exc()
            return None

    def summarize_parsed_content(
        self,
        parsed: ParsedContent,
        newsletter_name: str
    ) -> Optional[str]:
        """
        总结解析后的 Newsletter 内容

        Args:
            parsed: 解析后的内容
            newsletter_name: Newsletter 名称

        Returns:
            总结文本
        """
        # 组合内容
        content_parts = []

        if parsed.title:
            content_parts.append(f"# {parsed.title}")

        if parsed.main_content:
            content_parts.append(parsed.main_content)

        # 添加链接信息
        if parsed.links:
            content_parts.append("\n## 相关链接")
            for link in parsed.links[:10]:
                content_parts.append(f"- [{link['title']}]({link['url']})")

        full_content = "\n\n".join(content_parts)

        return self.summarize(full_content, newsletter_name)

    def batch_summarize(
        self,
        contents: dict[str, str],
        max_tokens_per_item: int = 2000
    ) -> dict[str, Optional[str]]:
        """
        批量总结多个内容

        Args:
            contents: {newsletter_name: content}
            max_tokens_per_item: 每项最大 token 数

        Returns:
            {newsletter_name: summary}
        """
        results = {}

        for name, content in contents.items():
            print(f"正在总结: {name}")
            summary = self.summarize(content, name, max_tokens_per_item)
            results[name] = summary

        return results