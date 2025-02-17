from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .protocols.message_protocol import Message, MessageType, MessagePriority

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Base class for all agents in the system."""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """Initialize the agent with a name and optional configuration."""
        self.name = name
        self.config = config or {}
        self.running = False
        self.last_run = None
        self.message_queue = asyncio.Queue()
        self.subscriptions = set()  # Message types the agent is interested in
        logger.info(f"Initialized {self.name} agent")

    @abstractmethod
    async def process(self, message: Message) -> Optional[Message]:
        """Process incoming messages - must be implemented by child classes."""
        pass

    def subscribe(self, msg_type: MessageType):
        """Subscribe to a specific message type."""
        self.subscriptions.add(msg_type)
        logger.debug(f"{self.name} subscribed to {msg_type.value}")

    def unsubscribe(self, msg_type: MessageType):
        """Unsubscribe from a specific message type."""
        self.subscriptions.discard(msg_type)
        logger.debug(f"{self.name} unsubscribed from {msg_type.value}")

    async def send_message(
        self,
        target_agent: str,
        payload: Dict[str, Any],
        msg_type: MessageType,
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: Optional[str] = None
    ) -> None:
        """Send a message to another agent."""
        try:
            message = Message(
                msg_type=msg_type,
                source=self.name,
                target=target_agent,
                payload=payload,
                priority=priority,
                correlation_id=correlation_id
            )

            if not message.validate():
                logger.error(f"Invalid message format from {self.name}")
                return

            await self.message_queue.put(message)
            logger.debug(f"Message sent from {self.name} to {target_agent}")
        except Exception as e:
            logger.error(f"Error sending message from {self.name}: {str(e)}")

    async def receive_message(self) -> Optional[Message]:
        """Receive a message from the queue."""
        try:
            message = await self.message_queue.get()
            if isinstance(message, dict):
                message = Message.from_dict(message)

            # Only process messages if we're subscribed to this type
            if message.type in self.subscriptions or not self.subscriptions:
                logger.debug(f"Message received by {self.name}")
                return message
            return None
        except Exception as e:
            logger.error(f"Error receiving message in {self.name}: {str(e)}")
            return None

    async def start(self):
        """Start the agent."""
        try:
            self.running = True
            self.last_run = datetime.utcnow()
            logger.info(f"Started {self.name} agent")

            # Start message processing loop
            while self.running:
                message = await self.receive_message()
                if message:
                    response = await self.process(message)
                    if response:
                        await self.send_message(
                            target_agent=response.target,
                            payload=response.payload,
                            msg_type=response.type,
                            priority=response.priority,
                            correlation_id=response.correlation_id
                        )
        except Exception as e:
            logger.error(f"Error in {self.name} agent message loop: {str(e)}")
            self.running = False

    async def stop(self):
        """Stop the agent."""
        try:
            self.running = False
            logger.info(f"Stopped {self.name} agent")
        except Exception as e:
            logger.error(f"Error stopping {self.name} agent: {str(e)}")

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the agent."""
        return {
            'name': self.name,
            'running': self.running,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'queue_size': self.message_queue.qsize(),
            'subscriptions': [sub.value for sub in self.subscriptions]
        }

    def __str__(self):
        return f"{self.name} Agent ({self.running})"