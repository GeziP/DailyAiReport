"""AI Builders Digest 模块 - 从 follow-builders skill 获取内容并生成摘要"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from openai import OpenAI
import httpx

from .config import Config


# Builders Digest 系统提示词
BUILDERS_SYSTEM_PROMPT = """你是一个 AI 行业内容整理者。你的任务是如实呈现 AI Builders 的动态，不做价值判断。

## 核心原则：如实呈现

**你不是编辑，是整理者。**

1. **全面呈现**：列出所有关注的人当天发布的所有内容
2. **保持原意**：忠实传达原文观点，不做删减或筛选
3. **不做判断**：不要说明"为什么重要"或"读者为什么要关心"

## 语言规范

- **统一用中文表达**
- 英文术语首次出现时用括号标注，如：智能体（Agent）
- 人名、公司名、产品名可保留英文
- 引用可保留完整内容，用*斜体*标注
- 引用后加角标 [1][2]，文末列出链接

## 输出格式

### 今日概览
[3-5个关键词，一句话说明今日内容范围]

### X/Twitter 动态

[按 Builder 分组，列出每人当天发的所有推文]

#### **[Builder 姓名]**

**简介**：[Builder 简介]

**推文**：

[推文1内容摘要，引用用*斜体*和角标]

[推文2内容摘要...]

---

#### **[Builder 姓名]**

...

---

### 播客摘要

[每个播客的摘要]

### 参考来源

[1] https://x.com/xxx/status/xxx
[2] https://x.com/yyy/status/yyy
..."""


@dataclass
class BuilderContent:
    """Builder 内容数据"""
    name: str
    bio: str
    tweets: list[dict]  # [{"text": "...", "url": "..."}]


@dataclass
class PodcastContent:
    """播客内容数据"""
    name: str
    title: str
    url: str
    transcript: str


@dataclass
class BuildersDigestData:
    """Builders Digest 原始数据"""
    builders: list[BuilderContent]
    podcasts: list[PodcastContent]
    stats: dict
    generated_at: str


class BuildersDigestFetcher:
    """获取 follow-builders 数据"""

    SKILL_DIR = Path.home() / ".claude" / "skills" / "follow-builders"

    def fetch(self) -> Optional[dict]:
        """
        从 follow-builders skill 获取原始数据

        Returns:
            JSON 数据字典，失败返回 None
        """
        prepare_script = self.SKILL_DIR / "scripts" / "prepare-digest.js"

        if not prepare_script.exists():
            print(f"警告: follow-builders skill 脚本不存在: {prepare_script}")
            return None

        try:
            # 运行 prepare-digest.js
            result = subprocess.run(
                ["node", str(prepare_script)],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                print(f"prepare-digest.js 执行失败: {result.stderr}")
                return None

            # 解析 JSON 输出
            data = json.loads(result.stdout)
            return data

        except subprocess.TimeoutExpired:
            print("prepare-digest.js 执行超时")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
            return None
        except Exception as e:
            print(f"获取 builders 数据失败: {e}")
            return None


class BuildersDigestSummarizer:
    """Builders Digest AI 总结器"""

    def __init__(self):
        http_client = httpx.Client(
            timeout=httpx.Timeout(2400.0, connect=120.0)
        )
        self.client = OpenAI(
            api_key=Config.AI_API_KEY,
            base_url=Config.AI_BASE_URL,
            http_client=http_client
        )
        self.model = Config.AI_MODEL

    def summarize_x(self, builders: list[dict]) -> str:
        """总结 X (Twitter) 内容"""
        if not builders:
            return ""

        # 构建内容 - 传递完整信息给 AI
        content_parts = ["## X/Twitter 动态\n"]

        for builder in builders:
            name = builder.get("name", "Unknown")
            handle = builder.get("handle", "")
            bio = builder.get("bio", "")
            tweets = builder.get("tweets", [])

            if not tweets:
                continue

            content_parts.append(f"### {name} (@{handle})")
            if bio:
                content_parts.append(f"简介: {bio}\n")

            content_parts.append("推文:")
            for i, tweet in enumerate(tweets, 1):
                text = tweet.get("text", "")
                url = tweet.get("url", "")
                created = tweet.get("createdAt", "")
                if text:
                    content_parts.append(f"\n[推文{i}] {text}")
                    if url:
                        content_parts.append(f"\n链接: {url}")
                    if created:
                        content_parts.append(f"\n时间: {created}")
            content_parts.append("\n")

        return "\n".join(content_parts)

    def summarize_podcasts(self, podcasts: list[dict]) -> str:
        """总结播客内容"""
        if not podcasts:
            return ""

        content_parts = ["## 播客摘要\n"]

        for i, podcast in enumerate(podcasts, 1):
            name = podcast.get("name", "Unknown Podcast")
            title = podcast.get("title", "")
            url = podcast.get("url", "")
            transcript = podcast.get("transcript", "")

            content_parts.append(f"### [播客{i}] {name}")
            if title:
                content_parts.append(f"标题: {title}")
            if url:
                content_parts.append(f"链接: {url}")
            content_parts.append("")

            # 截取转录内容（避免太长）
            if transcript:
                # 取前 15000 字符
                transcript_preview = transcript[:15000]
                if len(transcript) > 15000:
                    transcript_preview += "..."
                content_parts.append(f"转录内容:\n{transcript_preview}")
            content_parts.append("")

        return "\n".join(content_parts)

    def generate_digest(
        self,
        x_content: str,
        podcast_content: str,
        stats: dict
    ) -> Optional[str]:
        """生成完整的 Builders Digest"""
        if not x_content and not podcast_content:
            return None

        # 构建完整内容
        full_content = f"""# AI Builders 原始数据

