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
        hourly_prices[hour].append(record.hourly_price)
    
    # Calculate statistics for each hour
    hourly_stats = {}
    for hour, prices in hourly_prices.items():
        hourly_stats[hour] = {
            'average': round(np.mean(prices), 2),
            'std': round(np.std(prices), 2),
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
    
    avg_peak_price = np.mean([price for _, price in peak_hours])
    avg_off_peak_price = np.mean([price for _, price in off_peak_hours])
    potential_savings = round((avg_peak_price - avg_off_peak_price) * 30, 2)  # Monthly savings estimate
    
    # Generate peak usage insight
    peak_hours_str = ", ".join([f"{hour}:00" for hour, _ in peak_hours])
    insights.append({
        'type': 'shift_usage',
        'savings': potential_savings,
        'description': f"Shift energy-intensive activities away from peak hours ({peak_hours_str}) "
                      f"to save up to ${potential_savings:.2f} monthly",
        'impact_score': min(int((potential_savings / 10) * 100), 100)  # Scale impact score based on savings
    })
    
    # Generate off-peak usage recommendation
    off_peak_hours_str = ", ".join([f"{hour}:00" for hour, _ in off_peak_hours])
    insights.append({
        'type': 'optimal_usage',
        'savings': potential_savings * 0.8,  # Conservative estimate
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
    avg_prices = [stats['average'] for stats in hourly_stats.values()]
    
    best_price = min(avg_prices)
    avg_price = np.mean(avg_prices)
    
    # Assume 20% of usage can be shifted to optimal times
    potential_savings = (avg_price - best_price) * 24 * 7 * 0.2
    return round(potential_savings, 2)
