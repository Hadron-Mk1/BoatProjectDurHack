"""
Unit tests for CommsHub.
Verifies agent registration, broadcast delivery, targeted direct messaging,
message serialization, and decoupled packet delivery.
"""
import pytest
from src.core.comms_hub import CommsHub, Message

@pytest.fixture
def hub():
    """Provides a fresh CommsHub instance."""
    return CommsHub()

def test_comms_hub_registration(hub):
    """Verify agents can register, query registration, and unregister."""
    received = []
    handler = lambda msg: received.append(msg)
    
    assert hub.is_registered(1) is False
    hub.register_agent(1, handler)
    assert hub.is_registered(1) is True
    
    hub.unregister_agent(1)
    assert hub.is_registered(1) is False

def test_broadcast_delivery_excludes_sender(hub):
    """A broadcast must be delivered to all registered peers except the sender."""
    inboxes = {1: [], 2: [], 3: []}
    
    hub.register_agent(1, lambda msg: inboxes[1].append(msg))
    hub.register_agent(2, lambda msg: inboxes[2].append(msg))
    hub.register_agent(3, lambda msg: inboxes[3].append(msg))
    
    payload = {"school_id": 42, "pos": (150, 250)}
    hub.send_broadcast(sender_id=1, msg_type=Message.DISCOVERY, payload=payload)
    
    # Sender does not receive its own broadcast
    assert len(inboxes[1]) == 0
    # Peers receive the message
    assert len(inboxes[2]) == 1
    assert len(inboxes[3]) == 1
    
    msg = inboxes[2][0]
    assert msg.sender_id == 1
    assert msg.msg_type == Message.DISCOVERY
    assert msg.payload == payload
    assert msg.target_id is None

def test_direct_messaging(hub):
    """Direct message is delivered only to the target agent."""
    inboxes = {1: [], 2: [], 3: []}
    
    hub.register_agent(1, lambda msg: inboxes[1].append(msg))
    hub.register_agent(2, lambda msg: inboxes[2].append(msg))
    hub.register_agent(3, lambda msg: inboxes[3].append(msg))
    
    delivered = hub.send_direct(
        sender_id=1,
        target_id=2,
        msg_type=Message.ASSISTANCE_REQUEST,
        payload={"op_id": "op_9"},
    )
    assert delivered is True
    assert len(inboxes[1]) == 0
    assert len(inboxes[2]) == 1
    assert len(inboxes[3]) == 0
    
    assert inboxes[2][0].target_id == 2
    assert inboxes[2][0].msg_type == Message.ASSISTANCE_REQUEST

def test_direct_messaging_unregistered_target(hub):
    """Sending direct to an unregistered target returns False without exception."""
    hub.register_agent(1, lambda m: None)
    delivered = hub.send_direct(sender_id=1, target_id=99, msg_type="PING")
    assert delivered is False

def test_message_log_retention(hub):
    """CommsHub correctly logs transmitted messages."""
    hub.register_agent(1, lambda m: None)
    hub.register_agent(2, lambda m: None)
    
    hub.send_broadcast(1, "MSG_1")
    hub.send_direct(2, 1, "MSG_2")
    
    log = hub.get_message_log()
    assert len(log) == 2
    assert log[0].msg_type == "MSG_1"
    assert log[1].msg_type == "MSG_2"
    assert hub.total_messages_sent == 2
