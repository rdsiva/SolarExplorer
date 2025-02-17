from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BaseModule(ABC):
    """Base class for all pluggable modules"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.enabled = False
        self.config: Dict[str, Any] = {}
        
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
        logger.info(f"Module {self.name} enabled")
        
    def disable(self):
        """Disable this module"""
        self.enabled = False
        logger.info(f"Module {self.name} disabled")
        
    def is_enabled(self) -> bool:
        """Check if module is enabled"""
        return self.enabled
        
    def update_config(self, config: Dict[str, Any]):
        """Update module configuration"""
        self.config.update(config)
        logger.info(f"Updated config for module {self.name}")
