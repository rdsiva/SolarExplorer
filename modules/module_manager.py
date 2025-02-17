from typing import Dict, List, Type, Any
import logging
import os
from datetime import datetime
from .base_module import BaseModule

logger = logging.getLogger(__name__)

class ModuleManager:
    """Manages all pluggable modules in the system"""

    def __init__(self):
        self.modules: Dict[str, BaseModule] = {}
        self.module_errors: Dict[str, List[Dict[str, Any]]] = {}
        self.admin_chat_id = os.environ.get('ADMIN_CHAT_ID')
        self._notification_callback = None

    def register_module(self, module: BaseModule) -> bool:
        """Register a new module"""
        try:
            if module.name in self.modules:
                logger.warning(f"Module {module.name} already registered")
                return False

            self.modules[module.name] = module
            self.module_errors[module.name] = []
            logger.info(f"Registered module: {module.name}")
            return True
        except Exception as e:
            logger.error(f"Error registering module {module.name}: {str(e)}")
            return False

    async def initialize_modules(self) -> bool:
        """Initialize all registered modules"""
        success = True
        for name, module in self.modules.items():
            try:
                if not await module.initialize():
                    logger.error(f"Failed to initialize module: {name}")
                    success = False
                    await self._notify_admin(f"⚠️ Module {name} failed to initialize")
            except Exception as e:
                logger.error(f"Error initializing module {name}: {str(e)}")
                success = False
                await self._notify_admin(f"❌ Error initializing {name}: {str(e)}")
        return success

    def enable_module(self, module_name: str) -> bool:
        """Enable a specific module"""
        if module_name not in self.modules:
            logger.error(f"Module {module_name} not found")
            return False

        try:    
            self.modules[module_name].enable()
            logger.info(f"Module {module_name} enabled successfully")
            return True
        except Exception as e:
            logger.error(f"Error enabling module {module_name}: {str(e)}")
            return False

    def disable_module(self, module_name: str) -> bool:
        """Disable a specific module"""
        if module_name not in self.modules:
            logger.error(f"Module {module_name} not found")
            return False

        try:
            self.modules[module_name].disable()
            logger.info(f"Module {module_name} disabled successfully")
            return True
        except Exception as e:
            logger.error(f"Error disabling module {module_name}: {str(e)}")
            return False

    def get_enabled_modules(self) -> List[str]:
        """Get list of enabled module names"""
        return [name for name, module in self.modules.items() if module.is_enabled()]

    def get_all_modules(self) -> List[Dict[str, Any]]:
        """Get information about all registered modules"""
        return [
            {
                "name": module.name,
                "description": module.description,
                "enabled": module.is_enabled(),
                "errors": self.module_errors.get(module.name, [])
            }
            for module in self.modules.values()
        ]

    async def process_with_enabled_modules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data through all enabled modules with error handling"""
        results = {}

        for name, module in self.modules.items():
            if module.is_enabled():
                try:
                    logger.info(f"Processing data with module: {name}")
                    results[name] = await module.process(data)
                    # Clear any previous errors if successful
                    self._clear_module_errors(name)
                    logger.info(f"Successfully processed data with module: {name}")
                except Exception as e:
                    error_msg = f"Error processing in module {name}: {str(e)}"
                    logger.error(error_msg)
                    self._record_module_error(name, str(e))
                    await self._notify_admin(f"⚠️ Module {name} failed: {str(e)}")

                    # For core price_monitor module, raise the error
                    if name == "price_monitor":
                        logger.error("Critical error in price_monitor module")
                        raise

                    # For other modules, continue with partial results
                    results[name] = {"error": str(e)}
                    logger.warning(f"Continuing execution without module {name}")

        return results

    async def get_notification_data(self) -> Dict[str, Any]:
        """Get notification data from all enabled modules with error handling"""
        notification_data = {}

        for name, module in self.modules.items():
            if module.is_enabled():
                try:
                    logger.info(f"Getting notification data from module: {name}")
                    module_data = await module.get_notification_data()
                    if module_data:
                        notification_data[name] = module_data
                        logger.info(f"Successfully got notification data from module: {name}")
                except Exception as e:
                    error_msg = f"Error getting notification data from {name}: {str(e)}"
                    logger.error(error_msg)
                    self._record_module_error(name, str(e))
                    await self._notify_admin(f"⚠️ Module {name} notification failed: {str(e)}")

                    # Skip failed module's data without breaking functionality
                    logger.warning(f"Skipping notification data from module {name}")
                    continue

        return notification_data

    def _record_module_error(self, module_name: str, error_msg: str) -> None:
        """Record an error for a specific module"""
        if module_name not in self.module_errors:
            self.module_errors[module_name] = []

        self.module_errors[module_name].append({
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_msg
        })

        # Keep only last 10 errors
        if len(self.module_errors[module_name]) > 10:
            self.module_errors[module_name] = self.module_errors[module_name][-10:]

    def _clear_module_errors(self, module_name: str) -> None:
        """Clear errors for a specific module"""
        self.module_errors[module_name] = []

    async def _notify_admin(self, message: str) -> None:
        """Notify admin about module errors"""
        if not self.admin_chat_id:
            logger.warning("Admin chat ID not configured, skipping notification")
            return

        if self._notification_callback:
            try:
                logger.info(f"Sending admin notification: {message}")
                await self._notification_callback(self.admin_chat_id, message)
            except Exception as e:
                logger.error(f"Failed to send admin notification: {str(e)}")

    def set_notification_callback(self, callback):
        """Set callback for admin notifications"""
        self._notification_callback = callback