"""Agent manager module to handle agent initialization and management"""
import logging
from typing import List, Dict, Any
from datetime import datetime
from .base_agent import BaseAgent
from .live_price_agent import LivePriceAgent
from .notification_agent import NotificationAgent
from .analysis_agent import AnalysisAgent
from .data_collection_agent import DataCollectionAgent
from .coordinator_agent import CoordinatorAgent
from .prediction_agent import PricePredictionAgent

logger = logging.getLogger(__name__)

class AgentManager:
    _instance = None
    _agents: List[BaseAgent] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self._agents = []
            self.initialize_agents()

    def initialize_agents(self):
        """Initialize all system agents with their configurations"""
        try:
            self._agents = [
                LivePriceAgent(config={'price_threshold': 3.0, 'check_interval': 300}),
                NotificationAgent(),
                AnalysisAgent(),
                DataCollectionAgent(),
                CoordinatorAgent(),
                PricePredictionAgent()
            ]
            logger.info(f"Initialized {len(self._agents)} agents")
        except Exception as e:
            logger.error(f"Error initializing agents: {str(e)}", exc_info=True)
            raise

    def get_agents(self) -> List[BaseAgent]:
        """Get all initialized agents"""
        return self._agents

    def get_agent_statuses(self) -> List[Dict[str, Any]]:
        """Get detailed status information for all agents"""
        agent_statuses = []
        for agent in self._agents:
            try:
                # Get base status
                status = agent.get_status()

                # Ensure all required fields are present
                status.update({
                    'name': agent.name,
                    'type': agent.__class__.__name__,
                    'running': status.get('running', False),
                    'queue_size': status.get('queue_size', 0),
                    'total_messages_processed': status.get('total_messages_processed', 0),
                    'last_run': status.get('last_run', 'Never'),
                    'last_error': status.get('last_error', None),
                    'last_error_time': status.get('last_error_time', None),
                    'consecutive_failures': status.get('consecutive_failures', 0),
                    'subscriptions': status.get('subscriptions', []),
                    'config': getattr(agent, 'config', {}),
                })

                # Add UI specific fields
                status['status_class'] = (
                    'bg-green-100 text-green-800' if status['running']
                    else 'bg-red-100 text-red-800'
                )
                status['status_text'] = 'Active' if status['running'] else 'Inactive'

                agent_statuses.append(status)
                logger.debug(f"Got status for agent {agent.name}: {status}")
            except Exception as e:
                logger.error(f"Error getting status for agent {agent.name}: {str(e)}")
                # Add a minimal status entry for failed agents
                agent_statuses.append({
                    'name': getattr(agent, 'name', 'Unknown Agent'),
                    'type': agent.__class__.__name__,
                    'running': False,
                    'status_text': 'Error',
                    'status_class': 'bg-red-100 text-red-800',
                    'last_error': str(e),
                    'last_error_time': datetime.now().isoformat(),
                    'queue_size': 0,
                    'total_messages_processed': 0,
                    'consecutive_failures': 1,
                    'subscriptions': [],
                    'config': {}
                })

        return agent_statuses

    async def start_all_agents(self):
        """Start all registered agents"""
        for agent in self._agents:
            try:
                await agent.start()
                logger.info(f"Started agent: {agent.name}")
            except Exception as e:
                logger.error(f"Error starting agent {agent.name}: {str(e)}")

    async def stop_all_agents(self):
        """Stop all registered agents"""
        for agent in self._agents:
            try:
                await agent.stop()
                logger.info(f"Stopped agent: {agent.name}")
            except Exception as e:
                logger.error(f"Error stopping agent {agent.name}: {str(e)}")