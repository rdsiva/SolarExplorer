import asyncio
import logging
from datetime import datetime
from minimal_bot import check, Update, ContextTypes
from telegram import Message, Chat
from unittest.mock import MagicMock, AsyncMock, patch
from price_monitor import PriceMonitor

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_price_check():
    """Test the price check command with ML-based predictions"""
    try:
        # Create mock update and context
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        # Set up mock message with AsyncMock for reply_text
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        update.effective_chat = MagicMock(spec=Chat)
        update.effective_chat.id = 12345

        # Mock price monitor responses
        mock_hourly_data = {
            'price': '2.9',
            'day_ahead_price': '3.1',
            'time': '2025-02-17 01:00 AM CST',
            'trend': 'stable',
            'price_range': {'min': 2.5, 'max': 3.5}
        }
        mock_five_min_data = {
            'price': '2.85',
            'time': '2025-02-17 01:04 AM CST',
            'trend': 'falling'
        }

        # Patch the price monitor methods
        with patch.object(PriceMonitor, 'check_hourly_price', return_value=mock_hourly_data), \
             patch.object(PriceMonitor, 'check_five_min_price', return_value=mock_five_min_data):

            # Call the check command
            await check(update, context)

            # Get all calls to reply_text
            calls = update.message.reply_text.call_args_list
            messages = []
            for call in calls:
                args, kwargs = call
                if args:
                    messages.append(args[0])

            # Log all messages for debugging
            for idx, message in enumerate(messages):
                logger.info(f"Message {idx + 1}:")
                logger.info(message)

            # Get the main response message (skip initial "Checking prices..." message)
            main_message = messages[1] if len(messages) > 1 else messages[0]

            # Verify essential sections are present
            assert "Current Energy Prices" in main_message, "Price section missing"
            assert "ML Price Prediction" in main_message, "ML prediction section missing"

            logger.info("Price check test completed successfully")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_price_check())