"""Custom exceptions for the modules package"""

class ModuleError(Exception):
    """Custom exception for module-related errors"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)