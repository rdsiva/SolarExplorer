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
import socket

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

def is_port_in_use(port):
    """Check if a port is in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except socket.error:
            return True
        finally:
            s.close()

async def setup_webhook(app_instance: Application):
    """Set up webhook for receiving updates"""
    try:
        webhook_url = f"{PUBLIC_URL}/telegram-webhook"
        webhook_info = await app_instance.bot.get_webhook_info()

        # Delete existing webhook
        logger.info("Deleting existing webhook if any...")
        await app_instance.bot.delete_webhook()

        # Set new webhook
        logger.info(f"Setting webhook to {webhook_url}")
        await app_instance.bot.set_webhook(url=webhook_url)

        # Verify webhook was set
        webhook_info = await app_instance.bot.get_webhook_info()
        if webhook_info.url != webhook_url:
            raise Exception("Webhook URL verification failed")

        logger.info("Webhook setup completed successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to set up webhook: {e}", exc_info=True)
        return False

@app.route('/telegram-webhook', methods=['POST'])
async def telegram_webhook():
    """Handle incoming webhook updates from Telegram"""
    try:
        if not application:
            logger.error("Application not initialized")
            return jsonify({'status': 'error', 'message': 'Bot not initialized'}), 500

        update_data = request.get_json()
        logger.debug(f"Received webhook update: {update_data}")

        # Process update in async context
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
        return jsonify({
            'status': 'ok',
            'bot_username': application.bot.username,
            'webhook_url': f"{PUBLIC_URL}/telegram-webhook"
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
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
        if is_port_in_use(5000):
            raise Exception("Port 5000 is already in use")

        logger.info("Starting bot server...")
        app = create_app()

        # Use hypercorn for ASGI support
        from hypercorn.config import Config
        from hypercorn.asyncio import serve

        config = Config()
        config.bind = ["0.0.0.0:5000"]
        config.workers = 1
        config.worker_class = "asyncio"

        asyncio.run(serve(app, config))

    except Exception as e:
        logger.error(f"Bot failed to start: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    main()