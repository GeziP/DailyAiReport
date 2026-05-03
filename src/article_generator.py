"""文章生成模块 - 生成小红书和微信公众号格式文章"""

from typing import Optional
import httpx
from openai import OpenAI

from .config import Config


# 小红书风格提示词
XIAOHONGSHU_SYSTEM_PROMPT = """你是一个专业的小红书内容创作者。你的任务是将 Newsletter 总结改写为小红书风格的文章。

## 核心原则（必须遵守）
**绝对不要精简、缩写、省略任何内容！**
- 原文的每个观点、每个细节都必须完整保留
- 原文的每句话都要呈现，只改变表达方式，不减少信息量
- 原文有10个观点，输出就必须有10个观点
- 原文有500字，输出就不能少于500字

## 小红书文章特点
1. 标题：吸睛、带数字、带情绪词（如"必看"、"干货"、"宝藏"）
2. 内容：emoji 丰富、短段落、重点用【】或加粗标记
3. 结尾：引导互动（点赞、收藏、评论）+ 话题标签

## 输出格式
## 标题
（一个吸睛的标题，不超过20字）

## 正文
（改写后的内容，emoji丰富，段落短小）
**注意：完整保留原文所有观点和细节，一字不漏，只改变表达风格**

## 标签
（5-8个话题标签，如 #AI #科技资讯 #干货分享）"""


# 微信公众号风格提示词
WECHAT_SYSTEM_PROMPT = """你是一个专业的微信公众号内容创作者。你的任务是将 Newsletter 总结改写为公众号风格的文章。

核心原则（必须遵守）

绝对禁止任何形式的精简、缩写、省略！

这是最重要的规则，违反即失败：

- 原文的每个观点、每个细节、每个引用都必须一字不漏完整保留
- 原文有N个段落，输出就必须有N个段落
- 原文有N个观点，输出就必须有N个观点
- 原文有500字，输出就不能少于500字
- 原文的每个引用、数据、人名、产品名都要完整呈现
- 绝对禁止使用"详见"、"等"、"包括但不限于"这类缩写词
- 绝对禁止说"参考来源中有详细内容"这种话 - 必须在正文完整呈现

格式规范（极其重要，必须严格遵守）

禁止使用任何 Markdown 格式标记！具体禁止的符号包括：
- 禁止使用 # 号标题（如 #、##、###、####）
- 禁止使用 ** 加粗（如 **文字**）
- 禁止使用 * 斜体（如 *文字*）
- 禁止使用 --- 分隔线
- 禁止使用 [文字](链接) 这种链接格式
- 禁止使用 > 引用块
- 禁止使用 ``` 代码块

正确的格式是纯文本，使用以下方式组织内容：
- 用换行和空行分隔段落和章节
- 用数字编号（1. 2. 3.）组织列表
- 用「」标注关键术语
- 用""标注引用原话
- 链接直接写 URL，不要用方括号包裹文字
- 章节标题单独一行，不加任何符号前缀

公众号文章特点

1. 标题：专业、信息量大、有深度感
2. 导语：简短概括全文要点
3. 正文：段落适中、排版规范、逻辑清晰
4. 结语：总结升华、引导关注

输出结构

标题
（一个专业的标题，可带副标题）

导语
（2-3句话概括今日要点）

正文
（按主题分块，每块有小标题，小标题单独一行不加任何符号）
完整保留原文所有观点和细节，一字不漏，只改变表达风格

结语
（总结与展望）

参考来源
（列出原文中的所有重要链接）

参考来源格式规则：
- 正文中的引用用数字标记，如「观点来源[1]」
- 末尾参考来源部分格式如下：

  [1] 标题或描述文字
  https://完整链接地址

  [2] 标题或描述文字
  https://完整链接地址

- 每条链接占两行：第一行编号+标题，第二行完整 URL
- URL 直接从行首开始，方便复制"""


