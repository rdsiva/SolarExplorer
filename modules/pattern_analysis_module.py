from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta
from .base_module import BaseModule

logger = logging.getLogger(__name__)

class PatternAnalysisModule(BaseModule):
    """Module for analyzing price patterns and trends"""
    
    def __init__(self):
        super().__init__(
            name="pattern_analysis",
            description="Analyzes price patterns and provides insights"
        )
        self.price_history = []
        self.analysis_window = timedelta(hours=24)
        
    async def initialize(self) -> bool:
        """Initialize pattern analysis"""
        try:
            logger.info("Initializing pattern analysis module")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize pattern analysis: {str(e)}")
            return False
            
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process price data and detect patterns"""
        try:
            current_price = data.get('current_price', 0)
            timestamp = data.get('timestamp', datetime.now())
            
            # Add to price history
            self.price_history.append({
                'price': current_price,
                'timestamp': timestamp
            })
            
            # Clean old data
            self._clean_old_data()
            
            # Analyze patterns
            volatility = self._calculate_volatility()
            trend = self._determine_trend()
            patterns = self._detect_patterns()
            
            return {
                "status": "success",
                "analysis": {
                    "volatility": volatility,
                    "trend": trend,
                    "patterns": patterns,
                    "data_points": len(self.price_history)
                }
            }
        except Exception as e:
            logger.error(f"Error in pattern analysis: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
            
    async def get_notification_data(self) -> Optional[Dict[str, Any]]:
        """Get pattern analysis data for notifications"""
        if not self.price_history:
            return None
            
        try:
            latest = self.price_history[-1]
            volatility = self._calculate_volatility()
            trend = self._determine_trend()
            
            return {
                "current_trend": trend,
                "volatility": volatility,
                "timestamp": latest['timestamp']
            }
        except Exception as e:
            logger.error(f"Error getting notification data: {str(e)}")
            return None
            
    def _clean_old_data(self):
        """Remove data points older than the analysis window"""
        cutoff = datetime.now() - self.analysis_window
        self.price_history = [
            point for point in self.price_history 
            if point['timestamp'] > cutoff
        ]
            
    def _calculate_volatility(self) -> float:
        """Calculate price volatility"""
        if len(self.price_history) < 2:
            return 0.0
            
        prices = [point['price'] for point in self.price_history]
        mean = sum(prices) / len(prices)
        squared_diff = sum((p - mean) ** 2 for p in prices)
        return (squared_diff / len(prices)) ** 0.5
            
    def _determine_trend(self) -> str:
        """Determine the current price trend"""
        if len(self.price_history) < 2:
            return "unknown"
            
        recent_prices = [point['price'] for point in self.price_history[-3:]]
        
        if all(x < y for x, y in zip(recent_prices, recent_prices[1:])):
            return "rising"
        elif all(x > y for x, y in zip(recent_prices, recent_prices[1:])):
            return "falling"
        return "stable"
            
    def _detect_patterns(self) -> Dict[str, Any]:
        """Detect specific price patterns"""
        if len(self.price_history) < 12:
            return {"detected": [], "confidence": 0}
            
        patterns = []
        confidence = 0
        
        # Detect price spikes
        prices = [point['price'] for point in self.price_history]
        mean = sum(prices) / len(prices)
        std_dev = (sum((p - mean) ** 2 for p in prices) / len(prices)) ** 0.5
        
        if abs(prices[-1] - mean) > 2 * std_dev:
            patterns.append("price_spike")
            confidence = 80
            
        # Detect cyclic patterns (simplified)
        if len(self.price_history) >= 24:
            hourly_prices = prices[-24:]
            peaks = [i for i in range(1, 23) if hourly_prices[i] > hourly_prices[i-1] and hourly_prices[i] > hourly_prices[i+1]]
            if len(peaks) >= 2 and abs(peaks[-1] - peaks[-2]) in (5, 6, 7):
                patterns.append("cyclic_pattern")
                confidence = max(confidence, 70)
                
        return {
            "detected": patterns,
            "confidence": confidence
        }
