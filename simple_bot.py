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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    chat_id = update.effective_chat.id
    welcome_message = (
        f"👋 Welcome to the Energy Price Monitor Bot!\n\n"
        f"Your Chat ID is: {chat_id}\n\n"
        "Available commands:\n"
        "/check_price - Check current prices\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(welcome_message)

async def check_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check current prices when the command /check_price is issued."""
    try:
        await update.message.reply_text("🔍 Checking current prices...")
        
        # Get price data
        hourly_data = await PriceMonitor.check_hourly_price()
        five_min_data = await PriceMonitor.check_five_min_price()
        
        # Format message
        message = "📊 Current Energy Prices:\n\n"
        message += f"5-min price: {five_min_data.get('price', 'N/A')}¢\n"
        message += f"Hourly price: {hourly_data.get('price', 'N/A')}¢\n"
        message += f"Trend: {hourly_data.get('trend', 'unknown').capitalize()}\n\n"
        
        # Add timestamp
        cst_time = datetime.now(ZoneInfo("America/Chicago"))
        message += f"⏰ Last Updated: {cst_time.strftime('%Y-%m-%d %I:%M %p %Z')}"
        
        await update.message.reply_text(message)
        
    except Exception as e:
        error_msg = f"❌ Error checking prices: {str(e)}"
        logger.error(error_msg)
        await update.message.reply_text(error_msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await start(update, context)

def main():
    """Start the bot."""
    try:
        # Create the Application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("check_price", check_price))

        # Start the bot
        logger.info("Starting bot...")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == '__main__':
    main()
