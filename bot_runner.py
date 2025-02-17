"""Bot runner module for managing Telegram bot lifecycle."""
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

class BotRunner:
    """Manages the lifecycle of the Telegram bot and LivePrice agent."""

    def __init__(self):
        """Initialize the bot runner."""
        self.price_agent = LivePriceAgent(config={'price_threshold': 3.0, 'check_interval': 300})
        self.application = None
        self.is_running = False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        await update.message.reply_text(
            'Hi! I am your Energy Price Alert Bot.\n'
            'Use /price to get current energy prices\n'
            'Use /help to see all available commands'
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /help is issued."""
        await update.message.reply_text(
            'Available commands:\n'
            '/start - Start the bot\n'
            '/price - Get current energy prices\n'
            '/help - Show this help message'
        )

    async def get_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            response = await self.price_agent.process(command_msg)

            if response and response.type == MessageType.PRICE_UPDATE:
                message = response.payload['formatted_message']
            else:
                message = "⚠️ Unable to fetch price data at the moment. Please try again later."

            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error getting price data: {str(e)}")
            await update.message.reply_text("❌ An error occurred while fetching price data.")

    async def initialize(self):
        """Initialize the bot and price agent."""
        try:
            logger.info("Starting bot initialization...")

            # Get token from environment variable
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            if not token:
                logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
                return False

            # Create the Application
            self.application = Application.builder().token(token).build()
            await self.application.initialize()

            # Add command handlers
            logger.info("Adding command handlers...")
            self.application.add_handler(CommandHandler("start", self.start))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CommandHandler("price", self.get_price))

            # Start the price agent
            logger.info("Starting LivePrice agent...")
            await self.price_agent.start()
            self.is_running = True

            logger.info("Bot initialization completed successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing bot: {str(e)}")
            return False

    async def run(self):
        """Run the bot."""
        try:
            if not self.is_running:
                if not await self.initialize():
                    return

            logger.info("Starting Telegram bot...")
            # Start the application
            await self.application.start()

            # Run the bot
            await self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            logger.error(f"Error running bot: {str(e)}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Shutdown the bot and cleanup resources."""
        try:
            logger.info("Shutting down bot...")
            self.is_running = False
            if self.price_agent:
                await self.price_agent.stop()
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
            logger.info("Bot shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")

def main():
    """Main entry point for the bot runner."""
    try:
        logger.info("Starting bot runner...")
        bot_runner = BotRunner()
        asyncio.run(bot_runner.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

if __name__ == '__main__':
    main()