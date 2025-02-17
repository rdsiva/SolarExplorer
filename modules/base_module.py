from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from datetime import datetime
import os
from telegram import Bot

logger = logging.getLogger(__name__)

class BaseModule(ABC):
    """Base class for all pluggable modules with independent error handling"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.enabled = False
        self.config: Dict[str, Any] = {}
        self.last_error: Optional[str] = None
        self.last_error_time: Optional[datetime] = None
        self.consecutive_failures = 0
        self.status = "initialized"
        self.admin_chat_id = os.environ.get("ADMIN_CHAT_ID")
        self._bot: Optional[Bot] = None

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the module. Return True if successful."""
        pass

    @abstractmethod
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data and return results"""
        pass

    @abstractmethod
    async def get_notification_data(self) -> Optional[Dict[str, Any]]:
        """Get data to be included in notifications when this module is enabled"""
        pass

    def set_bot(self, bot: Bot):
        """Set the bot instance for admin notifications"""
        self._bot = bot

    async def notify_admin(self, message: str):
        """Send notification to admin if admin chat ID is set"""
        if self.admin_chat_id and self._bot:
            try:
                await self._bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=f"🤖 Module Alert ({self.name}):\n{message}"
                )
            except Exception as e:
                logger.error(f"Failed to send admin notification: {str(e)}")

    def enable(self):
        """Enable this module"""
        self.enabled = True
        self.status = "enabled"
        logger.info(f"Module {self.name} enabled")

    def disable(self):
        """Disable this module"""
        self.enabled = False
        self.status = "disabled"
        logger.info(f"Module {self.name} disabled")

    def is_enabled(self) -> bool:
        """Check if module is enabled"""
        return self.enabled

    def update_config(self, config: Dict[str, Any]):
        """Update module configuration"""
        self.config.update(config)
        logger.info(f"Updated config for module {self.name}")

    async def record_error(self, error: str):
        """Record an error occurrence and notify admin"""
        self.last_error = error
        self.last_error_time = datetime.utcnow()
        self.consecutive_failures += 1
        self.status = "error"

        error_msg = (
            f"Module {self.name} error:\n"
            f"Error: {error}\n"
            f"Consecutive failures: {self.consecutive_failures}\n"
            f"Time: {self.last_error_time.isoformat()}"
        )
        logger.error(error_msg)
        await self.notify_admin(error_msg)

    def clear_errors(self):
        """Clear error state after successful operation"""
        if self.consecutive_failures > 0:
            self.last_error = None
            self.last_error_time = None
            self.consecutive_failures = 0
            self.status = "enabled" if self.enabled else "disabled"
            logger.info(f"Module {self.name} errors cleared")

    def get_status(self) -> Dict[str, Any]:
        """Get detailed module status"""
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "status": self.status,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "consecutive_failures": self.consecutive_failures,
            "is_critical": self.name == "price_monitor"
        }

    async def safe_process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Safely process data with error handling and recovery"""
        try:
            if not self.enabled:
                return {
                    "status": "disabled",
                    "message": f"Module {self.name} is disabled"
                }

            result = await self.process(data)
            self.clear_errors()
            return result

        except Exception as e:
            error_msg = str(e)
            await self.record_error(error_msg)

            # For non-critical modules, return a graceful failure
            if self.name != "price_monitor":
                return {
                    "status": "error",
                    "message": f"Module {self.name} encountered an error but system continues",
                    "error": error_msg
                }
            else:
                # For critical modules, raise the error
                raise