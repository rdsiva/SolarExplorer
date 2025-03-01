import os
import logging
import asyncio
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from agents.live_price_agent import LivePriceAgent
from agents.protocols.message_protocol import Message, MessageType, MessagePriority

# Enable nested event loops
nest_asyncio.apply()

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
        # Create a command message
        command_msg = Message(
            msg_type=MessageType.COMMAND,
            source='telegram_bot',
            target='LivePrice',
            payload={'command': 'get_price'},
            priority=MessagePriority.NORMAL
        )

        # Process command through the agent
        response = await price_agent.process(command_msg)

        if response and response.type == MessageType.PRICE_UPDATE:
            message = response.payload['formatted_message']
        else:
            message = "⚠️ Unable to fetch price data at the moment. Please try again later."

        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error getting price data: {str(e)}")
        await update.message.reply_text("❌ An error occurred while fetching price data.")

async def run_bot():
    """Start the bot."""
    try:
        # Get token from environment variable
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
            return

        # Create and initialize the Application
        application = Application.builder().token(token).build()
        await application.initialize()

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("price", get_price))

        # Start the LivePrice agent
        price_agent_task = asyncio.create_task(price_agent.start())

        # Start the Telegram bot
        try:
            await application.start()
            await application.run_polling(allowed_updates=Update.ALL_TYPES)
        finally:
            # Ensure proper cleanup
            await price_agent.stop()
            await application.stop()
            await application.shutdown()

    except Exception as e:
        logger.error(f"Error in run_bot: {str(e)}")
        # Ensure cleanup even if an error occurs
        if 'application' in locals():
            await application.shutdown()

def main():
    """Main entry point."""
    try:
        # Run the event loop
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

if __name__ == '__main__':
    main()