import logging
import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import json

from .base_agent import BaseAgent
from .protocols.message_protocol import MessageType, MessagePriority, Message

logger = logging.getLogger(__name__)

class LivePriceAgent(BaseAgent):
    """Agent responsible for monitoring real-time energy prices from ComEd API."""

    def __init__(self, name: str = "LivePrice", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.base_url = "https://hourlypricing.comed.com/api"
        self.price_threshold = self.config.get('price_threshold', 3.0)
        self.check_interval = self.config.get('check_interval', 300)  # 5 minutes default

        # Subscribe to relevant message types
        self.subscribe(MessageType.COMMAND)
        self.subscribe(MessageType.PREFERENCE_UPDATE)

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

    async def process(self, message: Message) -> Optional[Message]:
        """Process incoming messages and return price data."""
        try:
            if message.type == MessageType.COMMAND and message.payload.get('command') == 'get_price':
                price_data = await self.get_current_price()
                if price_data:
                    alert_message = self.format_alert_message(price_data)

                    # Send price update to all interested agents
                    price_message = {
                        'data': price_data,
                        'formatted_message': alert_message,
                        'threshold_exceeded': price_data['current_hour'] > self.price_threshold
                    }

                    # If threshold exceeded, send with high priority
                    priority = (MessagePriority.HIGH 
                              if price_data['current_hour'] > self.price_threshold 
                              else MessagePriority.NORMAL)

                    return Message(
                        msg_type=MessageType.PRICE_UPDATE,
                        source=self.name,
                        target=message.source,
                        payload=price_message,
                        priority=priority,
                        correlation_id=message.correlation_id
                    )

            elif message.type == MessageType.PREFERENCE_UPDATE:
                # Update agent preferences
                if 'price_threshold' in message.payload:
                    self.price_threshold = float(message.payload['price_threshold'])
                if 'check_interval' in message.payload:
                    self.check_interval = int(message.payload['check_interval'])

                return Message(
                    msg_type=MessageType.RESPONSE,
                    source=self.name,
                    target=message.source,
                    payload={'status': 'preferences_updated'},
                    correlation_id=message.correlation_id
                )

        except Exception as e:
            logger.error(f"Error in LivePriceAgent process: {str(e)}")
            return Message(
                msg_type=MessageType.ERROR,
                source=self.name,
                target=message.source,
                payload={'error': str(e)},
                correlation_id=message.correlation_id
            )

    async def start(self):
        """Start the price monitoring loop."""
        await super().start()
        while self.running:
            try:
                price_data = await self.get_current_price()
                if price_data:
                    # Process price data as if received a command
                    command_message = Message(
                        msg_type=MessageType.COMMAND,
                        source='system',
                        target=self.name,
                        payload={'command': 'get_price'}
                    )
                    await self.process(command_message)
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in price monitoring loop: {str(e)}")
                await asyncio.sleep(60)  # Wait before retry on error