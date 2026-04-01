"""AI 总结模块（OpenAI 兼容接口）"""

from typing import Optional
import httpx
from openai import OpenAI

from .config import Config
from .newsletter_parser import ParsedContent


# 系统提示词
SYSTEM_PROMPT = """你是一个专业的 AI 行业内容编辑。你的任务是从 Newsletter 中筛选重点，像专业编辑一样判断内容价值。

## 核心原则：编辑筛选

**你不是搬运工，是编辑。**

1. **判断价值**：不是所有内容都值得同等关注
2. **筛选重点**：只深入展开真正有价值的内容
3. **说明理由**：每条内容都要回答"读者为什么要关心这个"

## 筛选标准

**值得深入展开的内容：**
- 真正的技术突破或产品创新
- 有数据支撑的行业分析
- 具体可操作的教程（必须给出步骤摘要）
- 重要人物的观点或预测

**一笔带过的内容：**
- 常规产品更新
- 营销性质的内容
- 缺乏具体信息的通知

**完全忽略的内容：**
- 纯广告推销
- 与 AI 无关的内容

## 语言规范

- 统一用中文表达
- 英文术语首次出现时用括号标注，如：基础模型（Foundation Model）
- 人名、公司名、产品名可保留英文

## 输出格式

### 今日必读

[1-3 条真正重要的内容，每条包含：]
- **标题**：简洁有力
- **内容**：具体是什么
- **为什么重要**：读者为什么要关心

### 其他值得关注

[简要列表，每条1-2句话说明]

### 参考来源

[列出原文链接]"""


class AISummarizer:
    """AI 总结器（OpenAI 兼容接口）"""

    def __init__(self):
        # 配置 HTTP 客户端，增加超时时间到 3 分钟
        http_client = httpx.Client(
            timeout=httpx.Timeout(180.0, connect=30.0)
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
        max_tokens: int = 4000
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
        user_prompt = f"""请筛选并总结以下来自「{newsletter_name}」的内容：

---
{content}
---

要求：
1. 像专业编辑一样判断内容价值，只深入展开真正重要的内容
2. 每条内容都要说明"读者为什么要关心这个"
3. 教程类内容必须给出具体步骤摘要
4. 用中文输出，英文术语首次出现时用括号标注"""

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