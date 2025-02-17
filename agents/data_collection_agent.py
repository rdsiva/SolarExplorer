import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager
from .base_agent import BaseAgent
from .protocols.message_protocol import Message, MessageType
from price_monitor import PriceMonitor
from models import PriceHistory
from database import db
import os

logger = logging.getLogger(__name__)

class DataCollectionAgent(BaseAgent):
    def __init__(self):
        super().__init__("DataCollection")
        self.price_monitor = PriceMonitor()
        self.db = db

    @contextmanager
    def db_session(self):
        """Context manager for database sessions"""
        try:
            yield self.db.session
            self.db.session.commit()
        except Exception as e:
            self.db.session.rollback()
            raise e

    async def process(self, message: Message) -> Optional[Message]:
        """Process incoming messages and handle price data collection"""
        if message.payload.get("command") == "fetch_prices":
            try:
                hourly_data = await self.price_monitor.check_hourly_price()

                # Store price data in database using PriceHistory model
                with self.db_session() as session:
                    price_record = PriceHistory(
                        hourly_price=float(hourly_data.get('price', 0)),
                        day_ahead_price=float(hourly_data.get('day_ahead_price', 0)) if 'day_ahead_price' in hourly_data else None
                    )
                    session.add(price_record)
                    logger.info(f"Stored price data: {hourly_data}")

                return Message(
                    msg_type=MessageType.RESPONSE,
                    source=self.name,
                    target=message.source,
                    payload={
                        "status": "success",
                        "data": {
                            "hourly_data": hourly_data
                        }
                    }
                )
            except Exception as e:
                logger.error(f"Error collecting price data: {str(e)}")
                return Message(
                    msg_type=MessageType.ERROR,
                    source=self.name,
                    target=message.source,
                    payload={
                        "status": "error",
                        "message": f"Failed to collect price data: {str(e)}"
                    }
                )

        return Message(
            msg_type=MessageType.ERROR,
            source=self.name,
            target=message.source,
            payload={
                "status": "error",
                "message": "Unknown command"
            }
        )

    async def start(self):
        """Start the agent and initialize database connection"""
        await super().start()
        logger.info(f"{self.name} agent started")