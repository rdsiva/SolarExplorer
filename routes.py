from flask import jsonify, render_template
from datetime import datetime, timedelta
import numpy as np
from app import app
from providers.comed_provider import ComedProvider
from models import UserPreferences, UserAnalytics, SavingsInsight, PriceHistory

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
            'timestamp': datetime.now().isoformat(),
            'status': 'error'
        }), 500

@app.route('/dashboard/<chat_id>')
def analytics_dashboard(chat_id):
    """Display the personalized analytics dashboard for a user"""
    try:
        # Get or create user preferences
        with app.app_context():
            user_prefs = UserPreferences.get_user_preferences(chat_id)
            if not user_prefs:
                user_prefs = UserPreferences.create_or_update(
                    chat_id=chat_id,
                    price_threshold=3.0,  # Default threshold
                    alert_frequency='immediate'
                )

        # Get latest analytics
        analytics = UserAnalytics.query.filter_by(chat_id=chat_id)\
            .order_by(UserAnalytics.timestamp.desc())\
            .first()

        # Get recent savings insights
        insights = SavingsInsight.get_user_insights(chat_id, days=30)

        # Get recent price history for the last week
        price_history = PriceHistory.get_recent_history(
            provider="ComEd",
            hours=24 * 7  # Last week of data
        )

        # Calculate additional analytics
        daily_stats = {}
        hourly_stats = {}
        if price_history:
            # Daily price patterns
            for record in price_history:
                day = record.timestamp.strftime('%A')  # Get day name
                if day not in daily_stats:
                    daily_stats[day] = []
                daily_stats[day].append(record.hourly_price)

            # Process daily stats
            for day in daily_stats:
                prices = daily_stats[day]
                daily_stats[day] = {
                    'average': round(np.mean(prices), 2),
                    'min': round(min(prices), 2),
                    'max': round(max(prices), 2)
                }

            # Hourly price patterns
            for record in price_history:
                hour = record.timestamp.hour
                if hour not in hourly_stats:
                    hourly_stats[hour] = []
                hourly_stats[hour].append(record.hourly_price)

            # Process hourly stats
            for hour in hourly_stats:
                prices = hourly_stats[hour]
                hourly_stats[hour] = {
                    'average': round(np.mean(prices), 2),
                    'min': round(min(prices), 2),
                    'max': round(max(prices), 2)
                }

        # Find optimal usage times
        best_hours = sorted(hourly_stats.items(), key=lambda x: x[1]['average'])[:3] if hourly_stats else []
        worst_hours = sorted(hourly_stats.items(), key=lambda x: x[1]['average'], reverse=True)[:3] if hourly_stats else []

        return render_template(
            'dashboard.html',
            user=user_prefs,
            analytics=analytics,
            insights=insights,
            price_history=price_history,
            daily_stats=daily_stats,
            hourly_stats=hourly_stats,
            best_hours=best_hours,
            worst_hours=worst_hours
        )

    except Exception as e:
        return render_template('error.html', message=str(e)), 500

@app.route('/api/analytics/<chat_id>')
def get_user_analytics(chat_id):
    """Get analytics data for a specific user"""
    try:
        analytics = UserAnalytics.query.filter_by(chat_id=chat_id)\
            .order_by(UserAnalytics.timestamp.desc())\
            .first()

        if not analytics:
            return jsonify({
                'error': 'No analytics data found',
                'chat_id': chat_id
            }), 404

        return jsonify({
            'avg_daily_price': analytics.avg_daily_price,
            'peak_usage_time': analytics.peak_usage_time.strftime('%H:%M') if analytics.peak_usage_time else None,
            'low_price_periods': analytics.low_price_periods,
            'high_price_periods': analytics.high_price_periods,
            'monthly_price_trend': analytics.monthly_price_trend,
            'timestamp': analytics.timestamp.isoformat()
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/insights/<chat_id>')
def get_user_insights(chat_id):
    """Get savings insights for a specific user"""
    try:
        insights = SavingsInsight.get_user_insights(chat_id)

        return jsonify([{
            'potential_savings': insight.potential_savings,
            'recommendation_type': insight.recommendation_type,
            'description': insight.description,
            'impact_score': insight.impact_score,
            'implemented': insight.implemented,
            'timestamp': insight.timestamp.isoformat()
        } for insight in insights])

    except Exception as e:
        return jsonify({'error': str(e)}), 500