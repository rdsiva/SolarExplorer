import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from price_monitor import PriceMonitor
from config import TELEGRAM_BOT_TOKEN

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get chat ID from environment
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
if not TELEGRAM_CHAT_ID:
    raise ValueError("TELEGRAM_CHAT_ID environment variable is not set")

logger.info(f"Bot initialized with CHAT_ID: {TELEGRAM_CHAT_ID}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    if not update.effective_chat:
        logger.error("No effective chat available in update")
        return

    chat_id = update.effective_chat.id
    logger.info(f"Received /start command from chat_id: {chat_id}")
    logger.info(f"Expected CHAT_ID from env: {TELEGRAM_CHAT_ID}")

    welcome_message = (
        f"👋 Welcome to the Energy Price Monitor Bot!\n\n"
        f"Your Chat ID is: {chat_id}\n\n"
        "Available commands:\n"
        "/check_price - Check current prices\n"
        "/help - Show this help message"
    )
    await update.effective_chat.send_message(welcome_message)
    logger.info(f"Sent welcome message to chat_id: {chat_id}")

async def check_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check current prices when the command /check_price is issued."""
    logger.debug("check_price command received")

    if not update.effective_chat:
        logger.error("No effective chat available in update")
        return

    chat_id = update.effective_chat.id
    logger.info(f"Received /check_price command from chat_id: {chat_id}")
    logger.info(f"Expected CHAT_ID from env: {TELEGRAM_CHAT_ID}")

    try:
        status_message = await update.effective_chat.send_message("🔍 Checking current prices...")
        logger.info("Sent status message, fetching price data...")

        # Get price data
        hourly_data = await PriceMonitor.check_hourly_price()
        five_min_data = await PriceMonitor.check_five_min_price()

        logger.debug(f"Hourly data received: {hourly_data}")
        logger.debug(f"5-min data received: {five_min_data}")

        # Format message
        message = "📊 Current Energy Prices:\n\n"

        # Add five minute price if available
        five_min_price = five_min_data.get('price', 'N/A')
        message += f"5-min price: {five_min_price}¢\n"

        # Add hourly price if available
        hourly_price = hourly_data.get('price', 'N/A')
        message += f"Hourly price: {hourly_price}¢\n"

        # Add trend information
        trend = hourly_data.get('trend', 'unknown')
        message += f"Trend: {trend.capitalize()}\n\n"

        # Add timestamp
        cst_time = datetime.now(ZoneInfo("America/Chicago"))
        message += f"⏰ Last Updated: {cst_time.strftime('%Y-%m-%d %I:%M %p %Z')}"

        await status_message.edit_text(message)
        logger.info(f"Successfully sent price data to chat_id: {chat_id}")

    except Exception as e:
        error_msg = f"❌ Error checking prices: {str(e)}"
        logger.error(f"Error in check_price: {str(e)}", exc_info=True)
        await update.effective_chat.send_message(error_msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await start(update, context)

async def init_bot():
    """Initialize the bot and send a test message"""
    try:
        # Create the application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("check_price", check_price))

        # Start the bot
        logger.info("Starting bot...")

        # Send initial test message
        try:
            logger.info("Attempting to send test message...")
            await application.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text="🔄 Bot has started and is ready to receive commands!\n\nAvailable commands:\n/start - Start the bot\n/check_price - Check current prices\n/help - Show help message"
            )
            logger.info("Test message sent successfully")
        except Exception as e:
            logger.error(f"Failed to send test message: {str(e)}", exc_info=True)

        # Start polling
        await application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    import asyncio
    asyncio.run(init_bot())