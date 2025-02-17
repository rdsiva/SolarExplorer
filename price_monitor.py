import requests
import json
from datetime import datetime
import logging
from config import FIVE_MIN_PRICE_URL, HOURLY_PRICE_URL, MIN_RATE

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
            today_date = datetime.now().strftime("%Y%m%d")
            response = requests.get(f"{HOURLY_PRICE_URL}?queryDate={today_date}")
            response.raise_for_status()
            data = response.json()

            if not data:
                raise ValueError("Empty response from hourly price API")

            current_time = datetime.now().strftime("%I:00 %p")
            current_data = [
                entry for entry in data 
                if entry["DateTime"].split(":")[0].zfill(2) + ":" + entry["DateTime"].split(":")[1] == current_time
            ]

            if not current_data:
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
