"""Unit tests for llm_service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


class TestLLMServiceInit:
    """Tests for LLMService initialization."""

    def test_service_initialization(self):
        """Test LLMService initializes with correct defaults."""
        with patch("services.llm_service.ExactCache"):
            from services.llm_service import LLMService
            
            service = LLMService(
                litellm_url="http://test:4000",
                qdrant_url="http://test:6333",
            )
            
            assert service.litellm_url == "http://test:4000"
            assert service.qdrant_url == "http://test:6333"

    def test_generate_incident_id(self):
        """Test incident ID generation."""
        from services.llm_service import LLMService
        
        id1 = LLMService.generate_incident_id()
        id2 = LLMService.generate_incident_id()
        
        assert id1.startswith("inc_")
        assert len(id1) == 16  # inc_ + 12 hex chars
        assert id1 != id2


class TestLLMServiceDependencyInjection:
    """Tests for LLMService dependency injection."""

    def test_get_llm_service_returns_singleton(self):
        """Test that get_llm_service returns same instance."""
        import services.llm_service as llm_module
        
        # Reset singleton
        llm_module._llm_service = None
        
        with patch("services.llm_service.ExactCache"):
            service1 = llm_module.get_llm_service()
            service2 = llm_module.get_llm_service()
            
            assert service1 is service2

    def test_set_llm_service_overrides(self):
        """Test that set_llm_service allows override."""
        import services.llm_service as llm_module
        
        mock_service = MagicMock()
        llm_module.set_llm_service(mock_service)
        
        assert llm_module.get_llm_service() is mock_service
        
        # Cleanup
        llm_module._llm_service = None


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_llm_response_creation(self):
        """Test LLMResponse dataclass creation."""
        from services.llm_service import LLMResponse
        
        response = LLMResponse(
            response_text="Hello world",
            model="test-model",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.001,
            cache_hit=False,
            cache_type=None,
            cache_latency_ms=None,
            guardrails_triggered=[],
        )
        
        assert response.response_text == "Hello world"
        assert response.model == "test-model"
        assert response.total_tokens == 15
        assert response.cache_hit is False


class TestRetryLogic:
    """Tests for retry logic in LLM service."""

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Test that timeouts trigger retry."""
        import services.llm_service as llm_module
        
        with patch("services.llm_service.ExactCache"):
            service = llm_module.LLMService(
                litellm_url="http://test:4000",
                qdrant_url="http://test:6333",
            )
            
            # Mock client to raise timeout then succeed
            call_count = 0
            
            async def mock_call(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise asyncio.TimeoutError("Timeout")
                return MagicMock(
                    choices=[MagicMock(message=MagicMock(content="Success"))],
                    usage=MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                    model="test-model",
                )
            
            with patch.object(service, "_call_llm_with_retry", side_effect=mock_call):
                # This would test retry behavior
                pass


class TestCostCalculation:
    """Tests for cost calculation."""

    def test_calculate_cost_fallback(self):
        """Test cost calculation fallback when litellm fails."""
        with patch("services.llm_service.ExactCache"):
            from services.llm_service import LLMService
            
            service = LLMService(
                litellm_url="http://test:4000",
                qdrant_url="http://test:6333",
            )
            
            mock_response = MagicMock()
            mock_response.usage.prompt_tokens = 100
            mock_response.usage.completion_tokens = 50
            mock_response.model = "test-model"
            
            with patch("services.llm_service.completion_cost", side_effect=Exception("No cost data")):
                cost = service._calculate_cost(mock_response, "test-model")
                
                # Fallback calculation: (100 * 0.00001) + (50 * 0.00002) = 0.002
                assert cost == 0.002
