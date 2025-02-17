import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from datetime import datetime
from zoneinfo import ZoneInfo
from modules import ModuleManager, PriceMonitorModule, PatternAnalysisModule, MLPredictionModule
from app import app, db

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

# Initialize ModuleManager and core modules
module_manager = ModuleManager()
price_module = PriceMonitorModule()
pattern_module = PatternAnalysisModule()
ml_module = MLPredictionModule()

# Register and enable price monitoring (required)
module_manager.register_module(price_module)
module_manager.enable_module("price_monitor")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when /start is issued"""
    logger.info(f"Received /start command from user {update.effective_user.id}")
    try:
        welcome_message = (
            "👋 Welcome to the Energy Price Monitor Bot!\n\n"
            "Available commands:\n"
            "/check - Check current prices\n"
            "/modules - List available modules\n"
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

        # Get basic price data from price monitor module
        price_data = await price_module.get_price_data()
        if not price_data:
            await update.message.reply_text("❌ Unable to fetch price data at this time.")
            return

        # Format basic message
        message = "📊 Current Energy Prices:\n\n"
        message += f"Current Price: {price_data.get('current_price', 'N/A')}¢\n"
        message += f"Average Price: {price_data.get('average_price', 'N/A')}¢\n"

        # Add timestamp
        current_time = datetime.now(ZoneInfo("America/Chicago"))
        message += f"\n⏰ Last Updated: {current_time.strftime('%I:%M %p %Z')}"

        await update.message.reply_text(message)

    except Exception as e:
        error_msg = f"❌ Error checking prices: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await update.message.reply_text(error_msg)

async def list_modules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available modules and their status"""
    logger.info(f"Received /modules command from user {update.effective_user.id}")
    try:
        modules = module_manager.get_all_modules()
        message = "📊 Available Modules:\n\n"

        # List required price monitor first
        for module in modules:
            if module["name"] == "price_monitor":
                message += (
                    f"1. {module['name'].replace('_', ' ').title()} 🔒\n"
                    f"   • Status: ✅ Always Enabled (Required)\n"
                    f"   • Description: {module['description']}\n\n"
                )
                break

        # List optional modules
        for module in modules:
            if module["name"] != "price_monitor":
                status = "✅ Enabled" if module["enabled"] else "❌ Disabled"
                message += (
                    f"• {module['name'].replace('_', ' ').title()}\n"
                    f"  Status: {status}\n"
                    f"  Description: {module['description']}\n\n"
                )

        await update.message.reply_text(message)
        logger.info("Module list sent successfully")
    except Exception as e:
        logger.error(f"Error listing modules: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ Sorry, there was an error listing the modules. Please try again later."
        )

def main():
    """Start the bot with core functionality"""
    try:
        # Create application with error handling
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add core command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("check", check))
        application.add_handler(CommandHandler("modules", list_modules))

        # Start polling
        logger.info("Starting bot...")
        application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()