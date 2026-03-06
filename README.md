# abner

## Telegram Finance Brief

This repo includes a GitHub Actions workflow that sends a daily Telegram finance brief at 08:00 Asia/Shanghai.

Files:
- `.github/workflows/telegram-finance-brief.yml`
- `scripts/telegram_finance_brief.py`

Required GitHub Actions secrets:
- `OPENAI_API_KEY`: your OpenAI API key
- `OPENAI_MODEL`: optional, defaults to `gpt-5`
- `TELEGRAM_BOT_TOKEN`: your Telegram bot token
- `TELEGRAM_CHAT_ID`: your Telegram private chat id

How it works:
1. GitHub Actions runs daily at `00:00 UTC`, which is `08:00` in Asia/Shanghai.
2. The Python script calls the OpenAI Responses API with web search enabled.
3. It generates a Chinese high-signal finance brief.
4. It sends the result to your Telegram bot chat.