## 统计信息
- X/Twitter Builders: {stats.get('xBuilders', 0)}
- 推文总数: {stats.get('totalTweets', 0)}
- 播客数量: {stats.get('podcastEpisodes', 0)}
- Feed 生成时间: {stats.get('feedGeneratedAt', 'N/A')}

{x_content}

{podcast_content}

---
请整理以上 AI Builders 动态。要求：
1. 列出所有关注的人当天发布的所有内容，不做筛选
2. 不要说明"为什么重要"或做价值判断
3. 用中文输出，英文术语首次出现时用括号标注
4. 引用可保留完整内容，用*斜体*和角标 [1][2]
5. 文末列出参考来源链接"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": BUILDERS_SYSTEM_PROMPT},
                    {"role": "user", "content": full_content}
                ],
                # 不设置 max_tokens 限制，让 AI 输出完整内容
                temperature=0.7
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"Builders Digest AI 总结失败: {e}")
            return None


def generate_builders_digest() -> Optional[str]:
    """
    生成 AI Builders Digest

    Returns:
        Markdown 格式的摘要，失败返回 None
    """
    print("\n正在获取 AI Builders 动态...")

    # 获取原始数据
    fetcher = BuildersDigestFetcher()
    data = fetcher.fetch()

    if not data:
        print("无法获取 Builders 数据（可能是 prepare-digest.js 执行失败）")
        return None

    stats = data.get("stats", {})
    print(f"  数据: {stats.get('xBuilders', 0)} 个 builders, "
          f"{stats.get('totalTweets', 0)} 条推文, "
          f"{stats.get('podcastEpisodes', 0)} 个播客")

    # 检查是否有内容
    if stats.get("xBuilders", 0) == 0 and stats.get("podcastEpisodes", 0) == 0:
        print("没有 Builders 动态")
        return None

    # 生成摘要
    summarizer = BuildersDigestSummarizer()

    x_content = summarizer.summarize_x(data.get("x", []))
    podcast_content = summarizer.summarize_podcasts(data.get("podcasts", []))

    digest = summarizer.generate_digest(x_content, podcast_content, stats)

    if digest:
        print("Builders Digest 生成成功")
    else:
        print("Builders Digest AI 总结失败（请检查超时设置或 API 配置）")

    return digest