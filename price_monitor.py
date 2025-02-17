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
    def format_time(time_str, format_in='%I:%M %p', format_out='%Y-%m-%d %I:%M %p %Z'):
        """Format time string with timezone and date"""
        try:
            cst_tz = ZoneInfo("America/Chicago")
            current_time = datetime.now(cst_tz)

            if not time_str:
                return current_time.strftime(format_out)

            # Parse the input time string
            if isinstance(time_str, datetime):
                time_obj = time_str
            else:
                try:
                    time_obj = datetime.strptime(time_str, format_in)
                except ValueError:
                    # Try alternate format if first fails
                    try:
                        time_obj = datetime.strptime(time_str, '%Y-%m-%d %I:%M %p')
                    except ValueError:
                        logger.error(f"Could not parse time string: {time_str}")
                        return current_time.strftime(format_out)

            # Combine current date with parsed time
            time_with_tz = current_time.replace(
                hour=time_obj.hour,
                minute=time_obj.minute,
                second=0,
                microsecond=0
            )

            return time_with_tz.strftime(format_out)
        except Exception as e:
            logger.error(f"Error formatting time '{time_str}': {str(e)}")
            return datetime.now(ZoneInfo("America/Chicago")).strftime(format_out)

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
            formatted_time = PriceMonitor.format_time(price_data.get('LocalTimeinCST'))

            # Calculate trend using valid prices only
            recent_prices = [
                PriceMonitor.clean_price_string(p.get('price')) 
                for p in data[:5]
            ]
            trend = PriceMonitor.determine_price_trend(cleaned_price, recent_prices)

            return {
                'price': cleaned_price if cleaned_price is not None else "N/A",
                'time': formatted_time,
                'raw_time': price_data.get('LocalTimeinCST'),
                'trend': trend,
                'message': PriceMonitor.format_price_message(
                    cleaned_price if cleaned_price is not None else "N/A",
                    formatted_time,
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
            formatted_time = PriceMonitor.format_time(hour_data.get('DateTime'))

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
                'time': formatted_time,
                'raw_time': hour_data.get('DateTime'),
                'trend': trend,
                'price_range': price_range,
                'message': PriceMonitor.format_price_message(
                    cleaned_price if cleaned_price is not None else "N/A",
                    formatted_time,
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