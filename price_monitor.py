import requests
import json
from datetime import datetime
import logging
from config import FIVE_MIN_PRICE_URL, HOURLY_PRICE_URL, MIN_RATE
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

class PriceMonitor:
    @staticmethod
    def format_price_message(price, time, price_type="current", additional_info=None):
        status = "below" if float(price) <= MIN_RATE else "above"
        message = (
            f"🔔 The Comed {price_type} price is {status} {MIN_RATE} cents!\n"
            f"💰 Price: {price} cents\n"
            f"🕒 Time: {time}"
        )
        if additional_info:
            message += f"\n📊 {additional_info}"
        return message

    @staticmethod
    async def check_five_min_price():
        try:
            response = requests.get(FIVE_MIN_PRICE_URL)
            response.raise_for_status()
            data = response.json()

            if not data:
                raise ValueError("Empty response from five minute price API")

            price_data = data[0]
            return {
                'price': price_data['price'],
                'time': price_data['LocalTimeinCST'],
                'message': PriceMonitor.format_price_message(
                    price_data['price'],
                    price_data['LocalTimeinCST'],
                    "5-minute"
                )
            }
        except Exception as e:
            logger.error(f"Error fetching 5-minute price: {str(e)}")
            raise

    @staticmethod
    async def check_hourly_price():
        try:
            cst_now = datetime.now(ZoneInfo("America/Chicago"))
            today_date = cst_now.strftime("%Y%m%d")
            logger.debug(f"Querying hourly price for CST date: {today_date}")

            api_url = f"{HOURLY_PRICE_URL}?queryDate={today_date}"
            logger.debug(f"Making API request to: {api_url}")

            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()

            if not data:
                raise ValueError("Empty response from hourly price API")

            current_time = cst_now.strftime("%I:00 %p")
            logger.debug(f"Looking for hourly price at CST time: {current_time}")
            logger.debug(f"API response contains {len(data)} records")

            current_data = [
                entry for entry in data 
                if entry["DateTime"].split(":")[0].zfill(2) + ":" + entry["DateTime"].split(":")[1] == current_time
            ]

            if not current_data:
                logger.warning(f"No data found for current hour: {current_time}")
                logger.debug("Available times in response: " + ", ".join(
                    sorted(set(entry["DateTime"] for entry in data))
                ))
                raise ValueError(f"No data found for current hour: {current_time}")

            hour_data = current_data[0]
            additional_info = f"Day Ahead Price: {hour_data['DayAheadPrice']} cents"

            return {
                'price': hour_data['RealTimePrice'],
                'time': hour_data['DateTime'],
                'message': PriceMonitor.format_price_message(
                    hour_data['RealTimePrice'],
                    hour_data['DateTime'],
                    "hourly",
                    additional_info
                )
            }
        except Exception as e:
            logger.error(f"Error fetching hourly price: {str(e)}")
            raise