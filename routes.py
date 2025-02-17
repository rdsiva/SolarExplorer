from flask import jsonify
from datetime import datetime
from app import app
from providers.comed_provider import ComedProvider

price_provider = ComedProvider()

@app.route('/api/price_data', methods=['GET'])
def get_price_data():
    """
    Get current price data from the provider
    Returns JSON with current hourly price, day-ahead price, and hourly average
    """
    try:
        current_date = datetime.now()
        hourly_prices = price_provider.get_hourly_prices(current_date)
        current_average = price_provider.get_current_average()
        
        if not hourly_prices:
            return jsonify({
                'error': 'No price data available',
                'timestamp': current_date.isoformat()
            }), 404
            
        latest_price = hourly_prices[0]
        
        return jsonify({
            'provider': price_provider.get_provider_name(),
            'timestamp': latest_price['timestamp'],
            'hourly_price': latest_price['price'],
            'hourly_average': current_average,
            'price_unit': price_provider.get_price_unit(),
            'status': 'success'
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': current_date.isoformat(),
            'status': 'error'
        }), 500
