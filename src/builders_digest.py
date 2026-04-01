"""AI Builders Digest 模块 - 从 follow-builders skill 获取内容并生成摘要"""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Set, List, Dict
from dataclasses import dataclass

from openai import OpenAI
import httpx

from .config import Config


# 去重历史文件
DEDUP_HISTORY_DIR = Config.BASE_DIR / "data" / "dedup_history"


def load_weekly_history() -> Dict[str, Set[str]]:
    """
    加载过去一周的去重历史

    Returns:
        {"tweets": set of URLs, "podcasts": set of episode IDs}
    """
    history = {"tweets": set(), "podcasts": set()}

    if not DEDUP_HISTORY_DIR.exists():
        return history

    # 读取过去 7 天的历史文件
    for i in range(7):
        date = datetime.now() - timedelta(days=i)
        history_file = DEDUP_HISTORY_DIR / f"{date.strftime('%Y-%m-%d')}.json"

        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    history["tweets"].update(data.get("tweets", []))
                    history["podcasts"].update(data.get("podcasts", []))
            except Exception:
                pass

    return history


def save_daily_history(tweets: List[str], podcasts: List[str]) -> None:
    """
    保存当天的去重历史

    Args:
        tweets: 当天推送的 tweet URL 列表
        podcasts: 当天推送的 podcast episode ID 列表
    """
    DEDUP_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime('%Y-%m-%d')
    history_file = DEDUP_HISTORY_DIR / f"{today}.json"

    data = {
        "tweets": tweets,
        "podcasts": podcasts,
        "generated_at": datetime.now().isoformat()
    }

    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def filter_duplicates(data: dict) -> dict:
    """
    过滤过去一周已推送的内容

    Args:
        data: 从 prepare-digest.js 获取的原始数据

    Returns:
        过滤后的数据
    """
    history = load_weekly_history()

    # 过滤 X/Twitter 内容
    filtered_x = []
    new_tweet_urls = []

    for builder in data.get("x", []):
        filtered_tweets = []
        for tweet in builder.get("tweets", []):
            url = tweet.get("url", "")
            if url and url not in history["tweets"]:
                filtered_tweets.append(tweet)
                new_tweet_urls.append(url)

        if filtered_tweets:
            filtered_builder = {**builder, "tweets": filtered_tweets}
            filtered_x.append(filtered_builder)

    # 过滤播客内容
    filtered_podcasts = []
    new_podcast_ids = []

    for podcast in data.get("podcasts", []):
        # 用 URL 作为唯一标识
        url = podcast.get("url", "")
        episode_id = url  # 或提取 video ID

        if episode_id and episode_id not in history["podcasts"]:
            filtered_podcasts.append(podcast)
            new_podcast_ids.append(episode_id)

    # 返回过滤后的数据
    filtered_data = {
        **data,
        "x": filtered_x,
        "podcasts": filtered_podcasts,
        "stats": {
            **data.get("stats", {}),
            "xBuilders": len(filtered_x),
            "totalTweets": sum(len(b.get("tweets", [])) for b in filtered_x),
            "podcastEpisodes": len(filtered_podcasts),
        }
    }

    return filtered_data, new_tweet_urls, new_podcast_ids


