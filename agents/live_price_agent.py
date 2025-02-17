import logging
import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import json

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class LivePriceAgent(BaseAgent):
    """Agent responsible for monitoring real-time energy prices from ComEd API."""

    def __init__(self, name: str = "LivePrice", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.base_url = "https://hourlypricing.comed.com/api"
        self.price_threshold = self.config.get('price_threshold', 3.0)
        self.check_interval = self.config.get('check_interval', 300)  # 5 minutes default

    async def get_current_price(self) -> Dict[str, Any]:
        """Fetch current price from ComEd API."""
        try:
            async with aiohttp.ClientSession() as session:
                # Get data from different endpoints using the same session
                endpoints = ['currenthouraverage', 'dayahead', '5minutefeed']
                responses = {}

                for endpoint in endpoints:
                    try:
                        url = f"{self.base_url}?type={endpoint}"
                        async with session.get(url) as response:
                            if response.status != 200:
                                logger.error(f"Error fetching {endpoint} data: {response.status}")
                                continue

                            if 'application/json' not in response.headers.get('content-type', ''):
                                logger.error(f"Invalid content type for {endpoint}")
                                continue

                            data = await response.json()
                            if data and isinstance(data, list) and data[0].get('price'):
                                responses[endpoint] = float(data[0]['price'])
                            else:
                                logger.error(f"Invalid data format from {endpoint}")
                    except Exception as e:
                        logger.error(f"Error fetching {endpoint} data: {str(e)}")

                if not responses:
                    logger.error("Failed to fetch any price data")
                    return {}

                return {
                    'current_hour': responses.get('currenthouraverage', 0.0),
                    'day_ahead': responses.get('dayahead', 0.0),
                    'five_min': responses.get('5minutefeed', 0.0),
                    'timestamp': datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Error in get_current_price: {str(e)}")
            return {}

    def format_alert_message(self, price_data: Dict[str, Any]) -> str:
        """Format price data into a Telegram message."""
        if not price_data:
            return "⚠️ Error fetching price data"

        return (
            f"🔔 ComEd Energy Price Update\n\n"
            f"⚡ Current Hour Average: {price_data['current_hour']:.2f}¢/kWh\n"
            f"📊 Day Ahead Price: {price_data['day_ahead']:.2f}¢/kWh\n"
            f"⏱️ Latest 5-min Price: {price_data['five_min']:.2f}¢/kWh\n"
            f"🕒 Time: {datetime.fromisoformat(price_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )

    async def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming messages and return price data."""
        try:
            command = message.get('command', 'get_price')

            if command == 'get_price':
                price_data = await self.get_current_price()
                if price_data:
                    alert_message = self.format_alert_message(price_data)
                    # Notify other agents if price exceeds threshold
                    if price_data['current_hour'] > self.price_threshold:
                        await self.send_message('notification', {
                            'type': 'price_alert',
                            'message': alert_message,
                            'data': price_data
                        })
                    return {
                        'status': 'success',
                        'data': price_data,
                        'message': alert_message
                    }

            return {'status': 'error', 'message': 'Invalid command or no data available'}

        except Exception as e:
            logger.error(f"Error in LivePriceAgent process: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    async def start(self):
        """Start the price monitoring loop."""
        await super().start()
        while self.running:
            try:
                price_data = await self.get_current_price()
                if price_data:
                    await self.process({'command': 'get_price'})
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in price monitoring loop: {str(e)}")
                await asyncio.sleep(60)  # Wait before retry on error