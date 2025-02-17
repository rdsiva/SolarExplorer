from .base_module import BaseModule
from .module_manager import ModuleManager
from .errors import ModuleError

# Lazy imports to avoid circular dependencies
def get_dashboard_module():
    from .dashboard_module import DashboardModule
    return DashboardModule

def get_price_monitor_module():
    from .price_monitor_module import PriceMonitorModule
    return PriceMonitorModule

def get_pattern_analysis_module():
    from .pattern_analysis_module import PatternAnalysisModule
    return PatternAnalysisModule

def get_ml_prediction_module():
    from .ml_prediction_module import MLPredictionModule 
    return MLPredictionModule

__all__ = [
    'BaseModule',
    'ModuleManager',
    'ModuleError',
    'get_dashboard_module',
    'get_price_monitor_module',
    'get_pattern_analysis_module',
    'get_ml_prediction_module'
]