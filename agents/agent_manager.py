"""Agent manager module to handle agent initialization and management"""
import logging
from typing import List
from .base_agent import BaseAgent
from .live_price_agent import LivePriceAgent
from .notification_agent import NotificationAgent
from .analysis_agent import AnalysisAgent
from .data_collection_agent import DataCollectionAgent

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
                DataCollectionAgent()
            ]
            logger.info(f"Initialized {len(self._agents)} agents")
        except Exception as e:
            logger.error(f"Error initializing agents: {str(e)}", exc_info=True)
            raise

    def get_agents(self) -> List[BaseAgent]:
        """Get all initialized agents"""
        return self._agents

    def get_agent_statuses(self):
        """Get detailed status information for all agents"""
        agent_statuses = []
        for agent in self._agents:
            try:
                status = agent.get_status()
                # Add additional display-friendly information
                status['queue_size'] = 0  # Initialize to 0 since agents just created
                status['last_run'] = status.get('last_run', 'Never')
                status['status_class'] = 'bg-green-100 text-green-800' if status.get('running', False) else 'bg-red-100 text-red-800'
                status['status_text'] = 'Active' if status.get('running', False) else 'Inactive'
                agent_statuses.append(status)
            except Exception as e:
                logger.error(f"Error getting status for agent {agent.name}: {str(e)}")
                continue
        
        return agent_statuses

    def start_all_agents(self):
        """Start all registered agents"""
        for agent in self._agents:
            try:
                agent.start()
                logger.info(f"Started agent: {agent.name}")
            except Exception as e:
                logger.error(f"Error starting agent {agent.name}: {str(e)}")

    def stop_all_agents(self):
        """Stop all registered agents"""
        for agent in self._agents:
            try:
                agent.stop()
                logger.info(f"Stopped agent: {agent.name}")
            except Exception as e:
                logger.error(f"Error stopping agent {agent.name}: {str(e)}")
