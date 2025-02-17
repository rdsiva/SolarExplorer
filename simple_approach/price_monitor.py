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

    def validate(self):
        """Validate price data"""
        if self.price <= 0:
            raise ValueError("Price must be positive")
        if self.day_ahead_price is not None and self.day_ahead_price < 0:
            raise ValueError("Day ahead price must be non-negative")
        if self.price_range:
            if self.price_range['min'] > self.price_range['max']:
                raise ValueError("Invalid price range: min > max")

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
            today_date = datetime.now().strftime("%Y%m%d")
            api_url = f"{self.api_url}?queryDate={today_date}"
            logger.debug(f"Requesting data from primary API: {api_url}")

            response = requests.get(api_url, timeout=10)
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Primary API response: {json.dumps(data[:2], indent=2)}")  # Log first 2 entries

            if not data or not isinstance(data, list):
                raise ValueError("Invalid API response format - expected array")

            # Get the most recent hour's data
            current_hour = datetime.now(ZoneInfo("America/Chicago")).strftime("%I:00 %p")
            current_price_data = None

            for entry in data:
                if entry['DateTime'] == current_hour:
                    current_price_data = entry
                    break

            if not current_price_data:
                current_price_data = data[0]  # Fallback to first entry if current hour not found

            # Parse prices (remove ¢ symbol and convert to float)
            day_ahead = float(current_price_data['DayAheadPrice'].replace('¢', ''))
            real_time = None
            if current_price_data['RealTimePrice'] != 'n/a':
                real_time = float(current_price_data['RealTimePrice'].replace('¢', ''))

            # Use real-time price if available, otherwise day-ahead
            current_price = real_time if real_time is not None else day_ahead

            # Calculate price range from all available prices
            all_prices = []
            for entry in data:
                if entry['RealTimePrice'] != 'n/a':
                    all_prices.append(float(entry['RealTimePrice'].replace('¢', '')))
                if entry['DayAheadPrice'] != 'n/a':
                    all_prices.append(float(entry['DayAheadPrice'].replace('¢', '')))

            price_range = {
                'min': min(all_prices),
                'max': max(all_prices)
            } if all_prices else None

            # Determine trend
            trend = 'unknown'
            if len(all_prices) > 1:
                if current_price > sum(all_prices) / len(all_prices):
                    trend = 'rising'
                else:
                    trend = 'falling'

            price_data = PriceData(
                price=current_price,
                timestamp=datetime.now(ZoneInfo("America/Chicago")),
                day_ahead_price=day_ahead,
                trend=trend,
                price_range=price_range
            )

            price_data.validate()
            logger.info(f"Successfully fetched price data: {price_data}")
            return price_data

        except requests.RequestException as e:
            logger.error(f"API request failed: {str(e)}", exc_info=True)
            return self._get_fallback_price_data()
        except (ValueError, KeyError, TypeError) as e:
            logger.error(f"Error parsing API response: {str(e)}", exc_info=True)
            return self._get_fallback_price_data()
        except Exception as e:
            logger.error(f"Unexpected error in primary API: {str(e)}", exc_info=True)
            return self._get_fallback_price_data()

    def _get_fallback_price_data(self) -> PriceData:
        """Get price data using fallback methods"""
        logger.info("Using fallback method to get price data...")
        try:
            current_price = self._get_current_price_fallback()
            hourly_average = self._get_hourly_average()
            trend = self._calculate_trend(current_price, hourly_average)

            price_data = PriceData(
                price=current_price,
                timestamp=datetime.now(ZoneInfo("America/Chicago")),
                hourly_average=hourly_average,
                trend=trend
            )
            price_data.validate()
            logger.info(f"Successfully got fallback price data: {price_data}")
            return price_data

        except Exception as e:
            logger.error(f"Fallback method failed: {str(e)}", exc_info=True)
            raise RuntimeError(f"Both primary and fallback methods failed: {str(e)}")

    def _get_current_price_fallback(self) -> float:
        """Get current price using ComEd API"""
        logger.debug("Fetching current price from ComEd API...")
        try:
            response = requests.get(self.five_min_feed, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data:
                raise ValueError("No price data in ComEd API response")

            price = float(data[0]['price'])
            if price <= 0:
                raise ValueError(f"Invalid price value: {price}")

            logger.info(f"Successfully got current price: {price}¢")
            return price

        except Exception as e:
            logger.error(f"Error in fallback price fetch: {str(e)}", exc_info=True)
            raise

    def _get_hourly_average(self) -> Optional[float]:
        """Get current hour average price"""
        try:
            response = requests.get(self.hourly_average, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data and len(data) > 0:
                avg = float(data[0]['price'])
                if avg > 0:
                    logger.info(f"Got hourly average: {avg}¢")
                    return avg

            logger.warning("No valid hourly average data found")
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
        # Determine price status and emoji based on current price
        if price_data.price <= 3.0:
            status = "🟢 LOW PRICE ALERT"
        elif price_data.price >= 6.0:
            status = "🔴 HIGH PRICE ALERT"
        else:
            status = "🟡 NORMAL PRICE LEVELS"

        message = [
            f"📊 ComEd Price Update - {status}",
            "",
            f"Current Price: {price_data.price:.2f}¢"
        ]

        if price_data.day_ahead_price:
            diff = price_data.price - price_data.day_ahead_price
            trend_indicator = "📈" if diff > 0 else "📉"
            message.append(
                f"Day-Ahead Price: {price_data.day_ahead_price:.2f}¢ "
                f"({abs(diff):+.2f}¢) {trend_indicator}"
            )

        if price_data.price_range:
            message.append(
                f"Today's Range: {price_data.price_range['min']:.2f}¢ - "
                f"{price_data.price_range['max']:.2f}¢"
            )

        message.extend([
            f"Price Trend: {price_data.trend.capitalize()}",
            "",
            "💡 Price Categories:",
            "• Low: ≤ 3.0¢",
            "• Normal: 3.1¢ - 5.9¢",
            "• High: ≥ 6.0¢",
            "",
            f"⏰ Last Updated: {price_data.timestamp.strftime('%I:%M %p %Z')}"
        ])

        return "\n".join(message)