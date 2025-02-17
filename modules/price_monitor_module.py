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
        self.api_endpoints = {
            "hourly": "https://hourlypricing.comed.com/api?type=currenthouraverage",
            "5min": "https://hourlypricing.comed.com/api?type=5minutefeed",
            "daily": "https://hourlypricing.comed.com/api?type=day"
        }

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

            # Try to get current hour average first
            response = requests.get(self.api_endpoints["hourly"])
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    self.last_price = float(data[0].get('price', 0))
                    self.last_update = datetime.utcnow()
                    logger.info(f"Updated price data: {self.last_price}¢ at {self.last_update}")
                    return True

            # If hourly fails, try 5-minute data
            response = requests.get(self.api_endpoints["5min"])
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    self.last_price = float(data[0].get('price', 0))
                    self.last_update = datetime.utcnow()
                    logger.info(f"Updated price data from 5min feed: {self.last_price}¢ at {self.last_update}")
                    return True

            logger.error("Failed to fetch price data from all endpoints")
            return False

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

            # Get additional data for comprehensive price info
            hourly_response = requests.get(self.api_endpoints["hourly"])
            five_min_response = requests.get(self.api_endpoints["5min"])

            result = {
                "status": "success",
                "current_price": self.last_price,
                "timestamp": self.last_update.isoformat() if self.last_update else None,
                "hourly_data": hourly_response.json() if hourly_response.status_code == 200 else [],
                "five_min_data": five_min_response.json() if five_min_response.status_code == 200 else []
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
                "provider": self.provider,
                "alert_threshold": self.config.get("alert_threshold", 3.0)  # Default threshold
            }

            # Add additional data from enabled modules through ModuleManager
            if hasattr(self, '_bot') and self._bot:
                module_manager = getattr(self._bot.application, 'module_manager', None)
                if module_manager:
                    enabled_modules = module_manager.get_enabled_modules()

                    # Add pattern analysis data if enabled
                    if "pattern_analysis" in enabled_modules:
                        pattern_module = module_manager.get_module("pattern_analysis")
                        if pattern_module:
                            pattern_data = await pattern_module.get_notification_data()
                            if pattern_data:
                                result["patterns"] = pattern_data

                    # Add ML prediction data if enabled
                    if "ml_prediction" in enabled_modules:
                        ml_module = module_manager.get_module("ml_prediction")
                        if ml_module:
                            ml_data = await ml_module.get_notification_data()
                            if ml_data:
                                result["predictions"] = ml_data

            logger.info(f"Successfully prepared notification data: {result}")
            return result

        except Exception as e:
            logger.error(f"Error getting notification data: {str(e)}")
            return None

    async def get_price_data(self) -> Optional[Dict[str, Any]]:
        """Get basic price data including current price and average"""
        try:
            logger.info("Getting basic price data")
            if not await self._update_price_data():
                logger.error("Failed to update price data")
                return None

            if self.last_price is None:
                logger.error("No price data available")
                return None

            # Get hourly average
            try:
                response = requests.get(self.api_endpoints["hourly"])
                if response.status_code == 200:
                    data = response.json()
                    average_price = float(data[0].get('price', 0)) if data else None
                else:
                    average_price = None
            except Exception as e:
                logger.error(f"Error getting average price: {str(e)}")
                average_price = None

            result = {
                'current_price': round(self.last_price, 2),
                'average_price': round(average_price, 2) if average_price is not None else "N/A",
                'timestamp': self.last_update.isoformat() if self.last_update else None
            }

            logger.info(f"Successfully prepared basic price data: {result}")
            return result

        except Exception as e:
            logger.error(f"Error getting basic price data: {str(e)}")
            return None