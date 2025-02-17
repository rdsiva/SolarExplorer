import logging
from datetime import datetime
import requests
import trafilatura
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from .base_provider import EnergyProvider

logger = logging.getLogger(__name__)

class ComedProvider(EnergyProvider):
    """ComEd energy provider implementation"""
    
    def __init__(self):
        self.pricing_table_url = "https://hourlypricing.comed.com/pricing-table/"
        self.hourly_api_url = "https://hourlypricing.comed.com/api"
        self.provider_name = "ComEd"
        self.price_unit = "¢/kWh"
    
    def get_provider_name(self) -> str:
        return self.provider_name
    
    def get_price_unit(self) -> str:
        return self.price_unit
    
    def get_hourly_prices(self, date: datetime) -> List[Dict[str, Any]]:
        """
        Get hourly prices by scraping the pricing table
        Returns a list of hourly prices with timestamps
        """
        try:
            # Download and parse the pricing table page
            response = trafilatura.fetch_url(self.pricing_table_url)
            if not response:
                raise ValueError("Failed to fetch pricing table")
            
            # Extract the table content using BeautifulSoup for better table parsing
            soup = BeautifulSoup(response, 'html.parser')
            price_table = soup.find('table', {'class': 'pricing-table'})
            
            if not price_table:
                raise ValueError("Price table not found on page")
            
            prices = []
            rows = price_table.find_all('tr')[1:]  # Skip header row
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 2:  # Ensure we have both time and price columns
                    time_str = cols[0].text.strip()
                    price_str = cols[1].text.strip().replace('¢', '')
                    
                    try:
                        price = float(price_str)
                        # Parse the time and combine with the provided date
                        time = datetime.strptime(time_str, "%I:%M %p")
                        timestamp = datetime.combine(date.date(), time.time())
                        
                        prices.append({
                            'timestamp': timestamp.isoformat(),
                            'price': price,
                            'type': 'actual'
                        })
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse price data: {e}")
                        continue
            
            return prices
            
        except Exception as e:
            logger.error(f"Error fetching hourly prices: {str(e)}")
            return []
    
    def get_current_average(self) -> float:
        """
        Get the current hour average price from the API
        Returns the average price as a float
        """
        try:
            response = requests.get(f"{self.hourly_api_url}?type=currenthouraverage")
            response.raise_for_status()
            
            # API returns a list with a single value
            data = response.json()
            if data and len(data) > 0:
                try:
                    return float(data[0]['price'])
                except (KeyError, ValueError, TypeError):
                    logger.error("Invalid price format in API response")
            
            raise ValueError("No price data in API response")
            
        except Exception as e:
            logger.error(f"Error fetching current average: {str(e)}")
            return 0.0
