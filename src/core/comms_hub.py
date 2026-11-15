"""
CommsHub for FishSwarm.
Provides a modular message broker for decoupled agent communication.
Starts with 100% reliable direct delivery, with architectural hooks for
packet loss, latency buffers, and range attenuation in later phases.
"""
from dataclasses import dataclass, field
import time
from typing import Callable, Optional

@dataclass
class Message:
    """Standardized communication packet between simulation entities."""
    msg_type: str
    sender_id: int
    target_id: Optional[int]  # None indicates broadcast to all
    payload: dict = field(default_factory=dict)
    timestamp: float = 0.0

    # Common Message Types
    DISCOVERY = "DISCOVERY"
    ASSISTANCE_REQUEST = "ASSISTANCE_REQUEST"
    ASSISTANCE_CONFIRMED = "ASSISTANCE_CONFIRMED"
    ASSISTANCE_CANCELLED = "ASSISTANCE_CANCELLED"
    SCHOOL_DEPLETED = "SCHOOL_DEPLETED"
    OPERATION_CANCELLED = "OPERATION_CANCELLED"
    OIL_SPILL_ALERT = "OIL_SPILL_ALERT"
    OIL_SPILL_DISTRESS = "OIL_SPILL_DISTRESS"
    OIL_SPILL_CLEARED = "OIL_SPILL_CLEARED"
    RESCUE_REQUEST = "RESCUE_REQUEST"
    RESCUE_DISPATCH = "RESCUE_DISPATCH"
    RESCUE_ATTACHED = "RESCUE_ATTACHED"
    RESCUE_COMPLETED = "RESCUE_COMPLETED"

class CommsHub:
    """
    Modular message broker managing delivery between autonomous agents.
    """
    
    def __init__(self, packet_loss_rate: float = 0.0, max_range: Optional[float] = None):
        self._handlers: dict[int, Callable[[Message], None]] = {}
        self._message_log: list[Message] = []
        self.packet_loss_rate = float(packet_loss_rate)
        self.max_range = max_range
        self.total_messages_sent = 0
        self.total_messages_dropped = 0

    def register_agent(self, agent_id: int, handler: Callable[[Message], None]):
        """Registers an agent handler callback for incoming messages."""
        self._handlers[int(agent_id)] = handler

    def unregister_agent(self, agent_id: int):
        """Unregisters an agent from the communications network."""
        self._handlers.pop(int(agent_id), None)

    def is_registered(self, agent_id: int) -> bool:
        """Checks if an agent is currently registered."""
        return int(agent_id) in self._handlers

    def send_broadcast(
        self,
        sender_id: int,
        msg_type: str,
        payload: Optional[dict] = None,
        timestamp: Optional[float] = None,
    ):
        """
        Broadcasts a message to all registered agents (excluding sender).
        """
        t = timestamp if timestamp is not None else time.time()
        msg = Message(
            msg_type=msg_type,
            sender_id=sender_id,
            target_id=None,
            payload=payload if payload is not None else {},
            timestamp=t,
        )
        self._message_log.append(msg)
        self.total_messages_sent += 1

        for target_id, handler in list(self._handlers.items()):
            if target_id != sender_id:
                handler(msg)

    def broadcast(self, msg: Message):
        """Broadcasts an already instantiated Message."""
        self._message_log.append(msg)
        self.total_messages_sent += 1
        for target_id, handler in list(self._handlers.items()):
            if target_id != msg.sender_id:
                handler(msg)

    def send_direct(
        self,
        sender_id: int,
        target_id: int,
        msg_type: str,
        payload: Optional[dict] = None,
        timestamp: Optional[float] = None,
    ) -> bool:
        """
        Sends a direct message to a specific target agent.
        Returns True if delivered, False if target is not registered.
        """
        t = timestamp if timestamp is not None else time.time()
        msg = Message(
            msg_type=msg_type,
            sender_id=sender_id,
            target_id=target_id,
            payload=payload if payload is not None else {},
            timestamp=t,
        )
        self._message_log.append(msg)
        self.total_messages_sent += 1

        handler = self._handlers.get(target_id)
        if handler is not None:
            handler(msg)
            return True
        return False

    def get_message_log(self, limit: Optional[int] = None) -> list[Message]:
        """Returns message log history."""
        if limit is None:
            return list(self._message_log)
        return self._message_log[-limit:]

    def clear_log(self):
        """Clears the message history."""
        self._message_log.clear()
        self.total_messages_sent = 0
        self.total_messages_dropped = 0
