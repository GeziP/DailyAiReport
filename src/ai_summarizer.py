"""AI 总结模块（OpenAI 兼容接口）"""

from typing import Optional
import httpx
from openai import OpenAI

from .config import Config
from .newsletter_parser import ParsedContent


# 系统提示词
SYSTEM_PROMPT = """你是一个 Newsletter 内容整理者。你的任务是详细呈现所有 Newsletter 的内容，按主题合并整理。

## 核心原则：详细呈现，按主题合并

**详细呈现，不做精简。按主题整合，不按来源分类。**

1. **详细呈现**：原文的每个观点、每个细节、每个引用都必须完整保留
   - 原文有100字，输出就不少于100字
   - 原文的引用、数据、人名、产品名都要保留
   - 不要用"详见"、"等"这类缩写词

2. **按主题合并**：将所有 Newsletter 的内容按主题整合，不要按来源分开
   - 例如：模型发布、产品动态、人员变动、行业观点等
   - 同一主题的内容放在一起，注明来源即可

3. **不做价值判断**：不要说明"为什么重要"，只呈现事实

## 语言规范

- 统一用中文表达
- 英文术语首次出现时用括号标注，如：基础模型（Foundation Model）
- 人名、公司名、产品名可保留英文
- 引用用*斜体*标注，保留原文完整内容

## 输出格式

### 今日概览
[一句话说明本期内容范围，列出2-3个核心主题]

### 主要内容

#### **[主题标题，如：模型发布动态]**

[合并所有Newsletter中关于模型发布的内容，详细展开，引用用*斜体*]

来源：AINews、The AI Break

---

#### **[主题标题，如：产品与人员动态]**

[合并所有Newsletter中关于产品发布、人员变动的内容...]

来源：The AI Break

---

### 其他动态

[如有其他零散内容，完整列出]

### 参考来源

[列出所有原文链接，按Newsletter来源分组]"""


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
        user_prompt = f"""请整理以下来自「{newsletter_name}」的内容：

---
{content}
---

要求：
1. 详细呈现每个内容点，原文有N字就呈现N字，不要精简
2. 不要用"详见"、"等"这类缩写词
3. 保留所有引用、数据、人名、产品名的完整信息
4. 用中文输出，英文术语首次出现时用括号标注
5. 不要说明"为什么重要"或做价值判断"""

        # 不限制 max_tokens，让 AI 输出完整内容
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
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