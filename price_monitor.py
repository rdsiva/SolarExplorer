import requests
import json
from datetime import datetime
import logging
from config import FIVE_MIN_PRICE_URL, HOURLY_PRICE_URL, MIN_RATE
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

class PriceMonitor:
    @staticmethod
    def clean_price_string(price_str):
        """Clean price string by removing '¢' symbol and converting to float"""
        try:
            # Handle numeric types directly
            if isinstance(price_str, (int, float)):
                return float(price_str)

            # Handle None, empty string, or 'n/a'
            if not price_str or str(price_str).lower() in ['n/a', 'none', '']:
                return None  # Return None instead of 0.0 for invalid values

            # Remove '¢' symbol and any whitespace
            cleaned = str(price_str).replace('¢', '').strip()
            return float(cleaned)
        except (ValueError, AttributeError) as e:
            logger.error(f"Error cleaning price string '{price_str}': {str(e)}")
            return None

    @staticmethod
    def _parse_price_time(time_str):
        """Parse time string in various formats and return datetime object"""
        try:
            # Handle numeric types directly
            if isinstance(time_str, (int, float)):
                return float(time_str)

            # Handle None, empty string, or 'n/a'
            if not time_str or str(time_str).lower() in ['n/a', 'none', '']:
                return None

            formats = [
                "%m/%d/%Y %I:%M:%S %p",  # 02/17/2025 08:30:00 AM
                "%m/%d/%Y %I:%M %p",     # 02/17/2025 08:30 AM
                "%Y-%m-%d %I:%M %p",     # 2025-02-17 08:30 AM
                "%I:%M %p"               # 08:30 AM
            ]

            for fmt in formats:
                try:
                    time_obj = datetime.strptime(time_str.strip(), fmt)
                    if fmt == "%I:%M %p":
                        # For time-only format, use current date
                        current = datetime.now(ZoneInfo("America/Chicago"))
                        time_obj = time_obj.replace(
                            year=current.year,
                            month=current.month,
                            day=current.day,
                            tzinfo=current.tzinfo
                        )
                    else:
                        # Add timezone info
                        time_obj = time_obj.replace(tzinfo=ZoneInfo("America/Chicago"))
                    return time_obj
                except ValueError:
                    continue

            logger.error(f"Could not parse time string: {time_str}")
            return datetime.now(ZoneInfo("America/Chicago"))

        except Exception as e:
            logger.error(f"Error parsing time string '{time_str}': {str(e)}")
            return datetime.now(ZoneInfo("America/Chicago"))


    @staticmethod
    def determine_price_trend(current_price, previous_prices):
        """Determine price trend based on recent price history"""
        if not previous_prices or len(previous_prices) < 2 or None in previous_prices:
            return "unknown"

        recent_prices = [p for p in previous_prices[-3:] if p is not None]
        if len(recent_prices) < 2:
            return "unknown"

        if all(x > y for x, y in zip(recent_prices[:-1], recent_prices[1:])):
            return "falling"
        elif all(x < y for x, y in zip(recent_prices[:-1], recent_prices[1:])):
            return "rising"
        else:
            return "stable"

    @staticmethod
    async def check_five_min_price():
        """Fetch and process 5-minute price data"""
        try:
            response = requests.get(FIVE_MIN_PRICE_URL)
            response.raise_for_status()
            data = response.json()

            if not data:
                raise ValueError("Empty response from five minute price API")

            price_data = data[0]
            cleaned_price = PriceMonitor.clean_price_string(price_data.get('price', None))
            formatted_time = PriceMonitor._parse_price_time(price_data.get('LocalTimeinCST'))
            formatted_time_str = formatted_time.strftime('%Y-%m-%d %I:%M %p %Z') if formatted_time else None

            # Calculate trend using valid prices only
            recent_prices = [
                PriceMonitor.clean_price_string(p.get('price'))
                for p in data[:5]
            ]
            trend = PriceMonitor.determine_price_trend(cleaned_price, recent_prices)

            return {
                'price': cleaned_price if cleaned_price is not None else "N/A",
                'time': formatted_time_str,
                'raw_time': price_data.get('LocalTimeinCST'),
                'trend': trend,
                'message': PriceMonitor.format_price_message(
                    cleaned_price if cleaned_price is not None else "N/A",
                    formatted_time_str,
                    "5-minute"
                )
            }
        except Exception as e:
            logger.error(f"Error fetching 5-minute price: {str(e)}")
            current_time = datetime.now(ZoneInfo("America/Chicago"))
            return {
                'price': "N/A",
                'time': current_time.strftime('%Y-%m-%d %I:%M %p %Z'),
                'raw_time': current_time.strftime('%I:%M %p'),
                'trend': 'unknown',
                'message': "Error fetching 5-minute price data"
            }

    @staticmethod
    async def check_hourly_price():
        """Fetch and process hourly price data"""
        try:
            cst_now = datetime.now(ZoneInfo("America/Chicago"))
            today_date = cst_now.strftime("%Y%m%d")
            current_hour = cst_now.strftime("%I:00 %p")

            logger.info(f"Current time in CST: {cst_now.strftime('%Y-%m-%d %I:%M %p %Z')}")
            api_url = f"{HOURLY_PRICE_URL}?queryDate={today_date}"

            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()

            if not data:
                raise ValueError("Empty response from hourly price API")

            # Find the current hour's data
            current_data = [
                entry for entry in data
                if entry["DateTime"].split(":")[0].zfill(2) + ":00 " + entry["DateTime"].split()[-1] == current_hour
            ]

            if not current_data:
                logger.warning(f"No data found for current hour: {current_hour}")
                raise ValueError(f"No data found for current hour: {current_hour}")

            hour_data = current_data[0]
            cleaned_price = PriceMonitor.clean_price_string(hour_data.get('RealTimePrice'))
            cleaned_day_ahead = PriceMonitor.clean_price_string(hour_data.get('DayAheadPrice'))
            formatted_time = PriceMonitor._parse_price_time(hour_data.get('DateTime'))
            formatted_time_str = formatted_time.strftime('%Y-%m-%d %I:%M %p %Z') if formatted_time else None

            # Calculate price range using valid prices
            if cleaned_price is not None and cleaned_day_ahead is not None:
                price_range = {
                    'min': round(min(cleaned_price * 0.9, cleaned_day_ahead * 0.9), 2),
                    'max': round(max(cleaned_price * 1.1, cleaned_day_ahead * 1.1), 2)
                }
            else:
                price_range = {'min': "N/A", 'max': "N/A"}

            # Calculate trend using valid prices only
            recent_prices = [
                PriceMonitor.clean_price_string(entry.get('RealTimePrice'))
                for entry in data[-3:]
                if PriceMonitor.clean_price_string(entry.get('RealTimePrice')) is not None
            ]
            trend = PriceMonitor.determine_price_trend(cleaned_price, recent_prices)

            return {
                'price': cleaned_price if cleaned_price is not None else "N/A",
                'day_ahead_price': cleaned_day_ahead if cleaned_day_ahead is not None else "N/A",
                'time': formatted_time_str,
                'raw_time': hour_data.get('DateTime'),
                'trend': trend,
                'price_range': price_range,
                'message': PriceMonitor.format_price_message(
                    cleaned_price if cleaned_price is not None else "N/A",
                    formatted_time_str,
                    "hourly",
                    f"Day Ahead Price: {cleaned_day_ahead if cleaned_day_ahead is not None else 'N/A'}¢"
                )
            }
        except Exception as e:
            logger.error(f"Error fetching hourly price: {str(e)}")
            current_time = datetime.now(ZoneInfo("America/Chicago"))
            return {
                'price': "N/A",
                'day_ahead_price': "N/A",
                'time': current_time.strftime('%Y-%m-%d %I:%M %p %Z'),
                'raw_time': current_time.strftime('%I:%M %p'),
                'trend': 'unknown',
                'price_range': {'min': "N/A", 'max': "N/A"},
                'message': "Error fetching hourly price data"
            }

    @staticmethod
    def format_price_message(price, time, price_type="current", additional_info=None):
        """Format price message with improved status message"""
        if price == "N/A":
            return f"⚠️ The Comed {price_type} price is currently unavailable.\n🕒 Time: {time}"

        price_float = float(price) if isinstance(price, (int, float)) else None
        if price_float is None:
            return f"⚠️ Invalid price format for {price_type} price.\n🕒 Time: {time}"

        status = "below" if price_float <= MIN_RATE else "above"
        message = (
            f"🔔 The Comed {price_type} price is {status} {MIN_RATE} cents!\n"
            f"💰 Price: {price_float:.2f}¢\n"
            f"🕒 Time: {time}"
        )
        if additional_info:
            message += f"\n📊 {additional_info}"
        return message