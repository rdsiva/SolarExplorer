import os
import logging
from datetime import datetime, timedelta
import requests
from zoneinfo import ZoneInfo

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WeatherProvider:
    """Provider for weather data and forecasts"""
    
    def __init__(self):
        self.api_key = os.environ.get("OPENWEATHERMAP_API_KEY")
        if not self.api_key:
            raise ValueError("OPENWEATHERMAP_API_KEY environment variable is not set")
            
        self.base_url = "http://api.openweathermap.org/data/2.5"
        self.city = "Chicago"  # Default to Chicago for ComEd service area
        self.country = "US"
        
    async def get_current_weather(self):
        """Get current weather conditions"""
        try:
            url = f"{self.base_url}/weather"
            params = {
                'q': f"{self.city},{self.country}",
                'appid': self.api_key,
                'units': 'imperial'  # Use Fahrenheit for US
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return {
                'temperature': data['main']['temp'],
                'feels_like': data['main']['feels_like'],
                'humidity': data['main']['humidity'],
                'wind_speed': data['wind']['speed'],
                'weather_main': data['weather'][0]['main'],
                'weather_description': data['weather'][0]['description']
            }
            
        except Exception as e:
            logger.error(f"Error fetching current weather: {str(e)}")
            return None
            
    async def get_weather_forecast(self):
        """Get hourly weather forecast"""
        try:
            url = f"{self.base_url}/forecast"
            params = {
                'q': f"{self.city},{self.country}",
                'appid': self.api_key,
                'units': 'imperial'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            forecasts = []
            for item in data['list'][:8]:  # Next 24 hours (3-hour intervals)
                forecast_time = datetime.fromtimestamp(item['dt'], tz=ZoneInfo("America/Chicago"))
                forecasts.append({
                    'timestamp': forecast_time,
                    'temperature': item['main']['temp'],
                    'feels_like': item['main']['feels_like'],
                    'humidity': item['main']['humidity'],
                    'wind_speed': item['wind']['speed'],
                    'weather_main': item['weather'][0]['main'],
                    'weather_description': item['weather'][0]['description']
                })
                
            return forecasts
            
        except Exception as e:
            logger.error(f"Error fetching weather forecast: {str(e)}")
            return None
            
    def calculate_weather_impact(self, weather_data):
        """Calculate potential weather impact on energy prices"""
        if not weather_data:
            return 0.0
            
        impact = 0.0
        
        # Temperature impact (higher temps usually mean higher energy usage)
        temp = weather_data['temperature']
        if temp >= 85:  # Hot weather
            impact += 0.15  # 15% increase
        elif temp <= 32:  # Cold weather
            impact += 0.1  # 10% increase
        
        # Humidity impact
        humidity = weather_data['humidity']
        if humidity >= 80:  # High humidity
            impact += 0.05  # 5% increase
        
        # Weather condition impact
        weather_main = weather_data['weather_main'].lower()
        if weather_main in ['thunderstorm', 'rain', 'snow']:
            impact += 0.08  # 8% increase for severe weather
        
        return impact

# Create global instance
weather_provider = WeatherProvider()
