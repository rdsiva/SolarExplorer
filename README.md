# Core dependencies
flask-sqlalchemy==3.1.1
python-telegram-bot==20.7
sqlalchemy==2.0.23
nest-asyncio==1.5.8
flask-wtf==1.2.1
scipy==1.11.4
requests==2.31.0
pandas==2.1.4
scikit-learn==1.3.2
python-dotenv==1.0.0
psycopg2-binary==2.9.9

# Additional utilities
beautifulsoup4==4.12.2
trafilatura==1.6.1
```

## Database Setup

### Configuration
The application uses PostgreSQL. Set up your database connection using the following environment variables:

```bash
DATABASE_URL=postgresql://username:password@localhost:5432/dbname
```

### Database Schema
The application uses SQLAlchemy for database management. Key models include:

```python
# Price History Table
class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    hourly_price = db.Column(db.Float, nullable=False)
    predicted_price = db.Column(db.Float)
    prediction_accuracy = db.Column(db.Float)
    prediction_confidence = db.Column(db.Integer)

# User Settings Table
class UserSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), unique=True, nullable=False)
    alert_threshold = db.Column(db.Float, default=3.0)
    notifications_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### Database Migrations
The application uses Flask-SQLAlchemy for database management. To handle schema changes:

1. Initialize migrations (first time only):
```python
flask db init
```

2. Generate a new migration:
```python
flask db migrate -m "Description of changes"
```

3. Apply migrations:
```python
flask db upgrade
```

Note: Never manually write SQL migrations. Use Flask-SQLAlchemy's migration tools to handle schema changes safely.

## Running the Application

### Environment Setup
1. Create a `.env` file in the project root:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
DATABASE_URL=your_database_url
SESSION_SECRET=your_session_secret
```

### Starting the Application
The application has multiple components that can be run independently:

1. Main Flask Application:
```bash
python main.py
```

2. Telegram Bot (Minimal Version):
```bash
python minimal_bot.py
```

3. Price Data Scheduler:
```bash
python price_scheduler.py
```

### Running Multiple Components
You can run all components simultaneously using different terminal sessions:
```bash
# Terminal 1: Start Flask server
python main.py

# Terminal 2: Start Telegram bot
python minimal_bot.py

# Terminal 3: Start price scheduler
python price_scheduler.py
```

## Module System

### Existing Modules
Each module in the system is designed to handle specific functionality:

1. **Price Monitor Module** (Required)
   - Monitors real-time energy prices
   - Provides price alerts and analysis
   ```python
   from modules import ModuleManager, PriceMonitorModule

   module_manager = ModuleManager()
   price_module = PriceMonitorModule()
   module_manager.register_module(price_module)
   module_manager.enable_module("price_monitor")
   ```

2. **Pattern Analysis Module** (Optional)
   - Analyzes price patterns
   - Provides trend insights
   ```python
   from modules import PatternAnalysisModule

   pattern_module = PatternAnalysisModule()
   module_manager.register_module(pattern_module)
   module_manager.enable_module("pattern_analysis")
   ```

3. **ML Prediction Module** (Optional)
   - Provides price predictions
   - Uses machine learning models
   ```python
   from modules import MLPredictionModule

   ml_module = MLPredictionModule()
   module_manager.register_module(ml_module)
   module_manager.enable_module("ml_prediction")
   ```

### Creating New Modules
To create a new module:

1. Create a new file in the `modules` directory
2. Inherit from `BaseModule`
3. Implement required methods
4. Register with `ModuleManager`

Example of a custom module:
```python
from modules.base_module import BaseModule
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ModuleError(Exception):
    pass


