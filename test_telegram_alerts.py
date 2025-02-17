import asyncio
import logging
import sys
from agents import CoordinatorAgent
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

async def test_notification_format():
    """Test notification formatting with sample data"""
    coordinator = None
    try:
        coordinator = CoordinatorAgent()
        await coordinator.start_all()

        # Sample test data
        test_data = {
            "command": "monitor_prices",
            "price_data": {
                "five_min_data": {
                    "price": 2.5,
                    "time": "10:30 PM",
                    "trend": "rising"
                },
                "hourly_data": {
                    "price": 2.2,
                    "day_ahead_price": 3.5,
                    "time": "10:00 PM",
                    "trend": "falling",
                    "price_range": {
                        "min": 1.98,
                        "max": 3.85
                    }
                }
            },
            "analysis": {
                "current_price": 2.2,
                "average_price": 2.8,
                "min_price": 1.98,
                "max_price": 3.85,
                "price_trend": "falling",
                "price_volatility": 0.5,
                "data_points": 24
            },
            "prediction": {
                "short_term_prediction": 2.0,
                "confidence": 85,
                "trend": "falling",
                "feedback_quality": 90,
                "next_hour_range": {
                    "low": 1.8,
                    "high": 2.4
                }
            }
        }

        logger.info("Testing notification format with sample data...")
        result = await coordinator.process(test_data)

        if result["status"] == "success":
            logger.info("Test notification sent successfully")
            logger.debug(f"Full response: {result}")
        else:
            logger.error(f"Test failed: {result['message']}")

    except Exception as e:
        logger.error(f"Error in notification format test: {str(e)}")
        raise
    finally:
        if coordinator:
            await coordinator.stop_all()

async def monitor_prices_continuously():
    """Regular price monitoring after initial test"""
    coordinator = None
    try:
        coordinator = CoordinatorAgent()
        await coordinator.start_all()
        logger.info("All agents started successfully")

        # First run the format test
        await test_notification_format()
        logger.info("Format test completed")

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

                        logger.debug(f"Price Data: {price_data}")
                        logger.debug(f"Analysis: {analysis}")
                        logger.debug(f"Prediction: {prediction}")

                        hourly_data = price_data.get("hourly_data", {})
                        logger.info(f"Current Time: {hourly_data.get('time', 'N/A')}")
                        logger.info(f"Price: {hourly_data.get('price', 'N/A')}¢")
                        logger.info(f"Trend: {hourly_data.get('trend', 'unknown')}")
                        if "price_range" in hourly_data:
                            logger.info(f"Price Range: {hourly_data['price_range']['min']}¢ - {hourly_data['price_range']['max']}¢")
                else:
                    logger.error(f"Price monitoring failed: {result['message']}")

                await asyncio.sleep(300)  # Wait 5 minutes before next check

            except Exception as e:
                logger.error(f"Error in monitoring cycle: {str(e)}")
                await asyncio.sleep(60)  # Shorter wait on error

    except Exception as e:
        logger.error(f"Monitor process failed: {str(e)}")
    finally:
        if coordinator:
            await coordinator.stop_all()
            logger.info("All agents stopped")

async def send_test_notification():
    """Send a single test notification"""
    coordinator = None
    try:
        coordinator = CoordinatorAgent()
        await coordinator.start_all()

        # Sample test data with current time
        test_data = {
            "command": "monitor_prices",
            "price_data": {
                "five_min_data": {
                    "price": 2.5,
                    "time": datetime.now(ZoneInfo("America/Chicago")).strftime("%I:%M %p"),
                    "trend": "rising"
                },
                "hourly_data": {
                    "price": 2.2,
                    "day_ahead_price": 3.5,
                    "time": datetime.now(ZoneInfo("America/Chicago")).strftime("%I:00 %p"),
                    "trend": "falling",
                    "price_range": {
                        "min": 1.98,
                        "max": 3.85
                    }
                }
            },
            "analysis": {
                "current_price": 2.2,
                "average_price": 2.8,
                "min_price": 1.98,
                "max_price": 3.85,
                "price_trend": "falling",
                "price_volatility": 0.5,
                "data_points": 24
            },
            "prediction": {
                "short_term_prediction": 2.0,
                "confidence": 85,
                "trend": "falling",
                "feedback_quality": 90,
                "next_hour_range": {
                    "low": 1.8,
                    "high": 2.4
                }
            }
        }

        logger.info("Sending test notification...")
        result = await coordinator.process(test_data)

        if result["status"] == "success":
            logger.info("Test notification sent successfully")
            logger.debug(f"Full response: {result}")
        else:
            logger.error(f"Test failed: {result['message']}")

    except Exception as e:
        logger.error(f"Error in sending test notification: {str(e)}")
        raise
    finally:
        if coordinator:
            await coordinator.stop_all()

if __name__ == "__main__":
    asyncio.run(send_test_notification())
    asyncio.run(monitor_prices_continuously())