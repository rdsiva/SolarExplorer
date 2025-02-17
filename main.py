from app import app
from flask import redirect
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def root():
    """Root route handler"""
    try:
        logger.info("Redirecting to module management interface")
        return redirect('/module-management')
    except Exception as e:
        logger.error(f"Error in root route: {str(e)}", exc_info=True)
        return "Error: Could not load module management interface", 500

if __name__ == "__main__":
    # Ensure the server is accessible externally
    logger.info("Starting Flask server on port 5000...")
    app.run(host="0.0.0.0", port=5000, debug=True)