"""Tests for LLMResearchAgent circuit breaker integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from quantlab.robustness.circuit_breaker import CircuitOpenError
from quantlab.robustness.llm_circuit_breaker import LLMCircuitBreaker
from quantlab.agents.llm_research_agent import LLMResearchAgent


class TestLLMResearchAgentCircuitBreakerIntegration:
    """LLMResearchAgent wraps call_llm() with LLMCircuitBreaker."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_wraps_call_llm(self):
        """GIVEN an LLMResearchAgent with a circuit breaker, WHEN generate_config() is called,
        THEN call_llm() is executed through the circuit breaker."""
        lb = LLMCircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        agent = LLMResearchAgent(circuit_breaker=lb)

        # Verify the agent has a circuit breaker
        assert agent._circuit_breaker is lb

    @pytest.mark.asyncio
    async def test_open_circuit_skips_llm_and_triggers_fallback(self):
        """GIVEN an OPEN circuit breaker, WHEN generate_config() is called,
        THEN the LLM call is skipped and fallback is triggered."""
        lb = LLMCircuitBreaker(failure_threshold=1, recovery_timeout=0.5)

        # Open the circuit by recording a failure
        async def fail_llm():
            raise RuntimeError("LLM timeout")

        with pytest.raises(RuntimeError):
            await lb.call(fail_llm())
        assert lb.state == "OPEN"

        # Now create an agent with the open circuit breaker
        agent = LLMResearchAgent(circuit_breaker=lb)

        # Mock the fallback class to return a mock agent
        mock_fallback_agent = MagicMock()
        mock_fallback_agent.generate_config = AsyncMock(return_value=MagicMock())
        mock_fallback_cls = MagicMock(return_value=mock_fallback_agent)
        agent._fallback_cls = mock_fallback_cls

        # generate_config should catch CircuitOpenError and trigger fallback
        result = await agent.generate_config(
            objectives=["test objective"],
            llm_config=MagicMock(provider="openai", model="gpt-4"),
        )

        # Fallback should have been called because circuit is OPEN
        mock_fallback_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_closed_circuit_allows_llm_call(self):
        """GIVEN a CLOSED circuit breaker, WHEN generate_config() is called,
        THEN call_llm() proceeds normally through the circuit breaker."""
        lb = LLMCircuitBreaker()
        agent = LLMResearchAgent(circuit_breaker=lb)

        # Verify the agent has a circuit breaker in CLOSED state
        assert agent._circuit_breaker.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_no_circuit_breaker_uses_default(self):
        """GIVEN an LLMResearchAgent without a circuit breaker, WHEN created,
        THEN a default LLMCircuitBreaker is used."""
        agent = LLMResearchAgent()

        assert agent._circuit_breaker is not None
        assert isinstance(agent._circuit_breaker, LLMCircuitBreaker)
        assert agent._circuit_breaker.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_counted_on_llm_error(self):
        """GIVEN a CLOSED circuit breaker, WHEN call_llm() raises an error,
        THEN the circuit breaker records the failure."""
        lb = LLMCircuitBreaker(failure_threshold=2)
        agent = LLMResearchAgent(circuit_breaker=lb)

        # Simulate an LLM call failure through the circuit breaker
        async def fail_llm():
            raise RuntimeError("LLM API error")

        with pytest.raises(RuntimeError):
            await lb.call(fail_llm())

        # Circuit should still be CLOSED (only 1 failure, threshold is 2)
        assert lb.state == "CLOSED"
        assert lb._circuit_breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold_failures(self):
        """GIVEN a circuit breaker with failure_threshold=2, WHEN call_llm() fails twice,
        THEN the circuit opens and subsequent calls skip the LLM."""
        lb = LLMCircuitBreaker(failure_threshold=2, recovery_timeout=0.5)
        agent = LLMResearchAgent(circuit_breaker=lb)

        async def fail_llm():
            raise RuntimeError("LLM API error")

        with pytest.raises(RuntimeError):
            await lb.call(fail_llm())
        with pytest.raises(RuntimeError):
            await lb.call(fail_llm())

        assert lb.state == "OPEN"

        # Next call should raise CircuitOpenError (skipping LLM)
        with pytest.raises(CircuitOpenError):
            await lb.call(fail_llm())
