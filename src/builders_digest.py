"""AI Builders Digest 模块 - 从 follow-builders skill 获取内容并生成摘要"""

import json
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from openai import OpenAI
import httpx

from .config import Config


# Builders Digest 系统提示词
BUILDERS_SYSTEM_PROMPT = """你是一个专业的 AI 行业动态总结助手。你的任务是将 AI Builders（创业者、研究者、工程师）的动态和观点进行详细总结。

总结要求：
1. 保持客观，准确传达原文要点
2. 提供详细、完整的信息，不要过度精简
3. 使用清晰的 Markdown 格式
4. 按主题/人物分类整理内容
5. 保留原文链接
6. 展开每个观点的背景和意义

输出格式：
## AI Builders 动态摘要

### 核心观点
- 列出所有重要的观点或动态，每条详细说明

### 详细内容
按人物或主题分组，每个部分包含：
- 该 builder 的背景和观点摘要
- 具体推文或发言内容的详细解读
- 观点的背景、意义和影响
- 来源链接

### 行业趋势
总结当前 AI 行业的热点话题和发展趋势

### 推荐关注
列出值得关注的人物或话题，说明原因

注意：内容来源于 X (Twitter) 和 YouTube 播客，请保持信息的准确性和时效性。尽量保留原文的细节和深度。"""


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
            timeout=httpx.Timeout(120.0, connect=30.0)
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

        # 构建内容
        content_parts = ["## X/Twitter 动态\n"]

        for builder in builders:
            name = builder.get("name", "Unknown")
            bio = builder.get("bio", "")
            tweets = builder.get("tweets", [])

            if not tweets:
                continue

            content_parts.append(f"### {name}")
            if bio:
                content_parts.append(f"*{bio}*\n")

            for tweet in tweets:  # 不限制数量，按时间过滤由 prepare-digest.js 处理
                text = tweet.get("text", "")
                url = tweet.get("url", "")
                if text:
                    content_parts.append(f"- {text}")
                    if url:
                        content_parts.append(f"  [链接]({url})")
            content_parts.append("")

        return "\n".join(content_parts)

    def summarize_podcasts(self, podcasts: list[dict]) -> str:
        """总结播客内容"""
        if not podcasts:
            return ""

        content_parts = ["## 播客摘要\n"]

        for podcast in podcasts:
            name = podcast.get("name", "Unknown Podcast")
            title = podcast.get("title", "")
            url = podcast.get("url", "")
            transcript = podcast.get("transcript", "")

            content_parts.append(f"### {name}")
            if title:
                content_parts.append(f"**{title}**")
            if url:
                content_parts.append(f"[收听链接]({url})")
            content_parts.append("")

            # 截取转录内容（避免太长）
            if transcript:
                # 取前 10000 字符
                transcript_preview = transcript[:10000]
                if len(transcript) > 10000:
                    transcript_preview += "..."
                content_parts.append(f"```\n{transcript_preview}\n```")
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
        full_content = f"""# AI Builders Digest

统计信息：
- X/Twitter Builders: {stats.get('xBuilders', 0)}
- 推文总数: {stats.get('totalTweets', 0)}
- 播客数量: {stats.get('podcastEpisodes', 0)}
- 生成时间: {stats.get('feedGeneratedAt', 'N/A')}

{x_content}

{podcast_content}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": BUILDERS_SYSTEM_PROMPT},
                    {"role": "user", "content": f"请总结以下 AI Builders 动态内容：\n\n{full_content}"}
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
        print("无法获取 Builders 数据")
        return None

    stats = data.get("stats", {})
    print(f"  获取到 {stats.get('xBuilders', 0)} 个 builders, "
          f"{stats.get('totalTweets', 0)} 条推文, "
          f"{stats.get('podcastEpisodes', 0)} 个播客")

    # 检查是否有内容
    if stats.get("xBuilders", 0) == 0 and stats.get("podcastEpisodes", 0) == 0:
        print("没有新的 Builders 动态")
        return None

    # 生成摘要
    summarizer = BuildersDigestSummarizer()

    x_content = summarizer.summarize_x(data.get("x", []))
    podcast_content = summarizer.summarize_podcasts(data.get("podcasts", []))

    digest = summarizer.generate_digest(x_content, podcast_content, stats)

    if digest:
        print("Builders Digest 生成成功")
    else:
        print("Builders Digest 生成失败")

    return digest