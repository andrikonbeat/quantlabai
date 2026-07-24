"""Integration test for knowledge lake agent memory functionality."""

import asyncio
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from quantlab.agents.memory import AgentMemoryManager
from quantlab.knowledge.store import KnowledgeStore


class TestKnowledgeLakeAgentMemory:
    """Test agent memory directories and basic functionality."""

    @pytest.fixture
    def temp_knowledge_lake(self):
        """Create a temporary Knowledge Lake for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kl_path = Path(tmpdir) / "knowledge"
            kl_path.mkdir(parents=True)
            
            # Create standard Knowledge Lake directories
            for dir_name in ["agent-memory"]:
                (kl_path / dir_name).mkdir(parents=True)
            
            yield kl_path

    @pytest.mark.asyncio
    async def test_agent_memory_basic_operations(self, temp_knowledge_lake):
        """Test basic save and load operations for agent memory."""
        # Create knowledge store
        knowledge_store = KnowledgeStore(root=temp_knowledge_lake)
        knowledge_store.initialize()
        
        # Create agent memory manager
        memory_manager = AgentMemoryManager(
            knowledge_root=temp_knowledge_lake / "agent-memory",
            retention_days=90
        )
        
        # Test saving a decision
        await memory_manager.save_decision(
            agent="test-agent",
            campaign="test-campaign-001",
            decision={"action": "BUY", "confidence": 0.85, "reason": "test signal"}
        )
        
        # Test loading the memory
        memories = await memory_manager.load_memory(
            agent="test-agent",
            campaign="test-campaign-001"
        )
        
        assert len(memories) == 1
        assert memories[0]["action"] == "BUY"
        assert memories[0]["confidence"] == 0.85
        
        # Test cross-agent query (should return empty for no matches)
        results = await memory_manager.query_cross_agent("BUY")
        # This might return empty or some results depending on implementation
        
    @pytest.mark.asyncio
    async def test_agent_memory_multiple_decisions(self, temp_knowledge_lake):
        """Test storing multiple decisions for same agent/campaign."""
        knowledge_store = KnowledgeStore(root=temp_knowledge_lake)
        knowledge_store.initialize()
        
        memory_manager = AgentMemoryManager(
            knowledge_root=temp_knowledge_lake / "agent-memory"
        )
        
        # Store multiple decisions
        await memory_manager.save_decision(
            agent="test-agent",
            campaign="test-campaign-001",
            decision={"step": 1, "value": 10}
        )
        
        await memory_manager.save_decision(
            agent="test-agent",
            campaign="test-campaign-001", 
            decision={"step": 2, "value": 20}
        )
        
        # Load all memories
        memories = await memory_manager.load_memory(
            agent="test-agent",
            campaign="test-campaign-001"
        )
        
        assert len(memories) == 2
        # Should be ordered by time (most recent first typically)
        values = [m["value"] for m in memories]
        assert 10 in values
        assert 20 in values
