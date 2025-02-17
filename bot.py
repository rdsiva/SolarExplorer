import os
import logging
import asyncio
import nest_asyncio
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import NetworkError, TelegramError
from config import TELEGRAM_BOT_TOKEN
from modules import (
    ModuleManager,
    get_price_monitor_module,
    get_pattern_analysis_module,
    get_ml_prediction_module,
    get_dashboard_module
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    welcome_message = (
        "👋 Welcome to the Energy Price Monitor Bot!\n\n"
        "Available commands:\n"
        "/check - Check current prices\n"
        "/modules - List available modules\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(welcome_message)

async def cmd_modules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available modules and their status"""
    try:
        module_manager = context.bot_data.get('module_manager')
        if not module_manager:
            await update.message.reply_text("Module system is not initialized")
            return

        modules = module_manager.get_all_modules()
        message = "📊 Available Modules:\n\n"

        # List required modules first
        required_modules = [m for m in modules if m["name"] in ["price_monitor", "dashboard"]]
        optional_modules = [m for m in modules if m["name"] not in ["price_monitor", "dashboard"]]

        for idx, module in enumerate(required_modules, 1):
            status = "✅ Always Enabled (Required)"
            message += (
                f"{idx}. {module['name'].replace('_', ' ').title()} 🔒\n"
                f"   • Status: {status}\n"
                f"   • Description: {module['description']}\n\n"
            )

        # Then list optional modules
        for idx, module in enumerate(optional_modules, len(required_modules) + 1):
            status = "✅ Enabled" if module["enabled"] else "❌ Disabled"
            message += (
                f"{idx}. {module['name'].replace('_', ' ').title()} (Optional)\n"
                f"   • Status: {status}\n"
                f"   • Description: {module['description']}\n\n"
            )

        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error listing modules: {e}")
        await update.message.reply_text("Sorry, there was an error listing the modules.")

async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check current prices and predictions"""
    try:
        module_manager = context.bot_data.get('module_manager')
        if not module_manager:
            await update.message.reply_text("Module system is not initialized")
            return

        # Get price monitor data (required module)
        price_module = module_manager.get_module("price_monitor")
        if not price_module:
            await update.message.reply_text("Price monitor module is not available")
            return

        price_data = await price_module.get_notification_data()
        if not price_data:
            await update.message.reply_text("Unable to fetch price data")
            return

        # Construct message
        message = f"👤 {update.effective_user.first_name}\n"
        message += f"📧 /check@{context.bot.username}\n\n"
        message += "📈 Current Energy Prices:\n"
        message += f"5-min price: {price_data.get('current_price')}\n"
        message += f"Hourly price: {price_data.get('hourly_price', 'N/A')}\n"
        message += f"Alert Threshold: {price_data.get('alert_threshold', 'N/A')}\n\n"

        # Add pattern analysis if enabled and available
        if "patterns" in price_data:
            message += "🔍 Pattern Analysis:\n"
            patterns = price_data["patterns"]
            if patterns.get("current_trend"):
                message += f"📊 {patterns['current_trend']}\n"
            if patterns.get("volatility"):
                message += f"📉 Volatility: {patterns['volatility']:.2f}\n"
            message += "\n"

        # Add ML predictions if enabled and available
        if "predictions" in price_data:
            message += "🤖 ML Price Prediction:\n"
            pred = price_data["predictions"]
            if pred:
                message += f"Next hour: {pred.get('predicted_price', 'N/A')}¢\n"
                message += f"Confidence: {pred.get('confidence', 'N/A')}%\n\n"

        message += f"⏰ Last Updated: {price_data.get('time', 'N/A')} CST"

        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error checking prices: {e}")
        await update.message.reply_text("Sorry, there was an error checking the prices.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler"""
    help_message = (
        "🤖 Energy Price Monitor Bot Help\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/check - Check current energy prices\n"
        "/modules - List available modules\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(help_message)

async def init_telegram_bot():
    """Initialize the Telegram bot with proper error handling"""
    try:
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

        # Initialize application with proper error handling
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Initialize modules
        module_manager = await init_modules(application)
        application.bot_data['module_manager'] = module_manager

        # Register command handlers
        application.add_handler(CommandHandler("start", cmd_start))
        application.add_handler(CommandHandler("check", cmd_check))
        application.add_handler(CommandHandler("modules", cmd_modules))
        application.add_handler(CommandHandler("help", cmd_help))

        # Start polling
        await application.initialize()
        await application.start()
        await application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}", exc_info=True)
        raise

async def init_modules(application):
    """Initialize all modules"""
    try:
        module_manager = ModuleManager()
        logger.info("Initializing modules...")

        # Initialize required modules first
        price_module = get_price_monitor_module()()
        if not await price_module.initialize():
            raise Exception("Failed to initialize price monitor module")
        module_manager.register_module(price_module)
        module_manager.enable_module("price_monitor")
        logger.info("Price monitor module initialized and enabled")

        # Initialize dashboard module
        dashboard_module = get_dashboard_module()()
        if not await dashboard_module.initialize():
            logger.warning("Dashboard module initialization failed, continuing without dashboard")
        else:
            module_manager.register_module(dashboard_module)
            module_manager.enable_module("dashboard")
            logger.info("Dashboard module initialized and enabled")

        # Initialize optional modules with error handling
        try:
            pattern_module = get_pattern_analysis_module()()
            await pattern_module.initialize()
            module_manager.register_module(pattern_module)
            logger.info("Pattern analysis module initialized")
        except Exception as e:
            logger.error(f"Failed to initialize pattern analysis module: {e}")

        try:
            ml_module = get_ml_prediction_module()()
            await ml_module.initialize()
            module_manager.register_module(ml_module)
            logger.info("ML prediction module initialized")
        except Exception as e:
            logger.error(f"Failed to initialize ML module: {e}")

        return module_manager
    except Exception as e:
        logger.error(f"Critical error during module initialization: {e}")
        raise


def init_flask_app():
    """Initialize Flask application"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')
    return app

def main():
    """Main function to run the bot"""
    try:
        # Enable nested asyncio
        nest_asyncio.apply()

        # Create and run event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Initialize Flask app
        app = init_flask_app()

        # Run the Flask app in a separate thread
        import threading
        flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080, debug=False))
        flask_thread.daemon = True
        flask_thread.start()

        # Run the bot
        loop.run_until_complete(init_telegram_bot())
    except Exception as e:
        logger.error(f"Bot failed to start: {e}", exc_info=True)
        raise
    finally:
        loop.close()

if __name__ == '__main__':
    main()