# AI Builders 微信公众号专用提示词
BUILDERS_WECHAT_SYSTEM_PROMPT = """你是一个专业的微信公众号内容创作者。你的任务是将 AI Builders 动态总结改写为公众号风格的文章，只调整排版格式，不做任何内容精简。

核心原则（必须遵守）

绝对不要精简、缩写、省略任何内容！
- 原文的每个观点、每个细节都必须完整保留
- 原文的每句话都要呈现，只改变表达方式，不减少信息量
- 原文有10个观点，输出就必须有10个观点
- 原文有1000字，输出就不能少于1000字
- 不要使用缩写，完整呈现每个观点的完整内容
- 人物背景、观点详解、行业关联等内容必须完整保留

格式规范（极其重要，必须严格遵守）

禁止使用任何 Markdown 格式标记！具体禁止的符号包括：
- 禁止使用 # 号标题（如 #、##、###、####）
- 禁止使用 ** 加粗（如 **文字**）
- 禁止使用 * 斜体（如 *文字*）
- 禁止使用 --- 分隔线
- 禁止使用 [文字](链接) 这种链接格式
- 禁止使用 > 引用块
- 禁止使用 ``` 代码块

正确的格式是纯文本，使用以下方式组织内容：
- 用换行和空行分隔段落和章节
- 用数字编号（1. 2. 3.）组织列表
- 用「」标注关键术语
- 用""标注引用原话
- 链接直接写 URL，不要用方括号包裹文字
- 章节标题单独一行，不加任何符号前缀
- 可以使用 emoji 增加可读性

排版设计规则

标题区：
- 主标题格式：AI Builders 周报 | 主话题 + 副话题
- 可在标题中加入 emoji 增加吸引力

导语区：
- 2-3句话概括本周要点
- 重要人物名、公司名、核心概念用「」标注
- 适时加入 emoji

正文区（分节）：
- 每节标题格式：序号 + emoji + 主题，如：01 🚨 供应链安全警报
- 核心事件/观点：用「」标注
- 人物引用：人名 + 完整观点内容，不要缩写
- 重要数据/数字：用「」标注
- 关键术语首次出现：用「」标注，如「智能体」（Agent）
- 每个观点后紧跟来源标记：[1][2]...
- 段落间可适当加入 emoji 分隔，增加可读性

emoji 使用指南（适时添加，不要过度）：
🚨 警示/风险/安全  🤖 AI/Agent  💡 创新/洞察  🔥 热门趋势
💰 投资/商业  📊 数据/报告  🎯 关键突破  ⚡ 效率提升

输出结构示例

AI Builders 周报 | 🚨 供应链警报、🤖 Agent 自主突破与 SaaS 范式转移

本周 AI 领域迎来多重重磅动态 🚨。「Karpathy」警示供应链安全，「Anthropic」推出 Claude Code 自动模式 🤖，「OpenAI」成立基金会聚焦安全 💰。

01 🚨 供应链安全警报

「核心事件」，完整详细说明...[1]

Karpathy 指出："完整观点内容，不要缩写"...[2]

「智能体」（Agent）解释...

影响/意义：完整展开...

02 🤖 Agent 自主突破
...

结语
总结本周动态，展望后续发展

参考来源

[1] Karpathy 谈供应链安全
https://x.com/karpathy/status/xxx

[2] Box CEO 谈 Agent API
https://x.com/levie/status/xxx

再次强调：完整保留原文所有内容，只调整排版格式，不做任何精简！"""


def strip_markdown(text: str) -> str:
    """
    代码级格式清洗兆底：移除残留的 Markdown 格式标记。
    保留纯文本内容，不会破坏 URL 和正常文本。
    """
    import re

    if not text:
        return text

    # 移除标题标记 (# ## ### ####)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # 移除加粗标记 **text** 或 __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)

    # 移除斜体标记 *text* 或 _text_（但不影响 URL 中的下划线）
    text = re.sub(r'(?<!\w)\*([^*\n]+?)\*(?!\w)', r'\1', text)
    text = re.sub(r'(?<!\w)_([^_\n]+?)_(?!\w)', r'\1', text)

    # 移除链接格式 [text](url) -> text url
    text = re.sub(r'\[([^\]]+?)\]\(([^)]+?)\)', r'\1\n\2', text)

    # 移除分隔线 ---
    text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)

    # 移除引用块标记 >
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)

    # 移除代码块标记 ```
    text = re.sub(r'^```[\w]*$', '', text, flags=re.MULTILINE)

    # 移除行内代码标记 `text`
    text = re.sub(r'`([^`]+?)`', r'\1', text)

    # 移除无序列表标记 - 或 *
    text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)

    # 清理多余空行（连续3个以上空行压缩为2个）
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    return text.strip()