# Builders Digest 系统提示词
BUILDERS_SYSTEM_PROMPT = """你是一个专业的 AI 行业动态总结助手。你的任务是将 AI Builders（创业者、研究者、工程师）的动态和观点进行详细、完整的总结。

## 核心原则
1. **完整保留原文信息**：不要过度精简，保留每个观点的完整内容和细节
2. **展开背景和意义**：对于每个观点，说明其背景、影响和行业意义
3. **保持人物视角**：清晰呈现每个 builder 的身份、立场和观点脉络
4. **客观准确**：准确传达原文要点，不添加主观判断

## 关键字加粗规则（必须遵守）
- **人名**加粗：**Karpathy**、**Sam Altman**、**Andrej Karpathy**
- **公司/产品**加粗：**OpenAI**、**Anthropic**、**Claude**、**Vercel**
- **数据/数字**加粗：**100倍**、**10亿美元**、**30天**
- **核心概念**加粗：**Agent**、**SaaSpocalypse**、**Headless API**

## 分段分行规则
- 每个观点单独一段，不要堆在一起
- 观点之间空一行
- 列表项用 `-` 开头
- 来源链接另起一行

## 输出格式

### 第一部分：今日概览
- 列出今日/本周涉及的主要话题（3-5个关键词，加粗）
- 简要说明话题之间的关联性
- 提及涉及的主要人物（人名加粗）

### 第二部分：核心观点
按照重要性排序，列出所有重要观点（每个观点详细说明）：
- **观点标题**：简洁有力的观点概括
- 观点来源：哪位 **builder** 提出此观点
- 观点内容：完整的原文内容（不要精简）
- 背景/意义：说明这个观点为什么重要，对行业的影响
- 相关链接

### 第三部分：详细内容（按人物展开）
为每个重要的 builder 建立独立章节：

#### **[Builder 姓名]**
- **身份背景**：简要介绍其身份、公司/项目、行业影响力
- **核心观点摘要**：列出其今日的主要观点（用原文）
- **观点详解**：展开每个观点的具体内容、论证过程
- **行业关联**：其观点与其他 builder 的观点有何呼应或对比
- **来源链接**：列出其所有推文/发言链接

### 第四部分：行业趋势与脉络
- **热点话题**：当前最受关注的议题
- **观点交锋**：不同 builder 之间的观点对比或呼应
- **时间线**：按时间顺序梳理事件发展脉络（如有）
- **趋势预判**：基于内容分析可能的发展方向

### 第五部分：推荐关注
- **关键人物**：列出值得持续关注的 builder 及原因
- **热门话题**：建议持续追踪的话题方向
- **相关资源**：播客、文章、项目等推荐

## 注意事项
- 尽量保留原文的措辞和表达风格，不要过度改写
- 如果 builder 提供了具体数据、案例，务必完整呈现
- 每个观点都要标注来源链接
- 内容来源于 X (Twitter) 和 YouTube 播客，注意区分不同来源的特点"""


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
            timeout=httpx.Timeout(600.0, connect=120.0)
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
    生成 AI Builders Digest（自动去重过去一周内容）

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

    original_stats = data.get("stats", {})
    print(f"  原始数据: {original_stats.get('xBuilders', 0)} 个 builders, "
          f"{original_stats.get('totalTweets', 0)} 条推文, "
          f"{original_stats.get('podcastEpisodes', 0)} 个播客")

    # 去重：过滤过去一周已推送的内容
    filtered_data, new_tweet_urls, new_podcast_ids = filter_duplicates(data)

    stats = filtered_data.get("stats", {})
    print(f"  去重后: {stats.get('xBuilders', 0)} 个 builders, "
          f"{stats.get('totalTweets', 0)} 条推文, "
          f"{stats.get('podcastEpisodes', 0)} 个播客")

    # 检查是否有新内容
    if stats.get("xBuilders", 0) == 0 and stats.get("podcastEpisodes", 0) == 0:
        print("没有新的 Builders 动态（过去一周已推送过）")
        return None

    # 生成摘要
    summarizer = BuildersDigestSummarizer()

    x_content = summarizer.summarize_x(filtered_data.get("x", []))
    podcast_content = summarizer.summarize_podcasts(filtered_data.get("podcasts", []))

    digest = summarizer.generate_digest(x_content, podcast_content, stats)

    if digest:
        print("Builders Digest 生成成功")

        # 保存当天历史（用于后续去重）
        save_daily_history(new_tweet_urls, new_podcast_ids)
        print(f"  已保存去重历史记录")
    else:
        print("Builders Digest AI 总结失败（请检查超时设置或 API 配置）")

    return digest