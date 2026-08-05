"""
Tests for app/chatbot/agent.py using FakeQwenClient -- no Ollama
required. Verifies session handling, business-logic wiring, and that
the vulnerable/hardened mode difference actually reaches end-to-end
behavior through the agent.
"""
from app.chatbot.agent import SupportAgent
from app.services.qwen_client import FakeQwenClient


def make_agent(mode="vulnerable", canned="ok"):
    client = FakeQwenClient(canned_response=canned)
    agent = SupportAgent(model_client=client, mode=mode)
    return agent, client


def test_general_chat_does_not_touch_database():
    agent, _ = make_agent()
    result = agent.send("s1", "Hello there!")
    assert result["intent"] == "general"
    assert result["database_accessed"] is False


def test_order_status_flags_database_accessed():
    agent, _ = make_agent()
    result = agent.send("s1", "Where is ORD-1001? my email is attacker@example.com")
    assert result["intent"] == "order_status"
    assert result["database_accessed"] is True
    assert "orders" in result["tables_used"]


def test_vulnerable_order_lookup_succeeds_with_wrong_email():
    agent, client = make_agent(mode="vulnerable", canned="Here is your order info.")
    agent.send("s1", "Check ORD-1001, my email is definitely-not-alice@example.com")
    # business context should have been built with real order info since
    # the planted BOLA bug authorizes on presence alone
    sent_context = [m["content"] for m in client.last_messages if m["role"] == "system"]
    assert any("ORD-1001" in c for c in sent_context)


def test_hardened_order_lookup_fails_with_wrong_email():
    agent, client = make_agent(mode="hardened", canned="Sorry, I can't verify that.")
    agent.send("s1", "Check ORD-1001, my email is definitely-not-alice@example.com")
    sent_context = [m["content"] for m in client.last_messages if m["role"] == "system"]
    assert not any("ORD-1001" in c and "unauthorized" not in c for c in sent_context)
    assert any("unauthorized" in c for c in sent_context)


def test_session_remembers_authenticated_email_across_turns():
    agent, client = make_agent(mode="hardened")
    agent.send("s1", "Check ORD-1001 for alice.johnson@example.com")
    # Second turn doesn't repeat the email; session should remember it.
    agent.send("s1", "And what about ORD-1002?")
    sent_context = [m["content"] for m in client.last_messages if m["role"] == "system"]
    assert any("ORD-1002" in c for c in sent_context)


def test_reset_clears_session_state():
    agent, _ = make_agent()
    agent.send("s1", "hello")
    assert agent.reset_session("s1") is True
    assert agent.sessions.get_history("s1") == []
    assert agent.reset_session("s1") is False


def test_diagnostics_included_when_requested():
    agent, _ = make_agent(canned="A perfectly clean answer.")
    result = agent.send("s1", "hi", include_diagnostics=True)
    assert "diagnostics" in result
    assert result["diagnostics"]["canary_leaked"] is False


def test_diagnostics_omitted_by_default():
    agent, _ = make_agent()
    result = agent.send("s1", "hi")
    assert "diagnostics" not in result


def test_ticket_create_flow():
    agent, client = make_agent(canned="Ticket created!")
    result = agent.send(
        "s1", "I want to report a problem: my case arrived damaged. email: brian.kim@example.com"
    )
    assert result["intent"] == "ticket_create"
    assert result["database_accessed"] is True
