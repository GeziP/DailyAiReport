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
1. **详细完整**：每个观点都要展开说明，不要精简，保留原文细节
2. **引用标注**：原文引用必须用*斜体*标注，并添加 [1][2] 这样的数字角标
3. **链接汇总**：所有引用链接在文末统一列出，便于阅读定位
4. **客观准确**：准确传达原文要点，不添加主观判断

## 格式规则

### 关键字加粗规则（必须遵守）
- **人名**加粗：**Karpathy**、**Sam Altman**
- **公司/产品**加粗：**OpenAI**、**Anthropic**、**Claude**
- **数据/数字**加粗：**100倍**、**10亿美元**
- **核心概念**加粗：**Agent**、**LLM**、**Reasoning**

### 引用标注规则（必须遵守）
- 原文引用用*斜体*包裹
- 每个引用后加角标 [1][2] 等
- 角标按出现顺序递增
- 文末列出所有引用链接

示例：
> *New supply chain attack this time for npm axios* [1]，这是 **Karpathy** 发现的最新安全问题。

### 分段分行规则
- 每个观点单独一段
- 观点之间空一行
- 列表项用 `-` 开头

## 输出格式

### 今日概览
- 列出主要话题（3-5个关键词，加粗）
- 简要说明话题关联性
- 提及主要人物（人名加粗）

### 核心观点

按重要性排序，每个观点详细展开：

#### **[观点标题]**

**观点来源**：**[Builder 姓名]**

**核心内容**：
[详细展开观点内容，引用原文时用*斜体*并加角标 [1]]

**背景/意义**：
[说明为什么重要，对行业的影响]

---

### 详细内容（按 Builder 展开）

为每个重要的 builder 建立独立章节：

#### **[Builder 姓名]**
*[身份背景]*

**核心观点**：
- 观点1：[详细内容，引用用*斜体*和角标 [2]]
- 观点2：[详细内容]

**行业洞察**：
[与其他观点的关联或对比]

---

### 行业趋势

- **热点话题**：当前最受关注的议题
- **观点交锋**：不同 builder 的观点对比
- **趋势预判**：可能的发展方向

### 参考来源

[1] https://x.com/xxx/status/xxx
[2] https://x.com/yyy/status/yyy
...

## 注意事项
- 必须保留原文的具体措辞和数据
- 引用必须标注角标，文末必须列出链接
- 不要过度改写，保持原文风格"""


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
请根据以上原始数据生成详细的 AI Builders 动态总结。注意：
1. 引用原文时用*斜体*并添加角标 [1][2] 等
2. 在文末"参考来源"部分列出所有引用链接
3. 保持内容详细完整，不要过度精简"""

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