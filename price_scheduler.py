import logging
import asyncio
from datetime import datetime
from providers.comed_provider import ComedProvider
from models import PriceHistory
from app import app

logger = logging.getLogger(__name__)

class PriceDataScheduler:
    def __init__(self):
        self.provider = ComedProvider()
        self.interval = 3600  # 1 hour in seconds

    async def fetch_and_store_prices(self):
        """Fetch current prices and store in database"""
        try:
            with app.app_context():
                # Get current prices
                current_date = datetime.now()
                hourly_prices = self.provider.get_hourly_prices(current_date)
                current_average = self.provider.get_current_average()

                if hourly_prices:
                    # Store the most recent price
                    latest_price = hourly_prices[0]
                    PriceHistory.add_price_data(
                        provider=self.provider.get_provider_name(),
                        hourly_price=latest_price['price'],
                        hourly_average=current_average,
                        timestamp=datetime.fromisoformat(latest_price['timestamp'])
                    )
                    logger.info(
                        f"Stored price data: {latest_price['price']}¢ "
                        f"(avg: {current_average}¢) "
                        f"for {self.provider.get_provider_name()}"
                    )
                else:
                    logger.warning("No price data available")

        except Exception as e:
            logger.error(f"Error in fetch_and_store_prices: {str(e)}", exc_info=True)

    async def run(self):
        """Run the scheduler"""
        logger.info(f"Starting price data scheduler for {self.provider.get_provider_name()}")
        while True:
            try:
                await self.fetch_and_store_prices()
                await asyncio.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error in scheduler run loop: {str(e)}", exc_info=True)
                await asyncio.sleep(60)  # Wait a minute before retrying on error

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    scheduler = PriceDataScheduler()
    await scheduler.run()

if __name__ == "__main__":
    asyncio.run(main())