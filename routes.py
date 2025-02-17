from flask import jsonify, render_template, request, redirect, url_for
from datetime import datetime, timedelta
import numpy as np
from app import app
from providers.comed_provider import ComedProvider
from models import UserPreferences, UserAnalytics, SavingsInsight, PriceHistory, TeslaPreferences
from agents.tesla_charging_agent import TeslaAPI
import logging
import os
from typing import Dict, List, Any
from agents.base_agent import BaseAgent
from agents.live_price_agent import LivePriceAgent
from agents.notification_agent import NotificationAgent
from agents.analysis_agent import AnalysisAgent
from agents.data_collection_agent import DataCollectionAgent


logger = logging.getLogger(__name__)

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
            try:
                user_prefs = UserPreferences.get_user_preferences(chat_id)
                if not user_prefs:
                    user_prefs = UserPreferences.create_or_update(
                        chat_id=chat_id,
                        price_threshold=3.0,  # Default threshold
                        alert_frequency='immediate'
                    )
            except Exception as db_error:
                logger.error(f"Database error while accessing user preferences: {str(db_error)}")
                return render_template('error.html', 
                    message="Unable to access user preferences. Please try again later."), 500

        # Get latest analytics and price history
        try:
            analytics = UserAnalytics.query.filter_by(chat_id=chat_id)\
                .order_by(UserAnalytics.timestamp.desc())\
                .first()

            price_history = PriceHistory.get_recent_history(
                provider="ComEd",
                hours=24 * 7  # Last week of data
            ) or []  # Default to empty list if no data
        except Exception as data_error:
            logger.error(f"Error fetching analytics data: {str(data_error)}")
            analytics = None
            price_history = []

        # Generate insights or use defaults
        try:
            from utils.analytics_helper import generate_savings_insights, calculate_weekly_savings_potential
            new_insights = generate_savings_insights(chat_id, price_history)
            weekly_savings = calculate_weekly_savings_potential(price_history)
        except Exception as insight_error:
            logger.error(f"Error generating insights: {str(insight_error)}")
            weekly_savings = 0.0
            new_insights = []

        # Get all insights for display
        try:
            insights = SavingsInsight.get_user_insights(chat_id, days=30) or []
        except Exception as insight_fetch_error:
            logger.error(f"Error fetching insights: {str(insight_fetch_error)}")
            insights = []

        # Calculate stats with safe defaults
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
                    'average': round(sum(prices) / len(prices), 2),
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
                    'average': round(sum(prices) / len(prices), 2),
                    'min': round(min(prices), 2),
                    'max': round(max(prices), 2)
                }

        # Find optimal usage times (safely handle empty data)
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
            worst_hours=worst_hours,
            weekly_savings_potential=weekly_savings,
            has_data=bool(price_history)  # Add flag for template
        )

    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}", exc_info=True)
        return render_template('error.html', 
            message="An error occurred while loading the dashboard. Please try again later."), 500

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

