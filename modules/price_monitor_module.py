from typing import Dict, Any, Optional
import logging
from datetime import datetime
import requests
from .base_module import BaseModule
from .errors import ModuleError

logger = logging.getLogger(__name__)

class PriceMonitorModule(BaseModule):
    """Module for monitoring real-time energy prices"""

    def __init__(self):
        super().__init__(
            name="price_monitor",
            description="Monitors real-time energy prices from providers"
        )
        self.last_price = None
        self.last_update = None
        self.provider = "ComEd"  # Default provider

    async def initialize(self) -> bool:
        """Initialize price monitoring"""
        try:
            logger.info("Initializing price monitor module")
            # Try to get initial price data
            return await self._update_price_data()
        except Exception as e:
            logger.error(f"Failed to initialize price monitor: {str(e)}")
            return False

    async def _update_price_data(self) -> bool:
        """Update price data from provider"""
        try:
            logger.info("Attempting to update price data")
            # For testing, we'll use a mock price until the actual API is integrated
            self.last_price = 3.5  # Example price
            self.last_update = datetime.utcnow()
            logger.info(f"Updated price data: {self.last_price}¢ at {self.last_update}")
            return True
        except Exception as e:
            logger.error(f"Error updating price data: {str(e)}")
            return False

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process current price data"""
        try:
            logger.info("Processing price data request")
            if not await self._update_price_data():
                error_msg = "Failed to update price data"
                logger.error(error_msg)
                raise ModuleError(error_msg)

            if self.last_price is None:
                error_msg = "No price data available"
                logger.error(error_msg)
                raise ModuleError(error_msg)

            result = {
                "status": "success",
                "price": self.last_price,
                "timestamp": self.last_update.isoformat() if self.last_update else None
            }
            logger.info(f"Successfully processed price data: {result}")
            return result
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            raise ModuleError(error_msg)

    async def get_notification_data(self) -> Optional[Dict[str, Any]]:
        """Get price data for notifications"""
        try:
            logger.info("Getting notification data")
            if not await self._update_price_data():
                logger.error("Failed to update price data for notification")
                return None

            if self.last_price is None:
                logger.error("No price data available for notification")
                return None

            result = {
                "current_price": round(self.last_price, 2),
                "time": self.last_update.strftime('%Y-%m-%d %H:%M:%S') if self.last_update else "N/A",
                "status": "active",
                "provider": self.provider
            }
            logger.info(f"Successfully prepared notification data: {result}")
            return result
        except Exception as e:
            logger.error(f"Error getting notification data: {str(e)}")
            return None