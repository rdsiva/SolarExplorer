"""Helper functions for generating analytics insights"""
from datetime import datetime, timedelta
import numpy as np
from typing import List, Dict, Tuple
from models import PriceHistory, SavingsInsight

def analyze_price_patterns(price_history: List[PriceHistory]) -> Dict:
    """Analyze price patterns to find optimal usage times and potential savings"""
    if not price_history:
        return {}

    # Get hourly averages
    hourly_prices = {}
    for record in price_history:
        hour = record.timestamp.hour
        if hour not in hourly_prices:
            hourly_prices[hour] = []
        hourly_prices[hour].append(float(record.hourly_price))

    # Calculate statistics for each hour
    hourly_stats = {}
    for hour, prices in hourly_prices.items():
        prices = [float(p) for p in prices]  # Convert to float
        hourly_stats[hour] = {
            'average': round(float(np.mean(prices)), 2),
            'std': round(float(np.std(prices)), 2),
            'samples': len(prices)
        }

    return hourly_stats

def generate_savings_insights(chat_id: str, price_history: List[PriceHistory]) -> List[Dict]:
    """Generate actionable savings insights based on price patterns"""
    if not price_history:
        return []

    insights = []
    hourly_stats = analyze_price_patterns(price_history)

    # Find peak and off-peak periods
    avg_prices = {hour: stats['average'] for hour, stats in hourly_stats.items()}
    sorted_hours = sorted(avg_prices.items(), key=lambda x: x[1])

    # Calculate potential savings
    peak_hours = sorted_hours[-3:]  # Top 3 most expensive hours
    off_peak_hours = sorted_hours[:3]  # Top 3 cheapest hours

    avg_peak_price = float(np.mean([price for _, price in peak_hours]))
    avg_off_peak_price = float(np.mean([price for _, price in off_peak_hours]))
    potential_savings = round(float((avg_peak_price - avg_off_peak_price) * 30), 2)  # Monthly savings estimate

    # Generate peak usage insight
    peak_hours_str = ", ".join([f"{hour}:00" for hour, _ in peak_hours])
    insights.append({
        'type': 'shift_usage',
        'savings': float(potential_savings),
        'description': f"Shift energy-intensive activities away from peak hours ({peak_hours_str}) "
                    f"to save up to ${potential_savings:.2f} monthly",
        'impact_score': min(int((potential_savings / 10) * 100), 100)  # Scale impact score based on savings
    })

    # Generate off-peak usage recommendation
    off_peak_hours_str = ", ".join([f"{hour}:00" for hour, _ in off_peak_hours])
    insights.append({
        'type': 'optimal_usage',
        'savings': float(potential_savings * 0.8),  # Conservative estimate
        'description': f"Schedule high-energy tasks during off-peak hours ({off_peak_hours_str}) "
                    f"for optimal savings",
        'impact_score': 85
    })

    return insights

def calculate_weekly_savings_potential(price_history: List[PriceHistory]) -> float:
    """Calculate potential weekly savings based on optimal usage patterns"""
    if not price_history:
        return 0.0

    hourly_stats = analyze_price_patterns(price_history)
    avg_prices = [float(stats['average']) for stats in hourly_stats.values()]

    best_price = float(min(avg_prices))
    avg_price = float(np.mean(avg_prices))

    # Assume 20% of usage can be shifted to optimal times
    potential_savings = float((avg_price - best_price) * 24 * 7 * 0.2)
    return round(potential_savings, 2)

def calculate_prediction_accuracy(price_history: List[PriceHistory], window_days: int = 30) -> float:
    """Calculate the accuracy of predictions based on user feedback"""
    if not price_history:
        return 0.0

    # Filter records with feedback
    feedback_records = [
        record for record in price_history 
        if record.prediction_accuracy is not None
    ]

    if not feedback_records:
        return 0.0

    # Calculate weighted average accuracy based on recency
    total_weight = 0
    weighted_accuracy = 0.0

    for record in feedback_records:
        # More recent feedback has higher weight
        days_old = (datetime.utcnow() - record.timestamp).days
        weight = 1.0 / (days_old + 1)  # Avoid division by zero

        weighted_accuracy += float(record.prediction_accuracy) * weight
        total_weight += weight

    return round(float(weighted_accuracy / total_weight if total_weight > 0 else 0.0), 2)