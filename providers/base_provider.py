from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List

class EnergyProvider(ABC):
    """Abstract base class for energy providers"""
    
    @abstractmethod
    def get_hourly_prices(self, date: datetime) -> List[Dict[str, Any]]:
        """Get hourly prices for a specific date"""
        pass
    
    @abstractmethod
    def get_current_average(self) -> float:
        """Get current hour average price"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of the energy provider"""
        pass
    
    @abstractmethod
    def get_price_unit(self) -> str:
        """Get the unit of price measurement (e.g., '¢/kWh')"""
        pass
