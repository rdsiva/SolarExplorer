import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
from simple_price_monitor import SimplePriceMonitor
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get bot token from environment
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when /start is issued"""
    welcome_message = (
        "👋 Welcome to the Simple ComEd Price Monitor!\n\n"
        "Available commands:\n"
        "/check - Check current prices\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message"""
    await start(update, context)

async def check_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check and display current prices"""
    try:
        await update.message.reply_text("🔍 Checking prices...")
        
        monitor = SimplePriceMonitor()
        price_data = monitor.get_current_prices()
        message = monitor.format_alert_message(price_data)
        
        await update.message.reply_text(message)
        
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await update.message.reply_text(error_msg)

def main():
    """Start the bot"""
    try:
        # Create application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("check", check_price))

        # Start polling
        logger.info("Starting bot...")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Bot error: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()
