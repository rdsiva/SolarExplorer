import os
import logging
import asyncio
import nest_asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import NetworkError, TelegramError
from config import TELEGRAM_BOT_TOKEN
from urllib.parse import urlparse
import re

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')

# Get domain for webhook
REPLIT_DOMAIN = os.environ.get('REPLIT_DOMAIN')
PUBLIC_URL = os.environ.get('PUBLIC_URL')

# Determine webhook URL
if REPLIT_DOMAIN:
    WEBHOOK_BASE_URL = f"https://{REPLIT_DOMAIN}"
elif PUBLIC_URL:
    WEBHOOK_BASE_URL = PUBLIC_URL if PUBLIC_URL.startswith(('http://', 'https://')) else f"https://{PUBLIC_URL}"
else:
    raise ValueError("No valid domain available. Set REPLIT_DOMAIN or PUBLIC_URL environment variable.")

logger.info(f"Using webhook URL base: {WEBHOOK_BASE_URL}")

# Initialize bot at module level
application = None

async def setup_webhook(app_instance: Application):
    """Set up webhook for receiving updates"""
    try:
        webhook_url = f"{WEBHOOK_BASE_URL}/telegram/webhook"
        logger.info(f"Setting up webhook at {webhook_url}")

        # Get current webhook info
        webhook_info = await app_instance.bot.get_webhook_info()
        logger.info(f"Current webhook info: {webhook_info.to_dict()}")

        # Delete existing webhook if any
        if webhook_info.url:
            logger.info("Deleting existing webhook...")
            await app_instance.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(1)

        # Set new webhook
        logger.info("Setting up new webhook...")
        success = await app_instance.bot.set_webhook(
            url=webhook_url,
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True
        )

        if not success:
            raise Exception("Failed to set webhook")

        # Verify webhook setup
        new_webhook_info = await app_instance.bot.get_webhook_info()
        logger.info(f"New webhook info: {new_webhook_info.to_dict()}")

        if new_webhook_info.last_error:
            logger.warning(f"Webhook has errors: {new_webhook_info.last_error}")

        return True

    except Exception as e:
        logger.error(f"Failed to set up webhook: {str(e)}", exc_info=True)
        return False

@app.before_request
def log_request_info():
    """Log details about each incoming request"""
    logger.info('Headers: %s', request.headers)
    logger.info('Body: %s', request.get_data())

@app.route('/telegram/webhook', methods=['POST'])
async def webhook():
    """Handle incoming webhook updates from Telegram"""
    try:
        global application
        if not application:
            logger.error("Application not initialized")
            return jsonify({'status': 'error', 'message': 'Bot not initialized'}), 500

        # Validate request content type
        if not request.is_json:
            logger.error("Invalid content type")
            return jsonify({'status': 'error', 'message': 'Invalid content type'}), 400

        # Get and validate update data
        update_data = request.get_json()
        if not update_data:
            logger.error("No JSON data in webhook request")
            return jsonify({'status': 'error', 'message': 'Invalid request format'}), 400

        logger.info(f"Received webhook update: {update_data}")

        # Process update
        update = Update.de_json(update_data, application.bot)
        if update:
            await application.process_update(update)
            logger.info("Update processed successfully")
            return jsonify({'status': 'ok'})
        else:
            logger.error("Failed to parse update from Telegram")
            return jsonify({'status': 'error', 'message': 'Invalid update format'}), 400

    except Exception as e:
        logger.error(f"Error processing webhook update: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint for basic health check"""
    return jsonify({
        'status': 'ok',
        'message': 'Telegram bot webhook server is running',
        'version': '1.0'
    })

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    try:
        logger.info(f"Handling /start command from user {update.effective_user.id}")
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

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler"""
    help_message = (
        "🤖 Energy Price Monitor Bot Help\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(help_message)

def create_app():
    """Factory function to create and initialize the Flask app"""
    global application

    try:
        # Verify bot token
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

        logger.info("Starting bot initialization...")

        # Enable nested asyncio for handling async operations
        nest_asyncio.apply()

        # Create and run event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Initialize bot
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Register command handlers
        application.add_handler(CommandHandler("start", cmd_start))
        application.add_handler(CommandHandler("help", cmd_help))

        # Initialize the application and set up webhook
        loop.run_until_complete(application.initialize())
        success = loop.run_until_complete(setup_webhook(application))

        if not success:
            raise ValueError("Failed to set up webhook")

        # Verify bot info
        bot_info = loop.run_until_complete(application.bot.get_me())
        logger.info(f"Bot initialized successfully: @{bot_info.username}")

        return app

    except Exception as e:
        logger.error(f"Failed to create app: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    try:
        logger.info("Starting bot server...")
        app = create_app()
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Bot failed to start: {str(e)}", exc_info=True)
        raise