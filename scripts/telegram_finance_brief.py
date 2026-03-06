#!/usr/bin/env python3
import email.utils
import html
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
import re


TELEGRAM_API_URL = "https://api.telegram.org"
DEFAULT_FEEDS = [
    ("CNBC Finance", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
    ("CNBC Top News", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("Schwab Press", "https://pressroom.aboutschwab.com/rss-feeds/default.aspx?cat=2675"),
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("MarketWatch Top Stories", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
]

SOURCE_NAMES_ZH = {
    "CNBC Finance": "CNBC 财经",
    "CNBC Top News": "CNBC 要闻",
    "Schwab Press": "嘉信理财",
    "Reuters Business": "路透商业",
    "MarketWatch Top Stories": "MarketWatch 焦点",
}

KEYWORD_MAP = {
    "fed": "美联储",
    "federal reserve": "美联储",
    "ecb": "欧洲央行",
    "inflation": "通胀",
    "cpi": "CPI",
    "ppi": "PPI",
    "jobs": "就业",
    "payrolls": "非农",
    "treasury": "美债",
    "bond": "债券",
    "stocks": "股市",
    "stock": "股票",
    "shares": "个股",
    "oil": "原油",
    "gold": "黄金",
    "dollar": "美元",
    "yuan": "人民币",
    "bitcoin": "比特币",
    "crypto": "加密市场",
    "tariff": "关税",
    "trade": "贸易",
    "china": "中国",
    "us ": "美国",
    "u.s.": "美国",
    "earnings": "财报",
    "rate cut": "降息",
    "rates": "利率",
    "recession": "衰退",
    "trump": "特朗普",
    "merger": "并购",
    "acquisition": "收购",
    "ipo": "IPO",
    "guidance": "业绩指引",
    "forecast": "预期",
    "tesla": "特斯拉",
    "apple": "苹果",
    "nvidia": "英伟达",
    "microsoft": "微软",
    "amazon": "亚马逊",
    "meta": "Meta",
}

ACTION_MAP = {
    "falls": "下跌",
    "fall": "回落",
    "drops": "走弱",
    "drop": "回落",
    "rises": "走强",
    "rise": "走强",
    "gains": "上涨",
    "gain": "上涨",
    "jumps": "大涨",
    "surges": "飙升",
    "slips": "走弱",
    "cuts": "下调",
    "cut": "下调",
    "hikes": "上调",
    "raise": "上调",
    "holds": "维持",
    "keeps": "维持",
    "warns": "发出警告",
    "warn": "发出警告",
    "beats": "好于预期",
    "misses": "低于预期",
    "miss": "低于预期",
    "approves": "获批",
    "approval": "获批",
    "expands": "扩张",
    "slows": "放缓",
}


@dataclass
class FeedItem:
    source: str
    title: str
    link: str
    published_ts: float


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def fetch_url(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 TelegramFinanceBrief/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def parse_time(raw_value: str) -> float:
    if not raw_value:
        return 0.0
    parsed = email.utils.parsedate_tz(raw_value)
    if parsed is not None:
        return float(email.utils.mktime_tz(parsed))

    iso_value = raw_value.replace("Z", "+00:00")
    try:
        return __import__("datetime").datetime.fromisoformat(iso_value).timestamp()
    except ValueError:
        return 0.0


def first_text(item: ET.Element, names: list[str]) -> str:
    for name in names:
        element = item.find(name)
        if element is not None and element.text:
            return html.unescape(element.text.strip())
    return ""


def parse_rss(source: str, xml_bytes: bytes) -> list[FeedItem]:
    root = ET.fromstring(xml_bytes)
    items: list[FeedItem] = []

    for item in root.findall(".//item"):
        title = first_text(item, ["title"])
        link = first_text(item, ["link"])
        published = first_text(item, ["pubDate", "published", "updated"])
        if not title or not link:
            continue
        items.append(
            FeedItem(
                source=source,
                title=title,
                link=link,
                published_ts=parse_time(published),
            )
        )

    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = first_text(entry, ["{http://www.w3.org/2005/Atom}title"])
        link = ""
        for link_el in entry.findall("{http://www.w3.org/2005/Atom}link"):
            href = link_el.attrib.get("href", "").strip()
            if href:
                link = href
                break
        published = first_text(
            entry,
            [
                "{http://www.w3.org/2005/Atom}published",
                "{http://www.w3.org/2005/Atom}updated",
            ],
        )
        if not title or not link:
            continue
        items.append(
            FeedItem(
                source=source,
                title=title,
                link=link,
                published_ts=parse_time(published),
            )
        )

    return items


def load_feed_items() -> list[FeedItem]:
    items: list[FeedItem] = []
    errors: list[str] = []

    for source, url in DEFAULT_FEEDS:
        try:
            items.extend(parse_rss(source, fetch_url(url)))
        except Exception as exc:
            errors.append(f"{source}: {exc}")

    if not items:
        raise RuntimeError("Unable to fetch any RSS feed entries")
    if errors:
        print("Feed warnings: " + "; ".join(errors), file=sys.stderr)
    return items


def select_recent_items(items: list[FeedItem], max_age_hours: int = 24, limit: int = 12) -> list[FeedItem]:
    cutoff = time.time() - (max_age_hours * 3600)
    seen_links: set[str] = set()
    recent: list[FeedItem] = []

    for item in sorted(items, key=lambda entry: entry.published_ts, reverse=True):
        if item.link in seen_links:
            continue
        if item.published_ts and item.published_ts < cutoff:
            continue
        seen_links.add(item.link)
        recent.append(item)
        if len(recent) >= limit:
            break

    if recent:
        return recent

    fallback: list[FeedItem] = []
    for item in sorted(items, key=lambda entry: entry.published_ts, reverse=True):
        if item.link in seen_links:
            continue
        seen_links.add(item.link)
        fallback.append(item)
        if len(fallback) >= min(limit, 8):
            break
    return fallback


def build_message(items: list[FeedItem]) -> str:
    today = __import__("datetime").datetime.now(__import__("datetime").timezone(__import__("datetime").timedelta(hours=8)))
    lines = [f"{today.year}年{today.month}月{today.day}日 财经RSS早报", ""]
    lines.append("固定新闻源转发，按发布时间近似排序：")
    lines.append("")

    for index, item in enumerate(items, start=1):
        title = item.title.replace("\n", " ").strip()
        lines.append(f"{index}. [{SOURCE_NAMES_ZH.get(item.source, item.source)}] {title}")
        lines.append(f"关键信息：{summarize_title(title)}")
        lines.append(item.link)
        lines.append("")

    lines.append("Abner 的 AI 助理")
    return "\n".join(lines).strip()


def summarize_title(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", title).strip()
    lowered = f" {cleaned.lower()} "
    hits: list[str] = []
    actions: list[str] = []

    for keyword, label in KEYWORD_MAP.items():
        if keyword in lowered and label not in hits:
            hits.append(label)

    for keyword, label in ACTION_MAP.items():
        if keyword in lowered and label not in actions:
            actions.append(label)

    numbers = re.findall(r"\d+(?:\.\d+)?%?|\$\d+(?:\.\d+)?", cleaned)
    numeric_text = "、".join(numbers[:3]) if numbers else ""

    if not hits and not actions and not numeric_text:
        return "关注原文标题涉及的最新市场变化。"

    subject_text = "、".join(hits[:3]) if hits else "相关资产"
    action_text = actions[0] if actions else "出现新变化"

    if numeric_text:
        return f"{subject_text}{action_text}，标题涉及的关键数字包括 {numeric_text}。"

    return f"{subject_text}{action_text}，建议结合原文判断市场影响。"


def send_telegram(bot_token: str, chat_id: str, text: str) -> dict:
    url = f"{TELEGRAM_API_URL}/bot{bot_token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "false",
        }
    ).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        return __import__("json").loads(response.read().decode("utf-8"))


def main() -> int:
    try:
        telegram_bot_token = require_env("TELEGRAM_BOT_TOKEN")
        telegram_chat_id = require_env("TELEGRAM_CHAT_ID")

        items = load_feed_items()
        selected = select_recent_items(items)
        message = build_message(selected)

        result = send_telegram(telegram_bot_token, telegram_chat_id, message)
        if not result.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: {result}")

        print("Telegram RSS finance brief sent successfully.")
        return 0
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP error: {exc.code} {details}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