@app.route('/tesla/oauth/callback')
def tesla_oauth_callback():
    """Handle Tesla OAuth callback"""
    try:
        code = request.args.get('code')
        state = request.args.get('state')

        logger.info(f"Received OAuth callback with parameters: code={bool(code)}, state={bool(state)}")

        if not all([code, state]):
            missing_params = []
            if not code:
                missing_params.append('code')
            if not state:
                missing_params.append('state')

            error_msg = f"Missing required OAuth parameters: {', '.join(missing_params)}"
            logger.error(error_msg)
            return render_template('error.html', 
                message=error_msg), 400

        # Extract chat_id from state parameter
        try:
            state_parts = state.split('_')
            if len(state_parts) != 2:
                raise ValueError("Invalid state format")
            state_uuid, chat_id = state_parts
            logger.info(f"Extracted chat_id from state: {chat_id}")
        except Exception as e:
            logger.error(f"Failed to extract chat_id from state: {str(e)}")
            return render_template('error.html',
                message="Invalid state parameter format"), 400

        # Verify state matches stored state
        prefs = TeslaPreferences.get_preferences(chat_id)
        if not prefs or prefs.oauth_state != state:
            error_msg = f"OAuth state mismatch for chat_id: {chat_id}"
            logger.error(error_msg)
            if not prefs:
                logger.error("No Tesla preferences found for this chat_id")
            else:
                logger.error(f"Stored state: {prefs.oauth_state}, Received state: {state}")
            return render_template('error.html', 
                message="Invalid OAuth state parameter"), 400

        # Exchange code for tokens
        api = TeslaAPI()
        logger.info(f"Exchanging authorization code for tokens for chat_id: {chat_id}")
        result = api.exchange_code_for_token(code, state)

        if not result['success']:
            error_msg = f"Token exchange failed: {result.get('error')}"
            logger.error(error_msg)
            return render_template('error.html', 
                message="Failed to complete authentication"), 400

        # Update Tesla preferences with tokens
        logger.info(f"Updating Tesla preferences with new tokens for chat_id: {chat_id}")
        prefs.update_auth_tokens(
            access_token=result['access_token'],
            refresh_token=result['refresh_token']
        )

        # Redirect to success page using the same domain as the callback URL
        success_url = "https://1a8446b3-198e-4458-9e5f-60fa0a94ff1f-00-1nh6gkpmzmrcg.janeway.replit.dev/tesla/success"
        logger.info(f"OAuth flow completed successfully for chat_id: {chat_id}")
        logger.info(f"Redirecting to success URL: {success_url}")
        return redirect(success_url)

    except Exception as e:
        logger.error(f"Error in Tesla OAuth callback: {str(e)}", exc_info=True)
        return render_template('error.html', 
            message="An error occurred during authentication"), 500

@app.route('/tesla/success')
def tesla_success():
    """Display Tesla authentication success page"""
    return render_template('tesla_success.html', 
        message="Tesla authentication successful! You can now close this window and return to the Telegram bot.")

@app.route('/tesla/test-callback')
def test_tesla_callback():
    """Test endpoint to verify Tesla OAuth callback is properly registered"""
    logger.info("Tesla callback test endpoint accessed")
    callback_url = "https://1a8446b3-198e-4458-9e5f-60fa0a94ff1f-00-1nh6gkpmzmrcg.janeway.replit.dev/tesla/oauth/callback"
    logger.info(f"Generated callback URL: {callback_url}")
    return jsonify({
        'status': 'success',
        'message': 'Tesla OAuth callback test endpoint is accessible',
        'callback_url': callback_url
    })

@app.route('/agent-monitor')
def agent_monitor():
    """Display the agent monitoring dashboard."""
    try:
        # Initialize agents if needed (in real app these would be persistent)
        agents: List[BaseAgent] = [
            LivePriceAgent(config={'price_threshold': 3.0, 'check_interval': 300}),
            NotificationAgent(),
            AnalysisAgent(),
            DataCollectionAgent()
        ]

        # Collect agent statuses
        agent_statuses = [agent.get_status() for agent in agents]

        # Calculate dashboard metrics
        total_agents = len(agents)
        active_agents = sum(1 for status in agent_statuses if status.get('running', False))
        total_messages = sum(status.get('queue_size', 0) for status in agent_statuses)
        system_healthy = all(
            not status.get('last_error')
            and (status.get('consecutive_failures', 0) == 0)
            for status in agent_statuses
        )

        return render_template(
            'agent_dashboard.html',
            agents=agent_statuses,
            total_agents=total_agents,
            active_agents=active_agents,
            total_messages=total_messages,
            system_healthy=system_healthy
        )

    except Exception as e:
        logger.error(f"Error displaying agent monitor: {str(e)}")
        return render_template('error.html',
            message="An error occurred while loading the agent monitor."), 500