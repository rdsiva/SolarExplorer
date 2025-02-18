from flask import jsonify, render_template
from app import app
from agents.agent_manager import AgentManager
from agents.live_price_agent import LivePriceAgent
import logging

logger = logging.getLogger(__name__)

@app.route('/agent-monitor')
def agent_monitor():
    """Display the agent monitoring dashboard."""
    try:
        # Get agent statuses from AgentManager singleton
        agent_manager = AgentManager()
        agent_statuses = agent_manager.get_agent_statuses()

        # Calculate dashboard metrics
        total_agents = len(agent_statuses)
        active_agents = sum(1 for status in agent_statuses if status.get('running', False))
        total_messages = sum(status.get('total_messages_processed', 0) for status in agent_statuses)
        system_healthy = all(
            not status.get('last_error')
            and (status.get('consecutive_failures', 0) == 0)
            for status in agent_statuses
        )

        logger.info(f"Rendering agent monitor with {len(agent_statuses)} agents")
        return render_template(
            'agent_dashboard.html',
            agents=agent_statuses,
            total_agents=total_agents,
            active_agents=active_agents,
            total_messages=total_messages,
            system_healthy=system_healthy
        )

    except Exception as e:
        logger.error(f"Error displaying agent monitor: {str(e)}", exc_info=True)
        return render_template('error.html',
            message="An error occurred while loading the agent monitor."), 500

@app.route('/api/live-price')
async def get_live_price():
    """Get current price data from the LivePrice agent"""
    try:
        agent_manager = AgentManager()
        live_price_agent = next(
            (agent for agent in agent_manager.get_agents() 
             if isinstance(agent, LivePriceAgent)), None)

        if not live_price_agent:
            return jsonify({
                'error': 'LivePrice agent not found',
                'status': 'error'
            }), 404

        price_data = await live_price_agent.get_current_price()
        return jsonify({
            'status': 'success',
            'data': price_data
        })

    except Exception as e:
        logger.error(f"Error getting live price: {str(e)}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

# Root route shows the agent monitor
@app.route('/')
def index():
    """Home page redirects to agent monitor"""
    return agent_monitor()