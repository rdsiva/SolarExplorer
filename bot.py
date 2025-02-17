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
PUBLIC_URL = os.environ.get('PUBLIC_URL')
if not PUBLIC_URL:
    raise ValueError("PUBLIC_URL environment variable is not set")

# Ensure URL starts with https://
if not PUBLIC_URL.startswith('https://'):
    PUBLIC_URL = f"https://{PUBLIC_URL}"

WEBHOOK_URL = f"{PUBLIC_URL}/telegram/webhook"
logger.info(f"Using webhook URL: {WEBHOOK_URL}")

# Initialize bot at module level
application = None

async def setup_webhook(app_instance: Application):
    """Set up webhook for receiving updates"""
    try:
        logger.info(f"Setting up webhook at {WEBHOOK_URL}")

        # Get current webhook info and log it
        webhook_info = await app_instance.bot.get_webhook_info()
        logger.info(f"Current webhook info: {webhook_info.to_dict()}")

        # Delete existing webhook if any
        if webhook_info.url:
            logger.info(f"Deleting existing webhook: {webhook_info.url}")
            await app_instance.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(1)  # Small delay to ensure webhook is deleted

        # Set new webhook
        success = await app_instance.bot.set_webhook(
            url=WEBHOOK_URL,
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

@app.route('/telegram/webhook', methods=['POST'])
async def webhook():
    """Handle incoming webhook updates from Telegram"""
    try:
        global application
        if not application:
            logger.error("Application not initialized")
            return jsonify({'status': 'error', 'message': 'Bot not initialized'}), 500

        # Log request details for debugging
        logger.info(f"Received webhook request from: {request.remote_addr}")
        logger.info(f"Headers: {dict(request.headers)}")

        # Validate request
        if not request.is_json:
            logger.error("Invalid content type")
            return jsonify({'status': 'error', 'message': 'Invalid content type'}), 400

        update_data = request.get_json()
        if not update_data:
            logger.error("No data in webhook request")
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400

        logger.info(f"Received webhook update: {update_data}")

        # Process update
        update = Update.de_json(update_data, application.bot)
        if update:
            await application.process_update(update)
            logger.info("Update processed successfully")
            return jsonify({'status': 'ok'})
        else:
            logger.error("Failed to parse update")
            return jsonify({'status': 'error', 'message': 'Invalid update format'}), 400

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/', methods=['GET'])
def root():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Telegram bot webhook server is running',
        'webhook_url': WEBHOOK_URL
    })

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    try:
        chat_id = update.effective_chat.id
        logger.info(f"Received /start command from chat_id: {chat_id}")

        welcome_message = (
            "👋 Welcome to the Energy Price Monitor Bot!\n\n"
            "Available commands:\n"
            "/check - Check current prices\n"
            "/help - Show this help message"
        )
        await update.message.reply_text(welcome_message)
        logger.info(f"Sent welcome message to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, there was an error processing your command.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "🤖 Energy Price Monitor Help\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/check - Check current energy prices"
    )
    await update.message.reply_text(help_text)

def create_app():
    """Initialize the Flask app and Telegram bot"""
    global application

    try:
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

        # Enable nested asyncio
        nest_asyncio.apply()

        # Create and configure event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Initialize bot application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))

        # Initialize application and set up webhook
        loop.run_until_complete(application.initialize())
        success = loop.run_until_complete(setup_webhook(application))

        if not success:
            raise ValueError("Failed to set up webhook")

        # Verify bot
        bot_info = loop.run_until_complete(application.bot.get_me())
        logger.info(f"Bot initialized: @{bot_info.username}")

        return app

    except Exception as e:
        logger.error(f"Failed to create app: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    try:
        app = create_app()
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}", exc_info=True)
        raise