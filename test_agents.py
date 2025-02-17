import asyncio
import logging
from agents import CoordinatorAgent
import sys
from app import app

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

async def test_price_monitoring():
    coordinator = None  # Initialize coordinator outside try block
    try:
        # Initialize the coordinator agent
        coordinator = CoordinatorAgent()

        # Start all agents
        await coordinator.start_all()
        logger.info("All agents started successfully")

        # Use Flask application context for database operations
        with app.app_context():
            # Start a monitoring cycle
            result = await coordinator.process({"command": "monitor_prices"})

            # Log the results
            if result["status"] == "success":
                logger.info("Price monitoring cycle completed successfully")
                logger.info(f"Price Data: {result['data']['price_data']}")
                logger.info(f"Analysis: {result['data']['analysis']}")
                if 'prediction' in result['data']:
                    logger.info(f"Predictions: {result['data']['prediction']}")
            else:
                logger.error(f"Price monitoring failed: {result['message']}")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
    finally:
        # Stop all agents if coordinator was initialized
        if coordinator:
            await coordinator.stop_all()
            logger.info("All agents stopped")

if __name__ == "__main__":
    asyncio.run(test_price_monitoring())