#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


OPENAI_API_URL = "https://api.openai.com/v1/responses"
TELEGRAM_API_URL = "https://api.telegram.org"


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_prompt() -> str:
    return (
        "你是一名面向交易和资产配置的中文宏观/市场简报编辑。"
        "请基于过去24小时内的公开信息，生成一份'高信号版财经早报'。"
        "必须优先搜索并引用 Bloomberg、Reuters、Financial Times、BLS、Federal Reserve、ECB、"
        "中国政府网、人民银行、国家统计局、港交所、上交所、深交所等权威来源。"
        "不要写泛新闻汇总，不要写鸡汤，不要使用任何非公开信息。"
        "输出要求："
        "1. 全文使用简体中文。"
        "2. 标题格式为：YYYY年M月D日 高信号版财经早报。"
        "3. 正文严格包含四个部分："
        "   一、今晨最重要的5条；"
        "   二、怎么影响市场；"
        "   三、预期差；"
        "   四、今晚到明早要盯的日历。"
        "4. 每条重点信息都要给出可点击来源链接。"
        "5. 明确区分已确认事实与基于公开信息的判断。"
        "6. 优先覆盖：利率、美元、原油、黄金、美股、中概、A股、港股、债券、外汇、大宗商品、加密市场。"
        "7. 控制在 900 到 1400 字之间，信息密度高，少废话。"
        "8. 结尾署名：Abner 的 AI 助理。"
    )


def openai_finance_brief(api_key: str, model: str) -> str:
    payload = {
        "model": model,
        "input": build_prompt(),
        "tools": [{"type": "web_search"}],
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))

    output = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                output.append(content.get("text", ""))

    text = "\n".join(part.strip() for part in output if part.strip()).strip()
    if not text:
        raise RuntimeError("OpenAI response did not contain output_text content")
    return text


def send_telegram(bot_token: str, chat_id: str, text: str) -> dict:
    url = f"{TELEGRAM_API_URL}/bot{bot_token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    try:
        openai_api_key = require_env("OPENAI_API_KEY")
        telegram_bot_token = require_env("TELEGRAM_BOT_TOKEN")
        telegram_chat_id = require_env("TELEGRAM_CHAT_ID")
        openai_model = os.getenv("OPENAI_MODEL", "").strip() or "gpt-5"

        brief = openai_finance_brief(openai_api_key, openai_model)
        result = send_telegram(telegram_bot_token, telegram_chat_id, brief)
        if not result.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: {result}")

        print("Telegram finance brief sent successfully.")
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
