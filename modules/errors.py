"""Custom exceptions for the modules package"""

class ModuleError(Exception):
    """Custom exception for module-related errors"""
    def __init__(self, module_name: str, message: str):
        self.module_name = module_name
        self.message = message
        super().__init__(f"[{module_name}] {message}")
