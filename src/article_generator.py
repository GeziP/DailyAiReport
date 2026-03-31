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


# AI Builders 微信公众号专用提示词
BUILDERS_WECHAT_SYSTEM_PROMPT = """你是一个专业的微信公众号内容创作者。你的任务是将 AI Builders 动态总结改写为公众号风格的文章，并设计专业的排版格式。

## 排版设计规则

### 标题区
- 主标题格式：「AI Builders 周报 | 主话题 + 副话题」
- 示例：「AI Builders 周报 | 供应链警报、Agent 自主突破与 SaaS 范式转移」

### 导语区
- 2-3句话概括本周要点
- **关键词加粗**：重要人物名、公司名、核心概念要加粗
- 示例：本周 AI 领域迎来多重重磅动态。**Karpathy** 警示供应链安全，**Anthropic** 推出 Claude Code 自动模式，**OpenAI** 成立基金会聚焦安全。

### 正文区（分节）
- 每节标题格式：序号 + 主题 + 可选 emoji，如「### 01 供应链安全警报 ⚠️」
- 核心事件/观点：**加粗处理**
- 人物引用：**加粗名字** + 观点内容，如「**Karpathy 指出**：简单功能应直接用 LLM 生成代码。」
- 重要数据/数字：**加粗**，如「**100倍**」「**10亿美元**」
- 每个观点后紧跟来源标记：[1][2]...

### 内容呈现规则
1. **完整保留信息**：不要过度精简，每个观点要完整呈现
2. **分节清晰**：按主题分节，每节聚焦一个话题
3. **人物背景**：首次提及人物时简要介绍其身份
4. **观点展开**：不仅说结论，还要说明论证过程和影响
5. **来源标记**：每个观点都要有来源标记 [1][2]...

### 来源区（脚注格式）
```
## 参考来源

[1] Karpathy 谈供应链安全
https://x.com/karpathy/status/xxx

[2] Box CEO 谈 Agent API
https://x.com/levie/status/xxx

[3] Claude Code 自动模式发布
https://x.com/claudeai/status/xxx
```

## 输出格式

## 标题
（按规则设计的标题）

## 导语
（2-3句话，关键词加粗）

## 正文

### 01 [主题标题] [可选emoji]

**[核心事件/观点]**，详细说明...[1]

**[人物名] 指出**：完整观点内容...[2]

影响/意义：...

### 02 [主题标题] [可选emoji]
...

## 结语
（总结本周动态，展望后续发展）

## 参考来源
（按脚注格式列出所有来源）

注意：必须保留原文的所有核心信息、观点和细节，只改变表达风格和排版格式。"""


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

重要要求：
1. 使用专门的排版格式（标题、导语、正文分节、结语、参考来源）
2. 关键词、人物名、重要数据用 **加粗** 标记
3. 每节标题使用序号格式如「01 供应链安全警报」
4. 每个观点后标注来源标记 [1][2]...
5. 参考来源使用脚注格式（编号+标题一行，URL一行）
6. 完整保留原文所有信息，不要精简"""

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