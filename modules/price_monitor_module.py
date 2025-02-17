from typing import Dict, Any, Optional
import logging
from .base_module import BaseModule
from price_monitor import PriceMonitor

logger = logging.getLogger(__name__)

class PriceMonitorModule(BaseModule):
    """Module for monitoring real-time energy prices"""

    def __init__(self):
        super().__init__(
            name="price_monitor",
            description="Monitors real-time energy prices from providers"
        )
        self.price_monitor = PriceMonitor()

    async def initialize(self) -> bool:
        """Initialize price monitoring"""
        try:
            logger.info("Initializing price monitor module")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize price monitor: {str(e)}")
            return False

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process current price data"""
        try:
            hourly_data = await self.price_monitor.check_hourly_price()
            five_min_data = await self.price_monitor.check_five_min_price()

            # Handle non-numeric price values
            hourly_price = hourly_data.get("price", "N/A")
            five_min_price = five_min_data.get("price", "N/A")

            # Convert prices to float if possible, otherwise use None
            try:
                hourly_price = float(hourly_price) if hourly_price != "N/A" else None
            except (ValueError, TypeError):
                logger.warning(f"Invalid hourly price value: {hourly_price}")
                hourly_price = None

            try:
                five_min_price = float(five_min_price) if five_min_price != "N/A" else None
            except (ValueError, TypeError):
                logger.warning(f"Invalid 5-min price value: {five_min_price}")
                five_min_price = None

            return {
                "status": "success",
                "hourly_data": {
                    **hourly_data,
                    "price": hourly_price
                },
                "five_min_data": {
                    **five_min_data,
                    "price": five_min_price
                }
            }
        except Exception as e:
            logger.error(f"Error processing price data: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def get_notification_data(self) -> Optional[Dict[str, Any]]:
        """Get price data for notifications"""
        try:
            hourly_data = await self.price_monitor.check_hourly_price()
            five_min_data = await self.price_monitor.check_five_min_price()

            # Handle non-numeric price values
            hourly_price = hourly_data.get("price", "N/A")
            five_min_price = five_min_data.get("price", "N/A")

            # Convert prices to float if possible, otherwise use "N/A"
            try:
                hourly_price = float(hourly_price) if hourly_price != "N/A" else "N/A"
            except (ValueError, TypeError):
                logger.warning(f"Invalid hourly price value: {hourly_price}")
                hourly_price = "N/A"

            try:
                five_min_price = float(five_min_price) if five_min_price != "N/A" else "N/A"
            except (ValueError, TypeError):
                logger.warning(f"Invalid 5-min price value: {five_min_price}")
                five_min_price = "N/A"

            return {
                "current_price": hourly_price,
                "five_min_price": five_min_price,
                "trend": hourly_data.get("trend", "unknown"),
                "time": hourly_data.get("time", "N/A")
            }
        except Exception as e:
            logger.error(f"Error getting notification data: {str(e)}")
            return None