import asyncio
import logging
import sys
from agents import CoordinatorAgent
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

async def monitor_prices_continuously():
    try:
        # Initialize the coordinator agent
        coordinator = CoordinatorAgent()

        # Start all agents
        await coordinator.start_all()
        logger.info("All agents started successfully")

        # Initial test message to verify format
        logger.info("Sending initial test message...")
        result = await coordinator.process({"command": "monitor_prices"})
        if result["status"] == "success":
            logger.info("Initial test message sent successfully")

        # Continue with regular monitoring
        while True:
            try:
                result = await coordinator.process({"command": "monitor_prices"})
                if result["status"] == "success":
                    logger.info("Price monitoring cycle completed successfully")
                    if "data" in result:
                        price_data = result["data"].get("price_data", {})
                        analysis = result["data"].get("analysis", {})
                        prediction = result["data"].get("prediction", {})

                        # Detailed logging
                        logger.debug(f"Price Data: {price_data}")
                        logger.debug(f"Analysis: {analysis}")
                        logger.debug(f"Prediction: {prediction}")

                        # Log specific components
                        hourly_data = price_data.get("hourly_data", {})
                        logger.info(f"Current Time: {hourly_data.get('time', 'N/A')}")
                        logger.info(f"Price: {hourly_data.get('price', 'N/A')}¢")
                        logger.info(f"Trend: {hourly_data.get('trend', 'unknown')}")
                        if "price_range" in hourly_data:
                            logger.info(f"Price Range: {hourly_data['price_range']['min']}¢ - {hourly_data['price_range']['max']}¢")
                else:
                    logger.error(f"Price monitoring failed: {result['message']}")

                # Wait for 5 minutes before the next check
                await asyncio.sleep(300)

            except Exception as e:
                logger.error(f"Error in monitoring cycle: {str(e)}")
                await asyncio.sleep(60)

    except Exception as e:
        logger.error(f"Monitor process failed: {str(e)}")
    finally:
        if 'coordinator' in locals():
            await coordinator.stop_all()
            logger.info("All agents stopped")

if __name__ == "__main__":
    asyncio.run(monitor_prices_continuously())