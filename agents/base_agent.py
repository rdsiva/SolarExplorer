from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    def __init__(self, name):
        self.name = name
        self.running = False
        logger.info(f"Initialized {self.name} agent")

    @abstractmethod
    async def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming messages"""
        pass

    async def start(self):
        """Start the agent"""
        self.running = True
        logger.info(f"Started {self.name} agent")

    async def stop(self):
        """Stop the agent"""
        self.running = False
        logger.info(f"Stopped {self.name} agent")

    def __str__(self):
        return f"{self.name} Agent"