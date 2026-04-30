"""AI 总结模块（OpenAI 兼容接口）"""

from typing import Optional
import httpx
from openai import OpenAI

from .config import Config
from .newsletter_parser import ParsedContent


# 系统提示词
SYSTEM_PROMPT = """你是一个 Newsletter 内容整理者。你的任务是深入、详尽地呈现所有 Newsletter 的内容，按主题合并整理。

## 核心原则：深入展开，按主题合并

深入展开每个话题，不做精简。按主题整合，不按来源分类。

1. 深入展开：原文的每个观点、每个细节、每个引用都必须完整保留，并进一步展开
   - 原文有100字，输出应该有150-200字（增加背景补充和技术解读）
   - 原文的引用、数据、人名、产品名都要保留
   - 不要用"详见"、"等"这类缩写词
   - 每个主题必须包含：事件背景、核心内容、技术细节、关键数据、行业影响

2. 技术细节不能省略：
   - 模型发布：必须包含模型名称、参数规模、基准测试结果、与竞品对比、定价等
   - 产品更新：必须包含新功能详细描述、使用场景、与旧版对比
   - 融资/商业：必须包含金额、估值、投资方、业务方向
   - 研究/论文：必须包含研究方法、核心发现、实验数据

3. 按主题合并：将所有 Newsletter 的内容按主题整合，不要按来源分开
   - 例如：模型发布、产品动态、人员变动、行业观点等
   - 同一主题的内容放在一起，注明来源即可

4. 不做价值判断：不要说明"为什么重要"，只呈现事实

## 语言规范

- 统一用中文表达
- 英文术语首次出现时用括号标注，如：基础模型（Foundation Model）
- 人名、公司名、产品名可保留英文
- 引用用引号标注，保留原文完整内容

## 格式规范（极其重要，必须严格遵守）

禁止使用任何 Markdown 格式标记！具体禁止的符号包括：
- 禁止使用 # 号标题（如 #、##、###、####）
- 禁止使用 ** 加粗（如 **文字**）
- 禁止使用 * 斜体（如 *文字*）
- 禁止使用 --- 分隔线
- 禁止使用 [文字](链接) 这种链接格式
- 禁止使用 > 引用块
- 禁止使用 ``` 代码块

正确的格式是纯文本，使用以下方式组织内容：
- 用换行和空行分隔段落
- 用数字编号（1. 2. 3.）组织列表
- 用「」标注关键术语
- 用""标注引用原话
- 链接直接写 URL，不要用方括号包裹
- 主题标题单独一行，不加任何符号前缀

## 输出结构示例

今日概览
一句话说明本期内容范围，列出2-3个核心主题

主要内容

模型发布动态

背景：简要说明该主题的行业背景

核心事实：发生了什么，谁做了什么
技术细节：具体的技术参数、架构、方法
关键数据：性能指标、金额、规模等具体数字
引用原文：重要人物的原话用""呈现

来源：AINews、The AI Break

产品与人员动态

背景：...

合并所有Newsletter中关于产品发布、人员变动的内容，深入展开...

来源：The AI Break

其他动态

如有其他零散内容，完整列出

参考来源

按Newsletter来源分组列出链接，每条格式为：
[编号] 标题或描述
链接URL"""


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
        user_prompt = f"""请深入整理以下来自「{newsletter_name}」的内容：

---
{content}
---

要求：
1. 深入展开每个内容点，原文有N字就至少呈现N字，并补充背景和技术解读
2. 不要用"详见"、"等"这类缩写词
3. 保留所有引用、数据、人名、产品名的完整信息
4. 技术细节必须完整呈现：模型参数、基准测试分数、定价、架构特点等
5. 重要人物的原话必须完整引用，不要概括
6. 用中文输出，英文术语首次出现时用括号标注
7. 不要说明"为什么重要"或做价值判断
8. 禁止使用任何 Markdown 格式（不要用 #、**、*、---、[]() 等标记符号）
9. 使用纯文本格式：换行分段、数字编号列表、""标注引用、「」标注术语"""

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
            content_parts.append(f"标题: {parsed.title}")

        if parsed.main_content:
            content_parts.append(parsed.main_content)

        # 添加链接信息
        if parsed.links:
            content_parts.append("\n相关链接")
            for link in parsed.links[:10]:
                content_parts.append(f"- {link['title']}: {link['url']}")

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