class ArticleGenerator:
    """文章生成器 - 生成小红书和微信公众号格式"""

    def __init__(self):
        # 详细完整版本需要更长的超时时间
        http_client = httpx.Client(
            timeout=httpx.Timeout(300.0, connect=30.0)  # 5 分钟超时
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

        user_prompt = f"""请将以下内容改写为{platform}风格的文章。

---

{content}

---

核心要求（必须遵守）：
1. 完整保留原文所有内容，一字不漏
2. 不要精简、缩写、省略任何观点或细节
3. 原文有N个观点，输出就必须有N个观点
4. 只改变表达风格和排版格式，不减少信息量
5. 不要使用缩写词，完整呈现每个观点
6. 禁止使用任何 Markdown 格式标记（不要用 #、**、*、---、[]()、>、``` 等）
7. 使用纯文本格式输出"""

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
                result = response.choices[0].message.content
                # 代码级格式清洗兆底：移除残留的 Markdown 标记
                return strip_markdown(result) if result else None
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

        parts = [f"{date_str} AI Newsletter 每日资讯\n"]

        for summary in summaries:
            parts.append(f"\n{summary['name']}\n")
            parts.append(summary.get('summary', '（无内容）'))

            # 添加链接
            links = summary.get('links', [])
            if links:
                parts.append("\n相关链接：\n")
                for link in links:  # 不限制链接数量
                    parts.append(f"{link['title']}: {link['url']}\n")

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

    def generate_wechat_for_builders(
        self,
        content: str
    ) -> Optional[str]:
        """
        专门为 AI Builders Digest 生成微信公众号风格文章

        使用专门的排版提示词，包括：
        - 关键词、人物名、数据加粗
        - 按主题分节，每节带序号
        - 来源使用脚注格式

        Args:
            content: Builders Digest 原始内容

        Returns:
            微信公众号风格文章内容
        """
        if not content or len(content.strip()) < 50:
            return None

        print("  生成 Builders 微信公众号文章（专用排版）...")

        user_prompt = f"""请将以下 AI Builders 动态内容改写为微信公众号风格的文章。

---

{content}

---

核心要求（必须遵守）：
1. 完整保留原文所有内容，一字不漏
2. 不要精简、缩写、省略任何观点或细节
3. 原文有N个观点，输出就必须有N个观点
4. 原文有N个builder介绍，输出就必须有N个builder介绍
5. 人物背景、观点详解、行业关联等内容必须完整保留
6. 只调整排版格式，不改内容
7. 禁止使用任何 Markdown 格式标记（不要用 #、**、*、---、[]()、>、``` 等）
8. 使用纯文本格式：换行分段、数字编号列表、「」标注术语、""标注引用
9. 可以使用 emoji 增加可读性
10. 排版格式：
    - 标题：AI Builders 周报 | emoji + 主话题 + 副话题
    - 导语：关键词用「」标注，适时加 emoji
    - 正文：按序号分节，如 01 🚨 供应链安全警报
    - 关键术语首次出现用「」标注，如「智能体」（Agent）
    - 来源：脚注格式（编号+标题一行，URL一行）"""

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": BUILDERS_WECHAT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7
                )
                result = response.choices[0].message.content
                return strip_markdown(result) if result else None
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Builders 微信文章生成失败，重试中... ({attempt + 1}/{max_retries})")
                    continue
                print(f"Builders 微信文章生成失败: {type(e).__name__}: {e}")
                return None

    def generate_unified_xiaohongshu(
        self,
        unified_content: str
    ) -> Optional[str]:
        """
        从统一日报内容生成小红书风格文章

        Args:
            unified_content: 融合后的统一日报内容

        Returns:
            小红书风格文章内容
        """
        if not unified_content or len(unified_content.strip()) < 50:
            return None

        print("  生成统一日报小红书文章...")

        user_prompt = f"""请将以下 AI 日报内容改写为小红书风格的文章。

---

{unified_content}

---

核心要求（必须遵守）：
1. 完整保留原文所有内容，一字不漏
2. 不要精简、缩写、省略任何观点或细节
3. 原文有几个部分，输出就必须有几个部分
4. 只改变表达风格（emoji丰富、段落短小、互动引导）
5. 禁止使用任何 Markdown 格式标记（不要用 #、**、*、---、[]()、>、``` 等）
6. 使用纯文本格式：换行分段、数字编号列表、「」标注术语、""标注引用"""

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": XIAOHONGSHU_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.8
                )
                result = response.choices[0].message.content
                return strip_markdown(result) if result else None
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"小红书文章生成失败，重试中... ({attempt + 1}/{max_retries})")
                    continue
                print(f"小红书文章生成失败: {type(e).__name__}: {e}")
                return None

    def generate_unified_wechat(
        self,
        unified_content: str
    ) -> Optional[str]:
        """
        从统一日报内容生成微信公众号风格文章

        Args:
            unified_content: 融合后的统一日报内容

        Returns:
            微信公众号风格文章内容
        """
        if not unified_content or len(unified_content.strip()) < 50:
            return None

        print("  生成统一日报微信公众号文章...")

        user_prompt = f"""请将以下 AI 日报内容改写为微信公众号风格的文章。

---

{unified_content}

---

核心要求（必须遵守）：
1. 完整保留原文所有内容，一字不漏
2. 不要精简、缩写、省略任何观点或细节
3. 原文有几个部分，输出就必须有几个部分
4. 只调整排版格式，不改内容
5. 禁止使用任何 Markdown 格式标记（不要用 #、**、*、---、[]()、>、``` 等）
6. 使用纯文本格式：换行分段、数字编号列表、「」标注术语、""标注引用
7. 排版格式：
   - 标题：AI 日报 | 主话题
   - 导语：关键词用「」标注
   - 正文：按序号分节
   - 来源：脚注格式（编号+标题一行，URL一行）"""

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": WECHAT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7
                )
                result = response.choices[0].message.content
                return strip_markdown(result) if result else None
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"微信公众号文章生成失败，重试中... ({attempt + 1}/{max_retries})")
                    continue
                print(f"微信公众号文章生成失败: {type(e).__name__}: {e}")
                return None