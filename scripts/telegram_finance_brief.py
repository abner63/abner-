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


TELEGRAM_API_URL = "https://api.telegram.org"
DEFAULT_FEEDS = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"),
    ("CNBC Finance", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
    ("MarketWatch Top Stories", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
]


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
        lines.append(f"{index}. [{item.source}] {title}")
        lines.append(item.link)
        lines.append("")

    lines.append("Abner 的 AI 助理")
    return "\n".join(lines).strip()


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

