from telegram.ext import Application, CommandHandler, MessageHandler, filters
import config
from bot.handlers import (
    handle_photo,
    handle_text,
    cmd_today,
    cmd_note,
    cmd_week,
    cmd_status,
    cmd_ask,
    cmd_ask_end,
)
from scheduler import create_scheduler


def create_app() -> Application:
    if not config.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set")
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set")
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("note", cmd_note))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ask", cmd_ask))
    app.add_handler(CommandHandler("ask_end", cmd_ask_end))
    return app


def _run() -> None:
    scheduler = create_scheduler()
    scheduler.start()
    create_app().run_polling()


if __name__ == "__main__":
    _run()
