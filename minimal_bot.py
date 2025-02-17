import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime
from zoneinfo import ZoneInfo
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

# Initialize ModuleManager and price module
module_manager = ModuleManager()
price_module = PriceMonitorModule()

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors caused by updates."""
    try:
        if isinstance(context.error, Conflict):
            logger.warning("Another bot instance is running. Shutting down this instance.")
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when /start is issued"""
    logger.info(f"Received /start command from user {update.effective_user.id}")
    try:
        welcome_message = (
            "👋 Welcome to the Energy Price Monitor Bot!\n\n"
            "Available commands:\n"
            "/check - Check current prices\n"
            "/help - Show this help message"
        )
        await update.message.reply_text(welcome_message)
        logger.info("Welcome message sent successfully")
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, there was an error processing your command.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message"""
    logger.info(f"Received /help command from user {update.effective_user.id}")
    await start(update, context)

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check current prices with basic analysis"""
    logger.info(f"Received /check command from user {update.effective_user.id}")
    try:
        await update.message.reply_text("🔍 Checking current prices...")

        # Get price data from module
        price_data = await price_module.get_notification_data()
        if not price_data:
            await update.message.reply_text("❌ Unable to fetch price data at this time.")
            return

        # Format message
        message = "📊 Current Energy Prices:\n\n"
        message += f"Current Price: {price_data.get('current_price')}¢\n"
        message += f"Provider: {price_data.get('provider', 'ComEd')}\n"
        message += f"Status: {price_data.get('status', 'unknown').capitalize()}\n"

        # Add timestamp
        current_time = datetime.now(ZoneInfo("America/Chicago"))
        message += f"\n⏰ Last Updated: {current_time.strftime('%I:%M %p %Z')}"

        await update.message.reply_text(message)

    except Exception as e:
        error_msg = f"❌ Error checking prices: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await update.message.reply_text(error_msg)

def main():
    """Start the bot with improved error handling"""
    try:
        # Register and enable the price monitor module
        module_manager.register_module(price_module)
        module_manager.enable_module("price_monitor")

        # Create application with error handling
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Register error handler
        application.add_error_handler(error_handler)

        # Add core command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("check", check))

        # Start polling with clean session
        logger.info("Starting bot...")
        application.run_polling(drop_pending_updates=True)

    except Conflict:
        logger.warning("Another bot instance is already running")
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()