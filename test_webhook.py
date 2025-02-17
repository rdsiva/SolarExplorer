import os
import logging
import requests
from telegram import Bot
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Your webhook URL
WEBHOOK_URL = "https://comed-price-telegram-notification.onrender.com/telegram/webhook"

async def test_webhook():
    """Test the webhook configuration"""
    try:
        # Create bot instance
        bot = Bot(token=os.environ.get("TELEGRAM_BOT_TOKEN"))

        # Get current webhook info
        webhook_info = await bot.get_webhook_info()
        logger.info(f"Current webhook info: {webhook_info.to_dict()}")

        # Test URL connectivity
        try:
            response = requests.get(WEBHOOK_URL.replace("/telegram/webhook", "/"))
            logger.info(f"Webhook server response: {response.status_code}")
            logger.info(f"Response content: {response.text}")
        except requests.RequestException as e:
            logger.error(f"Error connecting to webhook URL: {e}")

        # Set webhook
        success = await bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True
        )
        if success:
            logger.info("✅ Webhook set successfully")
        else:
            logger.error("❌ Failed to set webhook")

        # Get updated webhook info
        new_webhook_info = await bot.get_webhook_info()
        logger.info(f"Updated webhook info: {new_webhook_info.to_dict()}")

        if new_webhook_info.url == WEBHOOK_URL:
            logger.info("✅ Webhook URL matches expected URL")
        else:
            logger.error(f"❌ Webhook URL mismatch. Expected: {WEBHOOK_URL}, Got: {new_webhook_info.url}")

    except Exception as e:
        logger.error(f"Error testing webhook: {e}")

if __name__ == "__main__":
    asyncio.run(test_webhook())