from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import logging

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the Base class
db = SQLAlchemy(model_class=Base)

def init_db(app):
    """Initialize the database with the Flask app"""
    try:
        logger.info("Initializing database connection...")
        db.init_app(app)

        with app.app_context():
            logger.info("Creating database tables...")
            import models  # Import here to avoid circular imports
            db.create_all()
            logger.info("Database tables created successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise