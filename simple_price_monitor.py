import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PriceData:
    """Simple data class to hold price information"""
    current_price: float
    day_ahead_price: Optional[float]
    hourly_average: Optional[float]
    timestamp: datetime
    trend: str = "unknown"

class SimplePriceMonitor:
    """Simplified price monitoring implementation"""
    
    def __init__(self):
        self.pricing_table_url = "https://hourlypricing.comed.com/pricing-table/"
        self.hourly_api_url = "https://hourlypricing.comed.com/api"
        
    def get_current_prices(self) -> PriceData:
        """Fetch current price data from ComEd"""
        try:
            # Get the current hour's price from the pricing table
            response = requests.get(self.pricing_table_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            price_table = soup.find('table', {'class': 'pricing-table'})
            
            if not price_table:
                raise ValueError("Price table not found on page")
                
            # Get the most recent price (first row after header)
            rows = price_table.find_all('tr')[1:2]  # Get just the first data row
            if not rows:
                raise ValueError("No price data found in table")
                
            cols = rows[0].find_all('td')
            if len(cols) < 2:
                raise ValueError("Invalid price table format")
                
            # Parse price and time
            current_price = float(cols[1].text.strip().replace('¢', ''))
            time_str = cols[0].text.strip()
            
            # Get hourly average
            avg_response = requests.get(f"{self.hourly_api_url}?type=currenthouraverage")
            avg_response.raise_for_status()
            avg_data = avg_response.json()
            hourly_average = float(avg_data[0]['price']) if avg_data else None
            
            # Parse the time
            time_obj = datetime.strptime(time_str, "%I:%M %p")
            current_time = datetime.now(ZoneInfo("America/Chicago"))
            timestamp = current_time.replace(
                hour=time_obj.hour,
                minute=time_obj.minute,
                second=0,
                microsecond=0
            )
            
            # Determine trend (simple implementation)
            trend = "unknown"
            if hourly_average:
                if current_price > hourly_average:
                    trend = "rising"
                elif current_price < hourly_average:
                    trend = "falling"
                else:
                    trend = "stable"
            
            return PriceData(
                current_price=current_price,
                day_ahead_price=None,  # We'll implement this later
                hourly_average=hourly_average,
                timestamp=timestamp,
                trend=trend
            )
            
        except Exception as e:
            logger.error(f"Error fetching price data: {str(e)}", exc_info=True)
            raise
    
    def format_alert_message(self, price_data: PriceData) -> str:
        """Format price data into a readable alert message"""
        message = (
            "📊 ComEd Price Update\n\n"
            f"Current Price: {price_data.current_price:.2f}¢\n"
            f"Hourly Average: {price_data.hourly_average:.2f}¢\n"
            f"Trend: {price_data.trend.capitalize()}\n"
            f"\n⏰ As of: {price_data.timestamp.strftime('%I:%M %p %Z')}"
        )
        return message

def main():
    """Test the simple price monitor"""
    try:
        monitor = SimplePriceMonitor()
        price_data = monitor.get_current_prices()
        message = monitor.format_alert_message(price_data)
        print(message)
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
