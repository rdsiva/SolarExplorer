import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from agents.live_price_agent import LivePriceAgent

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize LivePrice agent
price_agent = LivePriceAgent(config={'price_threshold': 3.0, 'check_interval': 300})

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Hi! I am your Energy Price Alert Bot.\n'
        'Use /price to get current energy prices\n'
        'Use /help to see all available commands'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        'Available commands:\n'
        '/start - Start the bot\n'
        '/price - Get current energy prices\n'
        '/help - Show this help message'
    )

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get current energy prices when /price command is issued."""
    try:
        # Get price data from LivePrice agent
        price_data = await price_agent.get_current_price()
        if price_data:
            # Format message using the agent's formatter
            message = price_agent.format_alert_message(price_data)
        else:
            message = "⚠️ Unable to fetch price data at the moment. Please try again later."
        
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error getting price data: {str(e)}")
        await update.message.reply_text("❌ An error occurred while fetching price data.")

def main():
    """Start the bot."""
    # Get token from environment variable
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        return

    # Create the Application
    application = Application.builder().token(token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("price", get_price))

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
