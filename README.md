# Energy Price Monitor Bot
A Telegram bot for monitoring real-time energy prices with ML-powered predictions and alerts.

## Table of Contents
- [Dependencies](#dependencies)
- [Database Setup](#database-setup)
  - [Schema](#schema)
- [Getting Started](#getting-started)
- [Running the Application](#running-the-application)
  - [Main Components](#main-components)
- [Module System](#module-system)
  - [Active Modules](#active-modules)
  - [Creating New Modules](#creating-new-modules)
- [Notification System](#notification-system)
  - [Price Alerts](#price-alerts)
  - [Alert Configuration](#alert-configuration)
- [Local Development Setup](#local-development-setup)
- [Project Structure](#project-structure)

### Dependencies
```bash
# Core dependencies
flask-sqlalchemy==3.1.1      # Database ORM
python-telegram-bot==20.7    # Telegram Bot API
sqlalchemy==2.0.23          # SQL Toolkit
nest-asyncio==1.5.8         # Async support
flask-wtf==1.2.1         # Form handling
scipy==1.11.4            # Scientific computing
requests==2.31.0            # HTTP client
pandas==2.1.4               # Data analysis
scikit-learn==1.3.2      # Machine learning
python-dotenv==1.0.0        # Environment variables
psycopg2-binary==2.9.9      # PostgreSQL adapter
beautifulsoup4==4.12.2   # HTML parsing
trafilatura==1.6.1       # Web scraping

```

## Database Setup

### Schema
```sql
-- Price History Table
CREATE TABLE price_history (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    hourly_price FLOAT NOT NULL,
    predicted_price FLOAT,
    prediction_accuracy FLOAT,
    prediction_confidence INTEGER
);

-- User Settings Table
CREATE TABLE user_settings (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(128) UNIQUE NOT NULL,
    alert_threshold FLOAT DEFAULT 3.0,
    notifications_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Getting Started

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables (create .env file):
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
DATABASE_URL=postgresql://username:password@localhost:5432/dbname
SESSION_SECRET=your_secret_key
```

4. Initialize the database:
```python
python
>>> from app import db
>>> db.create_all()
```

## Running the Application

### Main Components
The application consists of three main components that need to run simultaneously:

1. Telegram Bot (Primary Interface):
```bash
python minimal_bot.py
```

2. Price Monitor (Background Service):
```bash
python price_scheduler.py
```

3. Flask Server (Optional - For Web Dashboard):
```bash
python main.py
```

## Module System

### Active Modules
The system uses a modular architecture with the following components:

#### Required Modules (Always Enabled)
1. **Price Monitor Module** (`modules/price_monitor_module.py`)
   - Monitors real-time energy prices
   - Provides price alerts and analysis

2. **Dashboard Module** (`modules/dashboard_module.py`)
   - Web interface for data visualization
   - User settings management

#### Optional Modules
1. **Pattern Analysis Module** (`modules/pattern_analysis_module.py`)
   - Analyzes price patterns
   - Provides trend insights

2. **ML Prediction Module** (`modules/ml_prediction_module.py`)
   - Price predictions using machine learning
   - Accuracy tracking and feedback

### Creating New Modules

To create a new module:

1. Create a new file in the `modules` directory
2. Inherit from `BaseModule`
3. Implement required methods
4. Register with `ModuleManager`

Example:
```python
from modules.base_module import BaseModule
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class CustomModule(BaseModule):
    def __init__(self):
        super().__init__(
            name="custom_module",
            description="Custom module description"
        )
        self.initialized = False

    async def initialize(self) -> bool:
        """Initialize module"""
        try:
            # Your initialization logic here
            self.initialized = True
            return True
        except Exception as e:
            logger.error(f"Initialization failed: {str(e)}")
            return False

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data"""
        if not self.initialized:
            raise ModuleError("Module not initialized")

        try:
            # Your processing logic here
            result = {
                "status": "success",
                "data": data  # Replace with actual processing
            }
            return result
        except Exception as e:
            logger.error(f"Processing error: {str(e)}")
            raise ModuleError(str(e))
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

### Alert Configuration
Users can configure their notification preferences through the settings:
```python
async def update_user_settings(telegram_user_id, new_threshold):
    with app.app_context():
        user_settings = UserSettings.query.filter_by(user_id=telegram_user_id).first()
        if not user_settings:
            user_settings = UserSettings(
                user_id=telegram_user_id,
                alert_threshold=new_threshold
            )
            db.session.add(user_settings)
        else:
            user_settings.alert_threshold = new_threshold
        db.session.commit()
```

## Local Development Setup

1. Create a Python virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up PostgreSQL database:
```bash
createdb energy_price_monitor
export DATABASE_URL="postgresql://localhost/energy_price_monitor"
```

4. Initialize the database:
```python
python
>>> from app import db
>>> db.create_all()
```

## Project Structure
```
project_root/
├── minimal_bot.py           # Primary Telegram bot implementation
├── price_scheduler.py       # Price monitoring service
├── main.py                 # Flask application entry point
├── app.py                  # Flask app and database initialization
├── models.py              # Database models
│
├── modules/               # Module implementations
│   ├── __init__.py
│   ├── base_module.py           # Base module class
│   ├── price_monitor_module.py  # Price monitoring
│   ├── pattern_analysis.py      # Price pattern analysis
│   ├── ml_prediction.py         # ML predictions
│   └── module_manager.py        # Module management
│
└── templates/            # Flask templates
    ├── base.html
    └── dashboard.html