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
from modules import (
    ModuleManager,
    get_price_monitor_module
)
from asgiref.sync import sync_to_async
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
CORS(app, resources={
    r"/telegram/*": {"origins": "*"},
    r"/health": {"origins": "*"}
})
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')

# Get domain from environment or use Replit domain
REPLIT_DOMAIN = os.environ.get('REPLIT_DOMAIN')
CUSTOM_DOMAIN = os.environ.get('PUBLIC_URL', '').strip().rstrip('/')

# Determine the public URL
if CUSTOM_DOMAIN:
    # If custom domain provided, ensure it has proper scheme
    if not CUSTOM_DOMAIN.startswith(('http://', 'https://')):
        PUBLIC_URL = f"https://{CUSTOM_DOMAIN}"
    else:
        PUBLIC_URL = CUSTOM_DOMAIN
elif REPLIT_DOMAIN:
    # Use Replit's domain if available
    PUBLIC_URL = f"https://{REPLIT_DOMAIN}"
else:
    raise ValueError("No valid domain available. Set PUBLIC_URL or use Replit's domain.")

# Validate URL format
parsed_url = urlparse(PUBLIC_URL)
if not all([parsed_url.scheme, parsed_url.netloc]):
    raise ValueError(f"Invalid URL format: {PUBLIC_URL}")

logger.info(f"Using webhook URL base: {PUBLIC_URL}")

# Initialize bot at module level
application = None

@app.before_request
def log_request_info():
    """Log details about each incoming request"""
    logger.info('Headers: %s', request.headers)
    logger.info('Body: %s', request.get_data())

async def setup_webhook(app_instance: Application):
    """Set up webhook for receiving updates with improved error handling"""
    try:
        webhook_url = f"{PUBLIC_URL}/telegram/webhook"
        logger.info(f"Setting up webhook at {webhook_url}")

        # Get current webhook info
        webhook_info = await app_instance.bot.get_webhook_info()
        logger.info(f"Current webhook info: {webhook_info.url}")

        # Delete existing webhook if any
        if webhook_info.url:
            logger.info("Deleting existing webhook...")
            await app_instance.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(1)

        # Set new webhook with proper SSL validation
        logger.info("Setting up new webhook...")
        success = await app_instance.bot.set_webhook(
            url=webhook_url,
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True,
            max_connections=100
        )

        if not success:
            raise Exception("Failed to set webhook")

        # Verify webhook setup
        new_webhook_info = await app_instance.bot.get_webhook_info()
        logger.info(f"New webhook info: {new_webhook_info.to_dict()}")

        if new_webhook_info.last_error:
            logger.warning(f"Webhook has errors: {new_webhook_info.last_error}")
            if "Connection refused" in str(new_webhook_info.last_error):
                logger.error("Connection refused error detected. Please ensure the webhook URL is accessible.")

        return True

    except Exception as e:
        logger.error(f"Failed to set up webhook: {str(e)}", exc_info=True)
        return False

@app.route('/telegram/webhook', methods=['POST'])
async def webhook():
    """Handle incoming webhook updates from Telegram with improved validation"""
    try:
        if request.method != 'POST':
            logger.error(f"Invalid method {request.method} for webhook")
            return jsonify({'status': 'error', 'message': 'Method not allowed'}), 405

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
            logger.info(f"Processing update type: {update.effective_message.text if update.effective_message else 'No message'}")
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

@app.route('/health', methods=['GET'])
async def health_check():
    """Enhanced health check endpoint"""
    try:
        if not application:
            return jsonify({'status': 'error', 'message': 'Bot not initialized'}), 503

        # Get webhook status
        webhook_info = await application.bot.get_webhook_info()

        # Check if webhook has recent errors
        webhook_status = 'ok'
        webhook_error = None
        if webhook_info.last_error:
            webhook_status = 'warning'
            webhook_error = webhook_info.last_error_message

        return jsonify({
            'status': 'ok',
            'bot_username': application.bot.username,
            'webhook_url': webhook_info.url,
            'webhook_status': webhook_status,
            'webhook_error': webhook_error,
            'pending_updates': webhook_info.pending_update_count
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler with error handling"""
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
    """Initialize the Telegram bot with webhook support and improved error handling"""
    try:
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

        logger.info("Starting bot initialization...")

        # Initialize and verify bot credentials
        try:
            application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            bot_info = await application.bot.get_me()
            logger.info(f"Bot initialized: @{bot_info.username}")
        except Exception as e:
            raise ValueError(f"Failed to initialize bot with provided token: {str(e)}")

        # Initialize modules
        try:
            module_manager = await init_modules(application)
            application.bot_data['module_manager'] = module_manager
        except Exception as e:
            raise ValueError(f"Failed to initialize modules: {str(e)}")

        # Register command handlers
        logger.info("Registering command handlers...")
        application.add_handler(CommandHandler("start", cmd_start))
        application.add_handler(CommandHandler("help", cmd_help))
        application.add_handler(CommandHandler("check", cmd_check))
        logger.info("Command handlers registered successfully")

        # Set up webhook with retries
        MAX_RETRIES = 3
        retry_count = 0
        while retry_count < MAX_RETRIES:
            if await setup_webhook(application):
                break
            retry_count += 1
            if retry_count < MAX_RETRIES:
                logger.warning(f"Webhook setup failed, retrying... ({retry_count}/{MAX_RETRIES})")
                await asyncio.sleep(2)

        if retry_count == MAX_RETRIES:
            raise ValueError("Failed to set up webhook after maximum retries")

        # Initialize the application
        await application.initialize()
        logger.info("Bot initialization completed successfully")

        return application

    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {str(e)}", exc_info=True)
        raise

def create_app():
    """Factory function to create and initialize the Flask app with improved error handling"""
    global application

    try:
        # Enable nested asyncio for handling async operations
        nest_asyncio.apply()

        # Create and run event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Initialize bot
        application = loop.run_until_complete(init_telegram_bot())

        if not application:
            raise ValueError("Failed to initialize bot application")

        logger.info(f"Bot initialized successfully: @{application.bot.username}")

        # Set up error handlers
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            """Global error handler for the bot"""
            logger.error("Exception while handling an update:", exc_info=context.error)

            if isinstance(context.error, NetworkError):
                logger.error("Network error occurred")
            elif isinstance(context.error, TelegramError):
                logger.error("Telegram API error occurred")

        application.add_error_handler(error_handler)

        return app

    except Exception as e:
        logger.error(f"Failed to create app: {str(e)}", exc_info=True)
        raise

def main():
    """Main function to run the bot with improved error handling"""
    try:
        logger.info("Starting bot server...")
        app = create_app()

        # Use Flask's built-in server for development
        app.run(host='0.0.0.0', port=5000, debug=True)

    except Exception as e:
        logger.error(f"Bot failed to start: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()