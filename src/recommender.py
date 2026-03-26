"""推荐系统 - 发现已关注 Builder/播客的相似来源"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from openai import OpenAI
import httpx

from .config import Config


@dataclass
class RecommendedSource:
    """推荐来源"""
    name: str
    type: str  # "builder" 或 "podcast"
    platform: str  # "twitter", "youtube", etc.
    url: str
    reason: str
    topics: List[str]


# 推荐系统提示词
RECOMMENDATION_PROMPT = """你是一个 AI 行业专家。根据用户已关注的高质量来源，推荐相似的、用户可能感兴趣但尚未关注的新来源。

已关注列表：
{followed_sources}

请推荐 5-10 个类似的优质来源。要求：
1. 与已关注来源主题相似、质量相当
2. 用户很可能尚未关注
3. 提供 X/Twitter 账号或 YouTube 播客链接
4. 优先推荐活跃度高、内容质量好的来源

输出 JSON 格式：
{{
  "recommendations": [
    {{
      "name": "名称",
      "type": "builder/podcast",
      "platform": "twitter/youtube",
      "handle_or_url": "@handle 或 URL",
      "reason": "推荐理由（与哪个已关注来源相似，为什么值得关注）",
      "topics": ["主题1", "主题2"]
    }}
  ]
}}

注意：只输出 JSON，不要有其他内容。"""


class SourceRecommender:
    """来源推荐器 - 基于 AI 分析已关注列表，推荐新的优质来源"""

    # 已知的高质量 AI Builder（作为参考）
    KNOWN_BUILDERS = [
        "karpathy", "sama", "gdb", "dw_fry", "ylecun",
        "AndrewYNg", "goodfellow_ian", "ch402", "natfriedman",
        "patrickc", "davidfahl", "kepano", "paulg", "elonmusk"
    ]

    KNOWN_PODCASTS = [
        "Lex Fridman Podcast",
        "Huberman Lab",
        "All-In Podcast",
        "The Tim Ferriss Show",
        "Acquired",
        "My First Million",
        "How I Built This"
    ]

    def __init__(self):
        http_client = httpx.Client(timeout=httpx.Timeout(60.0, connect=30.0))
        self.client = OpenAI(
            api_key=Config.AI_API_KEY,
            base_url=Config.AI_BASE_URL,
            http_client=http_client
        )
        self.model = Config.AI_MODEL

    def get_followed_sources(self) -> str:
        """
        获取已关注的来源列表

        从 follow-builders skill 配置中读取已关注的 builders 和播客
        """
        skill_dir = Path.home() / ".claude" / "skills" / "follow-builders"
        config_file = skill_dir / "config.json"

        sources = {
            "builders": [],
            "podcasts": []
        }

        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # 提取 builders
                if "xBuilders" in config:
                    sources["builders"] = config["xBuilders"]

                # 提取播客
                if "podcasts" in config:
                    sources["podcasts"] = [
                        p.get("name", "") for p in config["podcasts"]
                        if p.get("name")
                    ]
            except Exception as e:
                print(f"读取 follow-builders 配置失败: {e}")

        # 如果没有配置，使用默认列表
        if not sources["builders"]:
            sources["builders"] = self.KNOWN_BUILDERS[:5]
        if not sources["podcasts"]:
            sources["podcasts"] = self.KNOWN_PODCASTS[:3]

        result = f"""Builders (X/Twitter):
{json.dumps(sources["builders"], indent=2, ensure_ascii=False)}

