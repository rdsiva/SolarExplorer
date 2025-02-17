from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class BaseModule(ABC):
    """Base class for all pluggable modules"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.enabled = False
        self.config: Dict[str, Any] = {}
        self.last_error: Optional[str] = None
        self.last_error_time: Optional[datetime] = None
        self.consecutive_failures = 0
        self.status = "initialized"

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

    def record_error(self, error: str):
        """Record an error occurrence"""
        self.last_error = error
        self.last_error_time = datetime.utcnow()
        self.consecutive_failures += 1
        self.status = "error"
        logger.error(f"Module {self.name} error: {error}")

    def clear_errors(self):
        """Clear error state after successful operation"""
        self.last_error = None
        self.last_error_time = None
        self.consecutive_failures = 0
        self.status = "enabled" if self.enabled else "disabled"

    def get_status(self) -> Dict[str, Any]:
        """Get detailed module status"""
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "status": self.status,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "consecutive_failures": self.consecutive_failures
        }

    async def safe_process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Safely process data with error handling"""
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
            self.record_error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "module": self.name
            }