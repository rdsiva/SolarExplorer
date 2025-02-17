from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime

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
        logger.info(f"Initialized {self.name} agent")

    @abstractmethod
    async def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming messages - must be implemented by child classes."""
        pass

    async def send_message(self, target_agent: str, message: Dict[str, Any]):
        """Send a message to another agent."""
        try:
            await self.message_queue.put({
                'target': target_agent,
                'source': self.name,
                'timestamp': datetime.utcnow().isoformat(),
                'payload': message
            })
            logger.debug(f"Message sent from {self.name} to {target_agent}")
        except Exception as e:
            logger.error(f"Error sending message from {self.name}: {str(e)}")

    async def receive_message(self) -> Dict[str, Any]:
        """Receive a message from the queue."""
        try:
            message = await self.message_queue.get()
            logger.debug(f"Message received by {self.name}")
            return message
        except Exception as e:
            logger.error(f"Error receiving message in {self.name}: {str(e)}")
            return {}

    async def start(self):
        """Start the agent."""
        try:
            self.running = True
            self.last_run = datetime.utcnow()
            logger.info(f"Started {self.name} agent")
        except Exception as e:
            logger.error(f"Error starting {self.name} agent: {str(e)}")
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
            'queue_size': self.message_queue.qsize()
        }

    def __str__(self):
        return f"{self.name} Agent ({self.running})"