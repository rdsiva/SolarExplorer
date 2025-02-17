import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for better troubleshooting
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PriceData:
    """Simple data class to hold price information"""
    price: float
    timestamp: datetime
    day_ahead_price: Optional[float] = None
    hourly_average: Optional[float] = None
    trend: str = "unknown"

class ComedPriceMonitor:
    """Simple price monitoring for ComEd"""

    def __init__(self):
        self.pricing_table_url = "https://hourlypricing.comed.com/pricing-table/"
        self.hourly_api_url = "https://hourlypricing.comed.com/api"

    def get_current_prices(self) -> PriceData:
        """Get current price data from ComEd"""
        try:
            logger.debug("Fetching current price data...")

            # Get current price from pricing table
            current_price = self._get_current_price()
            logger.debug(f"Current price: {current_price}")

            # Get hourly average
            hourly_average = self._get_hourly_average()
            logger.debug(f"Hourly average: {hourly_average}")

            # Determine trend
            trend = self._calculate_trend(current_price, hourly_average)
            logger.debug(f"Price trend: {trend}")

            return PriceData(
                price=current_price,
                timestamp=datetime.now(ZoneInfo("America/Chicago")),
                hourly_average=hourly_average,
                trend=trend
            )

        except Exception as e:
            logger.error(f"Error fetching price data: {str(e)}", exc_info=True)
            raise

    def _get_current_price(self) -> float:
        """Get current price from pricing table"""
        logger.debug("Fetching price from pricing table...")
        response = requests.get(self.pricing_table_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        price_table = soup.find('table', {'class': 'pricing-table'})

        if not price_table:
            raise ValueError("Price table not found")

        # Get first row after header
        rows = price_table.find_all('tr')
        if len(rows) < 2:  # Need at least header and one data row
            raise ValueError("No price data found")

        # Get the first data row (second row in table)
        data_row = rows[1]
        cols = data_row.find_all('td')
        if len(cols) < 2:
            raise ValueError("Invalid price table format")

        price_text = cols[1].text.strip().replace('¢', '')
        try:
            return float(price_text)
        except ValueError as e:
            logger.error(f"Error parsing price value '{price_text}': {str(e)}")
            raise ValueError(f"Invalid price format: {price_text}")

    def _get_hourly_average(self) -> Optional[float]:
        """Get current hour average price"""
        try:
            logger.debug("Fetching hourly average from API...")
            response = requests.get(f"{self.hourly_api_url}?type=currenthouraverage")
            response.raise_for_status()
            data = response.json()

            if data and len(data) > 0:
                try:
                    return float(data[0]['price'])
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(f"Error parsing API response: {e}")
                    return None

            logger.warning("No price data in API response")
            return None

        except Exception as e:
            logger.error(f"Error fetching hourly average: {str(e)}", exc_info=True)
            return None

    def _calculate_trend(self, current_price: float, hourly_average: Optional[float]) -> str:
        """Calculate price trend"""
        if hourly_average is None:
            return "unknown"

        if current_price > hourly_average * 1.05:
            return "rising"
        elif current_price < hourly_average * 0.95:
            return "falling"
        return "stable"

    def format_message(self, price_data: PriceData) -> str:
        """Format price data into a readable message"""
        # Determine price status
        if price_data.price <= 2.0:
            status = "🟢 LOW PRICE"
        elif price_data.price >= 4.0:
            status = "🔴 HIGH PRICE"
        else:
            status = "🟡 NORMAL PRICE"

        message = [
            f"📊 ComEd Price Update - {status}",
            "",
            f"Current Price: {price_data.price:.2f}¢"
        ]

        if price_data.hourly_average:
            message.append(f"Hourly Average: {price_data.hourly_average:.2f}¢")

        message.extend([
            f"Trend: {price_data.trend.capitalize()}",
            "",
            f"⏰ As of: {price_data.timestamp.strftime('%I:%M %p %Z')}"
        ])

        return "\n".join(message)