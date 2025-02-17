import os
import logging
import asyncio
import nest_asyncio
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import NetworkError, TelegramError
from config import TELEGRAM_BOT_TOKEN
from modules import (
    ModuleManager,
    get_price_monitor_module
)
from asgiref.sync import sync_to_async

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')

# Get the public URL from environment (needed for webhook)
PUBLIC_URL = os.environ.get('PUBLIC_URL')
if not PUBLIC_URL:
    raise ValueError("PUBLIC_URL environment variable is not set")

# Initialize bot at module level
application = None

async def setup_webhook(app_instance: Application):
    """Set up webhook for receiving updates"""
    try:
        webhook_url = f"{PUBLIC_URL}/webhook"
        logger.info(f"Setting up webhook at {webhook_url}")

        # Get current webhook info
        webhook_info = await app_instance.bot.get_webhook_info()
        logger.info(f"Current webhook info: {webhook_info.url}")

        # Always delete existing webhook first
        logger.info("Removing existing webhook...")
        await app_instance.bot.delete_webhook(drop_pending_updates=True)

        # Wait to ensure webhook is fully deleted
        await asyncio.sleep(2)

        # Set new webhook with proper parameters
        logger.info(f"Setting new webhook to {webhook_url}")
        success = await app_instance.bot.set_webhook(
            url=webhook_url,
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True,
            max_connections=100
        )

        if not success:
            raise Exception("Failed to set webhook")

        # Verify webhook was set correctly
        webhook_info = await app_instance.bot.get_webhook_info()
        logger.info(f"New webhook info: {webhook_info.url}")

        if webhook_info.url != webhook_url:
            raise Exception(f"Webhook verification failed. Expected {webhook_url}, got {webhook_info.url}")

        logger.info("Webhook setup completed successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to set up webhook: {e}", exc_info=True)
        return False

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Handle incoming webhook updates from Telegram"""
    try:
        if not application:
            logger.error("Application not initialized")
            return jsonify({'status': 'error', 'message': 'Bot not initialized'}), 500

        # Log incoming update
        update_data = request.get_json()
        logger.debug(f"Received webhook update: {update_data}")

        # Process update
        update = Update.de_json(update_data, application.bot)
        await application.process_update(update)

        return jsonify({'status': 'ok'})

    except Exception as e:
        logger.error(f"Error processing webhook update: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        if not application:
            return jsonify({'status': 'error', 'message': 'Bot not initialized'}), 503

        webhook_info = asyncio.run(application.bot.get_webhook_info())
        return jsonify({
            'status': 'ok',
            'bot_username': application.bot.username,
            'webhook_url': webhook_info.url,
            'pending_updates': webhook_info.pending_update_count
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    welcome_message = (
        "👋 Welcome to the Energy Price Monitor Bot!\n\n"
        "Available commands:\n"
        "/check - Check current prices\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(welcome_message)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler"""
    help_message = (
        "🤖 Energy Price Monitor Bot Help\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/check - Check current energy prices\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(help_message)

async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check current prices and send a test response"""
    try:
        module_manager = context.bot_data.get('module_manager')
        if not module_manager:
            await update.message.reply_text("Module system is not initialized")
            return

        # Get price monitor data
        price_module = module_manager.get_module("price_monitor")
        if not price_module:
            await update.message.reply_text("Price monitor module is not available")
            return

        price_data = await price_module.get_notification_data()
        if not price_data:
            await update.message.reply_text("Unable to fetch price data")
            return

        # Format response message
        message = "📊 Current Energy Price:\n\n"
        message += f"Price: {price_data.get('current_price', 'N/A')}\n"
        message += f"Time: {price_data.get('time', 'N/A')}"

        await update.message.reply_text(message)
        logger.info(f"Successfully processed /check command for user {update.effective_user.id}")

    except Exception as e:
        error_msg = f"Error checking prices: {str(e)}"
        logger.error(error_msg)
        await update.message.reply_text("Sorry, there was an error processing your request.")

async def init_telegram_bot():
    """Initialize the Telegram bot with webhook support"""
    try:
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

        # Initialize and verify bot credentials
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        bot_info = await application.bot.get_me()
        logger.info(f"Bot initialized: @{bot_info.username}")

        # Initialize modules
        module_manager = await init_modules(application)
        application.bot_data['module_manager'] = module_manager

        # Register command handlers
        application.add_handler(CommandHandler("start", cmd_start))
        application.add_handler(CommandHandler("help", cmd_help))
        application.add_handler(CommandHandler("check", cmd_check))

        # Set up webhook
        if not await setup_webhook(application):
            raise Exception("Failed to set up webhook")

        # Initialize the application
        await application.initialize()
        logger.info("Bot initialization completed successfully")

        return application

    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}", exc_info=True)
        raise

async def init_modules(application):
    """Initialize required modules"""
    try:
        module_manager = ModuleManager()
        logger.info("Initializing modules...")

        # Initialize required price monitor module
        price_module = get_price_monitor_module()()
        if not await price_module.initialize():
            raise Exception("Failed to initialize price monitor module")

        module_manager.register_module(price_module)
        module_manager.enable_module("price_monitor")
        logger.info("Price monitor module initialized and enabled")

        return module_manager
    except Exception as e:
        logger.error(f"Critical error during module initialization: {e}", exc_info=True)
        raise

def create_app():
    """Factory function to create and initialize the Flask app"""
    global application

    try:
        # Enable nested asyncio for handling async operations
        nest_asyncio.apply()

        # Create and run event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Initialize bot
        application = loop.run_until_complete(init_telegram_bot())
        logger.info(f"Bot initialized successfully: @{application.bot.username}")

        return app

    except Exception as e:
        logger.error(f"Failed to create app: {e}", exc_info=True)
        raise

def main():
    """Main function to run the bot"""
    try:
        logger.info("Starting bot server...")
        app = create_app()

        # Use hypercorn for ASGI support
        from hypercorn.config import Config
        from hypercorn.asyncio import serve

        config = Config()
        config.bind = ["0.0.0.0:5000"]
        config.workers = 1  # Single worker to avoid webhook conflicts
        config.worker_class = "asyncio"

        asyncio.run(serve(app, config))

    except Exception as e:
        logger.error(f"Bot failed to start: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    main()