Podcasts (YouTube):
{json.dumps(sources["podcasts"], indent=2, ensure_ascii=False)}"""

        return result

    def get_watchlist(self) -> List[dict]:
        """获取观察队列中已有的来源"""
        watchlist_file = Config.BASE_DIR / "config" / "watchlist.yaml"

        if not watchlist_file.exists():
            return []

        try:
            import yaml
            with open(watchlist_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data.get("watchlist", [])
        except Exception:
            return []

    def is_already_in_watchlist(self, name: str, watchlist: List[dict]) -> bool:
        """检查是否已在观察队列中"""
        for item in watchlist:
            if item.get("name", "").lower() == name.lower():
                return True
        return False

    def recommend(self) -> List[RecommendedSource]:
        """
        生成推荐

        Returns:
            推荐来源列表
        """
        followed = self.get_followed_sources()
        watchlist = self.get_watchlist()

        prompt = RECOMMENDATION_PROMPT.format(followed_sources=followed)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8
            )

            content = response.choices[0].message.content
            if not content:
                return []

            # 清理可能的 markdown 代码块标记
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content.strip())
            recommendations = []

            for item in result.get("recommendations", []):
                name = item.get("name", "")

                # 跳过已在观察队列中的
                if self.is_already_in_watchlist(name, watchlist):
                    continue

                recommendations.append(RecommendedSource(
                    name=name,
                    type=item.get("type", "builder"),
                    platform=item.get("platform", "twitter"),
                    url=item.get("handle_or_url", ""),
                    reason=item.get("reason", ""),
                    topics=item.get("topics", [])
                ))

            return recommendations

        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
            return []
        except Exception as e:
            print(f"推荐生成失败: {e}")
            return []

    def save_recommendations(
        self,
        recommendations: List[RecommendedSource],
        output_dir: Path
    ) -> Optional[Path]:
        """
        保存推荐到观察队列文件

        Args:
            recommendations: 推荐列表
            output_dir: 输出目录

        Returns:
            保存的文件路径
        """
        import yaml

        watchlist_file = Config.BASE_DIR / "config" / "watchlist.yaml"
        today = datetime.now().strftime("%Y-%m-%d")

        # 读取现有观察队列
        existing = {"watchlist": []}
        if watchlist_file.exists():
            try:
                with open(watchlist_file, 'r', encoding='utf-8') as f:
                    existing = yaml.safe_load(f) or {"watchlist": []}
            except Exception:
                pass

        # 添加新推荐
        for rec in recommendations:
            existing["watchlist"].append({
                "name": rec.name,
                "type": rec.type,
                "platform": rec.platform,
                "handle": rec.url,
                "reason": rec.reason,
                "topics": rec.topics,
                "status": "pending",
                "added_date": today
            })

        # 确保目录存在
        watchlist_file.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        with open(watchlist_file, 'w', encoding='utf-8') as f:
            yaml.dump(existing, f, allow_unicode=True, default_flow_style=False)

        return watchlist_file

    def save_recommendations_report(
        self,
        recommendations: List[RecommendedSource],
        output_dir: Path,
        date_str: str
    ) -> Optional[Path]:
        """
        保存推荐报告（Markdown 格式）

        Args:
            recommendations: 推荐列表
            output_dir: 输出目录
            date_str: 日期字符串

        Returns:
            保存的文件路径
        """
        if not recommendations:
            return None

        report_lines = [
            f"# Builder/播客推荐 - {date_str}",
            "",
            "基于你已关注的高质量来源，以下是推荐的新的优质来源：",
            ""
        ]

        # 按类型分组
        builders = [r for r in recommendations if r.type == "builder"]
        podcasts = [r for r in recommendations if r.type == "podcast"]

        if builders:
            report_lines.append("## 🧑‍💻 推荐关注的 Builder\n")
            for rec in builders:
                report_lines.append(f"### {rec.name}")
                report_lines.append(f"- **平台**: {rec.platform}")
                report_lines.append(f"- **账号**: {rec.url}")
                report_lines.append(f"- **推荐理由**: {rec.reason}")
                if rec.topics:
                    report_lines.append(f"- **主题**: {', '.join(rec.topics)}")
                report_lines.append("")

        if podcasts:
            report_lines.append("## 🎙️ 推荐订阅的播客\n")
            for rec in podcasts:
                report_lines.append(f"### {rec.name}")
                report_lines.append(f"- **平台**: {rec.platform}")
                report_lines.append(f"- **链接**: {rec.url}")
                report_lines.append(f"- **推荐理由**: {rec.reason}")
                if rec.topics:
                    report_lines.append(f"- **主题**: {', '.join(rec.topics)}")
                report_lines.append("")

        report_lines.extend([
            "---",
            f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "*状态: pending (待观察) → 可在 config/watchlist.yaml 中更新状态*"
        ])

        output_file = output_dir / f"{date_str}-recommendations.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(report_lines))

        return output_file


def generate_recommendations() -> Optional[List[RecommendedSource]]:
    """
    生成 Builder/播客推荐

    Returns:
        推荐列表，失败返回 None
    """
    print("\n" + "=" * 50)
    print("Builder/播客推荐")
    print("=" * 50)

    recommender = SourceRecommender()
    recommendations = recommender.recommend()

    if not recommendations:
        print("没有新的推荐")
        return None

    print(f"\n发现 {len(recommendations)} 个新推荐：\n")

    for i, rec in enumerate(recommendations, 1):
        emoji = "🧑‍💻" if rec.type == "builder" else "🎙️"
        print(f"{i}. {emoji} {rec.name}")
        print(f"   平台: {rec.platform} | 账号: {rec.url}")
        print(f"   理由: {rec.reason}")
        print()

    # 保存到观察队列
    watchlist_file = recommender.save_recommendations(recommendations, Config.OUTPUT_DIR)
    if watchlist_file:
        print(f"已添加到观察队列: {watchlist_file}")

    return recommendations