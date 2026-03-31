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

## 核心原则（必须遵守）
**绝对不要精简、缩写、省略任何内容！**
- 原文的每个观点、每个细节都必须完整保留
- 原文的每句话都要呈现，只改变表达方式，不减少信息量
- 原文有10个观点，输出就必须有10个观点
- 原文有500字，输出就不能少于500字
- 不要使用缩写，完整呈现每个观点

## 公众号文章特点
1. 标题：专业、信息量大、有深度感
2. 导语：简短概括全文要点
3. 正文：段落适中、排版规范、逻辑清晰
4. 结语：总结升华、引导关注

## 输出格式
## 标题
（一个专业的标题，可带副标题）

## 导语
（2-3句话概括今日要点）

## 正文
（按主题分块，每块有小标题）
**注意：完整保留原文所有观点和细节，一字不漏，只改变表达风格**

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
- URL 不要有缩进，直接从行首开始（方便复制）"""


# AI Builders 微信公众号专用提示词
BUILDERS_WECHAT_SYSTEM_PROMPT = """你是一个专业的微信公众号内容创作者。你的任务是将 AI Builders 动态总结改写为公众号风格的文章，只调整排版格式，不做任何内容精简。

## 核心原则（必须遵守）
**绝对不要精简、缩写、省略任何内容！**
- 原文的每个观点、每个细节都必须完整保留
- 原文的每句话都要呈现，只改变表达方式，不减少信息量
- 原文有10个观点，输出就必须有10个观点
- 原文有1000字，输出就不能少于1000字
- 不要使用缩写，完整呈现每个观点的完整内容
- 人物背景、观点详解、行业关联等内容必须完整保留

## 排版设计规则（只调整格式，不改内容）

### 标题区
- 主标题格式：「AI Builders 周报 | 主话题 + 副话题」
- 示例：「AI Builders 周报 | 供应链警报、Agent 自主突破与 SaaS 范式转移」

### 导语区
- 2-3句话概括本周要点
- **关键词加粗**：重要人物名、公司名、核心概念要加粗
- 示例：本周 AI 领域迎来多重重磅动态。**Karpathy** 警示供应链安全，**Anthropic** 推出 Claude Code 自动模式，**OpenAI** 成立基金会聚焦安全。

### 正文区（分节）
- 每节标题格式：序号 + 主题，如「### 01 供应链安全警报」
- 核心事件/观点：**加粗处理**
- 人物引用：**加粗名字** + 完整观点内容，不要缩写
- 重要数据/数字：**加粗**
- 每个观点后紧跟来源标记：[1][2]...

### 来源区（脚注格式）
```
## 参考来源

[1] Karpathy 谈供应链安全
https://x.com/karpathy/status/xxx

[2] Box CEO 谈 Agent API
https://x.com/levie/status/xxx
```

## 输出格式

## 标题
（按规则设计的标题）

## 导语
（2-3句话，关键词加粗）

## 正文

### 01 [主题标题]

**[核心事件/观点]**，完整详细说明...[1]

**[人物名] 指出**：完整观点内容，不要缩写...[2]

影响/意义：完整展开...

### 02 [主题标题]
...

## 结语
（总结本周动态，展望后续发展）

## 参考来源
（按脚注格式列出所有来源）

**再次强调：完整保留原文所有内容，只调整排版格式，不做任何精简！**"""


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

**核心要求（必须遵守）：**
1. 完整保留原文所有内容，一字不漏
2. 不要精简、缩写、省略任何观点或细节
3. 原文有N个观点，输出就必须有N个观点
4. 只改变表达风格和排版格式，不减少信息量
5. 不要使用缩写词，完整呈现每个观点"""

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

**核心要求（必须遵守）：**
1. 完整保留原文所有内容，一字不漏
2. 不要精简、缩写、省略任何观点或细节
3. 原文有N个观点，输出就必须有N个观点
4. 原文有N个builder介绍，输出就必须有N个builder介绍
5. 人物背景、观点详解、行业关联等内容必须完整保留
6. 只调整排版格式（加粗、分节、来源标记），不改内容
7. 使用专门的排版格式：
   - 标题：AI Builders 周报 | 主话题 + 副话题
   - 导语：关键词加粗
   - 正文：按序号分节，如 01 供应链安全警报
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
                return response.choices[0].message.content
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

**核心要求（必须遵守）：**
1. 完整保留原文所有内容，一字不漏
2. 不要精简、缩写、省略任何观点或细节
3. 原文有几个部分，输出就必须有几个部分
4. 只改变表达风格（emoji丰富、段落短小、互动引导）
5. 保留所有关键字加粗"""

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
                return response.choices[0].message.content
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

**核心要求（必须遵守）：**
1. 完整保留原文所有内容，一字不漏
2. 不要精简、缩写、省略任何观点或细节
3. 原文有几个部分，输出就必须有几个部分
4. 只调整排版格式（分节、加粗、来源脚注），不改内容
5. 使用专业的排版格式：
   - 标题：AI 日报 | 主话题
   - 导语：关键词加粗
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
                return response.choices[0].message.content
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"微信公众号文章生成失败，重试中... ({attempt + 1}/{max_retries})")
                    continue
                print(f"微信公众号文章生成失败: {type(e).__name__}: {e}")
                return None