class CustomModule(BaseModule):
    def __init__(self):
        super().__init__(
            name="custom_module",
            description="Custom module description"
        )
        self.initialized = False

    async def initialize(self) -> bool:
        try:
            # Your initialization logic here
            self.initialized = True
            return True
        except Exception as e:
            logger.error(f"Initialization failed: {str(e)}")
            return False

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.initialized:
            raise ModuleError("Module not initialized")

        try:
            # Your processing logic here
            processed_data = data # Replace with actual processing
            result = {
                "status": "success",
                "data": processed_data
            }
            return result
        except Exception as e:
            logger.error(f"Processing error: {str(e)}")
            raise ModuleError(str(e))

    async def get_notification_data(self) -> Optional[Dict[str, Any]]:
        """Implementation for notification data retrieval"""
        try:
            your_notification_data = {} # Replace with actual data
            return {
                "status": "active",
                "data": your_notification_data
            }
        except Exception as e:
            logger.error(f"Error getting notification data: {str(e)}")
            return None
```

## Notification System

### Price Alerts
The system sends notifications through Telegram when:
- Price exceeds threshold
- Significant price changes
- Pattern detection alerts

Example of sending notifications:
```python
async def send_price_alert(bot, chat_id, price_data):
    message = (
        "🔔 Price Alert!\n"
        f"Current Price: {price_data['current_price']}¢\n"
        f"Status: {price_data['status']}\n"
        f"Trend: {price_data['trend']}"
    )
    await bot.send_message(chat_id=chat_id, text=message)
```

### Notification Configuration
Users can configure their notification preferences through the UserSettings model:
```python
# Example of updating user settings
from app import app, db
from models import UserSettings

async def update_user_settings(telegram_user_id, new_threshold):
    with app.app_context():
        user_settings = UserSettings.query.filter_by(user_id=telegram_user_id).first()
        if not user_settings:
            user_settings = UserSettings(
                user_id=telegram_user_id,
                alert_threshold=new_threshold,
                notifications_enabled=True
            )
            db.session.add(user_settings)
        else:
            user_settings.alert_threshold = new_threshold
        db.session.commit()
```

## Local Development

### Setting Up Local Environment
1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up PostgreSQL database:
```bash
# Create database
createdb energy_price_monitor

# Configure environment variables
export DATABASE_URL="postgresql://localhost/energy_price_monitor"
export TELEGRAM_BOT_TOKEN="your_bot_token"
export SESSION_SECRET="your_secret_key"
```

4. Initialize the database:
```python
python
>>> from app import db
>>> db.create_all()
```

### Running Tests
```bash
# Run all tests
python -m unittest discover tests -v

# Run specific test files
python -m unittest tests/test_price_predictions.py -v
python -m unittest tests/test_tesla_charging.py -v
```

### Development Workflow
1. Start the Flask server:
```bash
python main.py
```

2. In a separate terminal, run the Telegram bot:
```bash
python minimal_bot.py
```

3. For testing price monitoring:
```bash
python test_agents.py
```

## Monitoring and Logging

The application uses Python's logging module with different levels:
```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
```

### Log Levels:
- DEBUG: Detailed information for debugging
- INFO: General operational information
- WARNING: Warning messages for potential issues
- ERROR: Error messages for actual problems

### Module-specific Logging
Each module has its own logger:
```python
# In your module file
logger = logging.getLogger(__name__)

class YourModule(BaseModule):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
```

## Testing

### Unit Tests
The project includes comprehensive unit tests for each module:
```bash
# Run specific module tests
python -m unittest tests/test_price_monitor.py
python -m unittest tests/test_pattern_analysis.py
```

### Integration Tests
Integration tests ensure different modules work together:
```bash
# Run integration tests
python -m unittest tests/test_integration.py
```

### Manual Testing
For manual testing of the Telegram bot:
1. Start the bot in development mode
2. Send test commands: /start, /check, /help
3. Verify responses and price data
4. Test notification triggers

## Troubleshooting

### Common Issues
1. Database Connection Errors
   - Verify DATABASE_URL environment variable
   - Check PostgreSQL service is running
   - Ensure database exists and is accessible

2. Telegram Bot Issues
   - Verify TELEGRAM_BOT_TOKEN is correct
   - Check internet connectivity
   - Review bot permissions

3. Module Initialization Failures
   - Check module dependencies
   - Verify required services are available
   - Review module logs for specific errors

### Debug Mode
Enable debug mode for detailed logs:
```python
# In config.py or .env
DEBUG=True