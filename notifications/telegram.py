import asyncio
from telegram import Bot
import config


async def _send(text: str) -> None:
    async with Bot(token=config.TELEGRAM_BOT_TOKEN) as bot:
        await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)


def send_alert(text: str) -> None:
    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_CHAT_ID is None:
        return
    asyncio.run(_send(text))
