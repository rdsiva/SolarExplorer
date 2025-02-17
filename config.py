import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
MIN_RATE = float(os.getenv('MIN_RATE', '3.0'))  # Default threshold 3.0 cents

# API Endpoints
FIVE_MIN_PRICE_URL = "https://srddev.pythonanywhere.com/api/fiveminPrice"
HOURLY_PRICE_URL = "https://srddev.pythonanywhere.com/api/hourlyprice"
HEALTH_CHECK_URL = "https://srddev.pythonanywhere.com/api/health"

# Check required environment variables
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set in environment variables")

if not TELEGRAM_CHAT_ID:
    logger.warning("TELEGRAM_CHAT_ID not set in environment variables")

logger.info(f"Configuration loaded - MIN_RATE: {MIN_RATE}")