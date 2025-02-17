from typing import Dict, List, Type, Any
import logging
from .base_module import BaseModule

logger = logging.getLogger(__name__)

class ModuleManager:
    """Manages all pluggable modules in the system"""
    
    def __init__(self):
        self.modules: Dict[str, BaseModule] = {}
        
    def register_module(self, module: BaseModule) -> bool:
        """Register a new module"""
        try:
            if module.name in self.modules:
                logger.warning(f"Module {module.name} already registered")
                return False
                
            self.modules[module.name] = module
            logger.info(f"Registered module: {module.name}")
            return True
        except Exception as e:
            logger.error(f"Error registering module {module.name}: {str(e)}")
            return False
            
    async def initialize_modules(self) -> bool:
        """Initialize all registered modules"""
        try:
            for name, module in self.modules.items():
                if not await module.initialize():
                    logger.error(f"Failed to initialize module: {name}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Error initializing modules: {str(e)}")
            return False
            
    def enable_module(self, module_name: str) -> bool:
        """Enable a specific module"""
        if module_name not in self.modules:
            logger.error(f"Module {module_name} not found")
            return False
            
        self.modules[module_name].enable()
        return True
        
    def disable_module(self, module_name: str) -> bool:
        """Disable a specific module"""
        if module_name not in self.modules:
            logger.error(f"Module {module_name} not found")
            return False
            
        self.modules[module_name].disable()
        return True
        
    def get_enabled_modules(self) -> List[str]:
        """Get list of enabled module names"""
        return [name for name, module in self.modules.items() if module.is_enabled()]
        
    def get_all_modules(self) -> List[Dict[str, Any]]:
        """Get information about all registered modules"""
        return [
            {
                "name": module.name,
                "description": module.description,
                "enabled": module.is_enabled()
            }
            for module in self.modules.values()
        ]
        
    async def process_with_enabled_modules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data through all enabled modules"""
        results = {}
        
        for name, module in self.modules.items():
            if module.is_enabled():
                try:
                    results[name] = await module.process(data)
                except Exception as e:
                    logger.error(f"Error processing in module {name}: {str(e)}")
                    results[name] = {"error": str(e)}
                    
        return results
        
    async def get_notification_data(self) -> Dict[str, Any]:
        """Get notification data from all enabled modules"""
        notification_data = {}
        
        for name, module in self.modules.items():
            if module.is_enabled():
                try:
                    module_data = await module.get_notification_data()
                    if module_data:
                        notification_data[name] = module_data
                except Exception as e:
                    logger.error(f"Error getting notification data from {name}: {str(e)}")
                    
        return notification_data
