import logging
from typing import Dict, Any
from .base_agent import BaseAgent
from price_monitor import PriceMonitor

logger = logging.getLogger(__name__)

class DataCollectionAgent(BaseAgent):
    def __init__(self):
        super().__init__("DataCollection")
        self.price_monitor = PriceMonitor()

    async def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if message.get("command") == "fetch_prices":
            try:
                five_min_data = await self.price_monitor.check_five_min_price()
                hourly_data = await self.price_monitor.check_hourly_price()
                return {
                    "status": "success",
                    "data": {
                        "five_min_data": five_min_data,
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