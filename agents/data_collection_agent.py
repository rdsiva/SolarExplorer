import logging
from typing import Dict, Any
from .base_agent import BaseAgent
from price_monitor import PriceMonitor
from models import PriceHistory
from app import app

logger = logging.getLogger(__name__)

class DataCollectionAgent(BaseAgent):
    def __init__(self):
        super().__init__("DataCollection")
        self.price_monitor = PriceMonitor()

    async def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if message.get("command") == "fetch_prices":
            try:
                hourly_data = await self.price_monitor.check_hourly_price()

                # Use Flask application context for database operations
                with app.app_context():
                    # Store price data in database
                    PriceHistory.add_price_data(
                        hourly_price=float(hourly_data.get('price', 0)),
                        day_ahead_price=float(hourly_data.get('day_ahead_price', 0)) if 'day_ahead_price' in hourly_data else None
                    )

                return {
                    "status": "success",
                    "data": {
                        "hourly_data": hourly_data
                    }
                }
            except Exception as e:
                logger.error(f"Error collecting price data: {str(e)}")
                return {
                    "status": "error",
                    "message": f"Failed to collect price data: {str(e)}"
                }
        return {
            "status": "error",
            "message": "Unknown command"
        }