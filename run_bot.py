import asyncio
import logging
from bot import EnergyPriceBot

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Run the Telegram bot"""
    try:
        bot = EnergyPriceBot()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot failed to start: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
