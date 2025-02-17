import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from modules import ModuleManager, PriceMonitorModule
from telegram.error import Conflict, NetworkError, TelegramError

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Get bot token from environment
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors caused by updates."""
    try:
        if isinstance(context.error, Conflict):
            logger.warning("Another bot instance is running")
            return

        if isinstance(context.error, NetworkError):
            logger.error("Network error occurred:", exc_info=context.error)
            return

        if isinstance(context.error, TelegramError):
            logger.error("Telegram API error occurred:", exc_info=context.error)
            return

        logger.error("Update caused error", exc_info=context.error)

    except Exception as e:
        logger.error(f"Error in error handler: {str(e)}", exc_info=True)

def main():
    """Main function - not starting the bot, just a placeholder"""
    logger.info("Bot functionality moved to webhook server (bot.py)")
    logger.info("Please use 'python bot.py' to start the webhook server")

if __name__ == '__main__':
    main()