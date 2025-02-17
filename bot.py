import os
import logging
import asyncio
import nest_asyncio
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
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

def init_flask_app():
    """Initialize Flask application"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')
    return app

async def run_bot():
    """Run the bot with proper async handling"""
    try:
        # Initialize application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Set up basic command handlers
        application.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Bot is starting...")))

        # Start the bot
        await application.initialize()
        await application.start()
        await application.run_polling()

    except Exception as e:
        logger.error(f"Error running bot: {str(e)}", exc_info=True)
        raise
    finally:
        if 'application' in locals():
            await application.stop()

def main():
    """Start the bot with proper error handling"""
    try:
        # Use nest_asyncio to allow nested event loops
        nest_asyncio.apply()

        # Create new event loop
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
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Bot failed to start: {str(e)}", exc_info=True)
    finally:
        try:
            loop.close()
        except Exception as e:
            logger.error(f"Error closing event loop: {str(e)}")

if __name__ == '__main__':
    main()