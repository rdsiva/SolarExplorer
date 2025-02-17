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

        while True:
            try:
                # Start a monitoring cycle
                result = await coordinator.process({"command": "monitor_prices"})
                
                # Log the results
                if result["status"] == "success":
                    logger.info("Price monitoring cycle completed successfully")
                    logger.debug(f"Price Data: {result['data']['price_data']}")
                    logger.debug(f"Analysis: {result['data']['analysis']}")
                else:
                    logger.error(f"Price monitoring failed: {result['message']}")

                # Wait for 5 minutes before the next check
                await asyncio.sleep(300)  # 300 seconds = 5 minutes

            except Exception as e:
                logger.error(f"Error in monitoring cycle: {str(e)}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying if there's an error

    except Exception as e:
        logger.error(f"Monitor process failed: {str(e)}")
    finally:
        # Stop all agents
        await coordinator.stop_all()
        logger.info("All agents stopped")

if __name__ == "__main__":
    asyncio.run(monitor_prices_continuously())
