"""Message protocol definitions for inter-agent communication."""
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class MessagePriority(Enum):
    """Priority levels for inter-agent messages."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

class MessageType(Enum):
    """Types of messages that can be exchanged between agents."""
    PRICE_UPDATE = "price_update"
    PATTERN_ANALYSIS = "pattern_analysis"
    PREDICTION = "prediction"
    DASHBOARD_UPDATE = "dashboard_update"
    PREFERENCE_UPDATE = "preference_update"
    COMMAND = "command"
    RESPONSE = "response"
    ERROR = "error"

class Message:
    """Standard message format for inter-agent communication."""
    def __init__(
        self,
        msg_type: MessageType,
        source: str,
        target: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: Optional[str] = None
    ):
        self.type = msg_type
        self.source = source
        self.target = target
        self.payload = payload
        self.priority = priority
        self.timestamp = datetime.utcnow().isoformat()
        self.correlation_id = correlation_id or f"{source}-{target}-{datetime.utcnow().timestamp()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        return {
            'type': self.type.value,
            'source': self.source,
            'target': self.target,
            'payload': self.payload,
            'priority': self.priority.value,
            'timestamp': self.timestamp,
            'correlation_id': self.correlation_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message instance from dictionary."""
        return cls(
            msg_type=MessageType(data['type']),
            source=data['source'],
            target=data['target'],
            payload=data['payload'],
            priority=MessagePriority(data['priority']),
            correlation_id=data.get('correlation_id')
        )

    def validate(self) -> bool:
        """Validate message format and content."""
        try:
            # Check required fields
            if not all([self.type, self.source, self.target, self.payload]):
                logger.error("Missing required fields in message")
                return False
            
            # Ensure payload is JSON serializable
            json.dumps(self.payload)
            
            # Validate timestamp format
            datetime.fromisoformat(self.timestamp)
            
            return True
        except Exception as e:
            logger.error(f"Message validation failed: {str(e)}")
            return False
