import logging
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
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
    price_range: Optional[Dict[str, float]] = None

    def __str__(self):
        return f"PriceData(price={self.price}¢, day_ahead={self.day_ahead_price}¢, trend={self.trend})"

class ComedPriceMonitor:
    """Simple price monitoring for ComEd"""

    def __init__(self):
        self.base_url = "https://hourlypricing.comed.com/api"
        self.five_min_feed = f"{self.base_url}?type=5minutefeed"
        self.hourly_average = f"{self.base_url}?type=currenthouraverage"
        # Primary API endpoint
        self.api_url = "https://srddev.pythonanywhere.com/api/hourlyprice"

    def get_current_prices(self) -> PriceData:
        """Get current price data from API with fallback to web scraping"""
        try:
            logger.debug("Fetching current price data...")

            # Try primary API first
            today_date = datetime.now().strftime("%Y%m%d")
            api_url = f"{self.api_url}?queryDate={today_date}"
            logger.debug(f"Requesting data from primary API: {api_url}")

            response = requests.get(api_url)
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Primary API response: {json.dumps(data, indent=2)}")

            if data and data.get('status') == 'success' and 'data' in data:
                price_data = data['data'].get('price_data', {})
                hourly_data = price_data.get('hourly_data', {})

                if not hourly_data:
                    raise ValueError("No hourly data found in API response")

                price = float(hourly_data.get('price', 0))
                day_ahead = float(hourly_data.get('day_ahead_price', 0))
                trend = hourly_data.get('trend', 'unknown')
                price_range = hourly_data.get('price_range', {})

                logger.info(f"Got price from primary API: {price}¢")
                return PriceData(
                    price=price,
                    timestamp=datetime.now(ZoneInfo("America/Chicago")),
                    day_ahead_price=day_ahead,
                    trend=trend,
                    price_range=price_range
                )

        except Exception as e:
            logger.error(f"Primary API failed, falling back to web scraping: {str(e)}")
            try:
                # Fallback to web scraping
                price = self._get_current_price_fallback()
                hourly_average = self._get_hourly_average()
                trend = self._calculate_trend(price, hourly_average)

                logger.info(f"Got price from fallback: {price}¢")
                return PriceData(
                    price=price,
                    timestamp=datetime.now(ZoneInfo("America/Chicago")),
                    hourly_average=hourly_average,
                    trend=trend
                )
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {str(fallback_error)}", exc_info=True)
                raise RuntimeError(f"Both primary and fallback methods failed: {str(fallback_error)}")

    def _get_current_price_fallback(self) -> float:
        """Fallback method to get current price using web scraping"""
        logger.debug("Using fallback method to get current price...")
        try:
            response = requests.get(self.five_min_feed)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Fallback API response: {json.dumps(data[:1], indent=2)}")  # Log first entry only

            if not data:
                raise ValueError("No price data in API response")

            price = float(data[0]['price'])
            logger.info(f"Successfully got fallback price: {price}¢")
            return price

        except Exception as e:
            logger.error(f"Error in fallback price fetch: {str(e)}", exc_info=True)
            raise

    def _get_hourly_average(self) -> Optional[float]:
        """Get current hour average price"""
        try:
            response = requests.get(self.hourly_average)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Hourly average API response: {json.dumps(data, indent=2)}")

            if data and len(data) > 0:
                avg = float(data[0]['price'])
                logger.info(f"Got hourly average: {avg}¢")
                return avg

            logger.warning("No hourly average data found")
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

        if price_data.day_ahead_price:
            price_diff = price_data.day_ahead_price - price_data.price
            trend_indicator = "📈" if price_diff > 0 else "📉"
            message.append(f"Day-Ahead Price: {price_data.day_ahead_price:.2f}¢ {trend_indicator}")

        if price_data.hourly_average:
            message.append(f"Hourly Average: {price_data.hourly_average:.2f}¢")

        if price_data.price_range:
            message.append(
                f"Price Range: {price_data.price_range['min']:.2f}¢ - "
                f"{price_data.price_range['max']:.2f}¢"
            )

        message.extend([
            f"Trend: {price_data.trend.capitalize()}",
            "",
            f"⏰ As of: {price_data.timestamp.strftime('%I:%M %p %Z')}"
        ])

        return "\n".join(message)