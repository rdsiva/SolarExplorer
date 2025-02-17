TELEGRAM_BOT_TOKEN=your_bot_token    # From Telegram BotFather
DATABASE_URL=postgresql://...        # PostgreSQL connection string
SESSION_SECRET=your_secret_key       # Flask session secret
```

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
```

## Scalability and Cloud Deployment

### Module Independence
Each module in the system is designed to run independently, allowing for flexible scaling:

1. **Price Monitor Module**
   - Can run as a standalone service
   - Scales based on monitoring load
   - Configuration via environment variables:
   ```bash
   PRICE_MONITOR_SCALING=auto
   PRICE_MONITOR_MIN_INSTANCES=1
   PRICE_MONITOR_MAX_INSTANCES=5
   ```

2. **Pattern Analysis Module**
   - Independent data processing
   - Scales based on analysis complexity
   - Configurable through:
   ```bash
   PATTERN_ANALYSIS_WORKERS=3
   PATTERN_ANALYSIS_BATCH_SIZE=100
   ```

3. **ML Prediction Module**
   - Separate ML processing service
   - GPU support for training
   - Scaling configuration:
   ```bash
   ML_PREDICTION_WORKERS=2
   ML_PREDICTION_BATCH_SIZE=50
   ```

### Cloud Deployment with Kubernetes

The application is designed to be cloud-agnostic and can be deployed on any Kubernetes cluster:

#### Component Separation
```yaml
# Example Kubernetes structure
services/
├── telegram-bot/         # Telegram bot service
│   ├── Dockerfile
│   └── k8s/
│       ├── deployment.yaml
│       └── service.yaml
├── price-monitor/       # Price monitoring service
│   ├── Dockerfile
│   └── k8s/
│       ├── deployment.yaml
│       └── service.yaml
├── flask-server/        # Web interface
│   ├── Dockerfile
│   └── k8s/
│       ├── deployment.yaml
│       └── service.yaml
└── shared/             # Shared configurations
    ├── configmap.yaml
    └── secrets.yaml
```

#### Scaling Strategies
1. **Horizontal Pod Autoscaling (HPA)**
   - Automatic scaling based on CPU/memory usage
   - Custom metrics for specific modules
   ```yaml
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   metadata:
     name: price-monitor-hpa
   spec:
     scaleTargetRef:
       apiVersion: apps/v1
       kind: Deployment
       name: price-monitor
     minReplicas: 1
     maxReplicas: 5
     metrics:
     - type: Resource
       resource:
         name: cpu
         target:
           type: Utilization
           averageUtilization: 80
   ```

2. **Vertical Pod Autoscaling (VPA)**
   - Automatic resource adjustment
   - Optimal resource utilization
   ```yaml
   apiVersion: autoscaling.k8s.io/v1
   kind: VerticalPodAutoscaler
   metadata:
     name: ml-prediction-vpa
   spec:
     targetRef:
       apiVersion: apps/v1
       kind: Deployment
       name: ml-prediction
     updatePolicy:
       updateMode: Auto
   ```

### Inter-Module Communication
- Uses message queues for asynchronous communication
- Supports both RabbitMQ and Redis pub/sub
- Configuration example:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: queue-config
data:
  QUEUE_TYPE: "rabbitmq"
  QUEUE_HOST: "rabbitmq-service"
  QUEUE_PORT: "5672"
```

### State Management
- PostgreSQL deployed as StatefulSet
- Persistent volume claims for data storage
- Example configuration:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgresql
spec:
  serviceName: postgresql
  replicas: 1
  selector:
    matchLabels:
      app: postgresql
  template:
    metadata:
      labels:
        app: postgresql
    spec:
      containers:
      - name: postgresql
        image: postgres:13
        env:
        - name: POSTGRES_DB
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: DB_NAME
        volumeMounts:
        - name: postgresql-data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgresql-data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 10Gi