"""Contract tests for EvaluatorProvider ABC."""

from abc import ABC
from typing import List
import pytest

from anchor_rag.evaluation.evaluator import (
    EvaluatorProvider,
    OpenAIEvaluatorProvider,
    OllamaEvaluatorProvider,
    AnthropicEvaluatorProvider,
    create_evaluator_provider,
)


class TestEvaluatorProviderContract:
    """Testes de contrato para garantir que todos os providers implementam a interface."""

    def test_evaluator_provider_is_abc(self):
        """EvaluatorProvider deve ser uma ABC."""
        assert issubclass(EvaluatorProvider, ABC)

    def test_evaluator_provider_has_required_methods(self):
        """Deve ter todos os métodos abstratos necessários."""
        required_methods = [
            "eval_faithfulness",
            "eval_answer_relevancy",
            "eval_context_precision",
            "eval_context_recall",
            "health_check",
        ]
        for method in required_methods:
            assert hasattr(EvaluatorProvider, method)
            assert getattr(EvaluatorProvider, method).__isabstractmethod__

    def test_openai_provider_inherits_abc(self):
        """OpenAIEvaluatorProvider deve herdar de EvaluatorProvider."""
        assert issubclass(OpenAIEvaluatorProvider, EvaluatorProvider)

    def test_ollama_provider_inherits_abc(self):
        """OllamaEvaluatorProvider deve herdar de EvaluatorProvider."""
        assert issubclass(OllamaEvaluatorProvider, EvaluatorProvider)

    def test_anthropic_provider_inherits_abc(self):
        """AnthropicEvaluatorProvider deve herdar de EvaluatorProvider."""
        assert issubclass(AnthropicEvaluatorProvider, EvaluatorProvider)


class TestEvaluatorProviderSignatures:
    """Testes de assinatura dos métodos."""

    def test_eval_faithfulness_signature(self):
        import inspect
        sig = inspect.signature(EvaluatorProvider.eval_faithfulness)
        params = list(sig.parameters.keys())
        assert params == ["self", "query", "context", "answer"]
        assert sig.return_annotation == float

    def test_eval_answer_relevancy_signature(self):
        import inspect
        sig = inspect.signature(EvaluatorProvider.eval_answer_relevancy)
        params = list(sig.parameters.keys())
        assert params == ["self", "query", "answer"]
        assert sig.return_annotation == float

    def test_eval_context_precision_signature(self):
        import inspect
        sig = inspect.signature(EvaluatorProvider.eval_context_precision)
        params = list(sig.parameters.keys())
        assert params == ["self", "query", "context", "answer"]
        assert sig.return_annotation == float

    def test_eval_context_recall_signature(self):
        import inspect
        sig = inspect.signature(EvaluatorProvider.eval_context_recall)
        params = list(sig.parameters.keys())
        assert params == ["self", "query", "context", "answer"]
        assert sig.return_annotation == float

    def test_health_check_signature(self):
        import inspect
        sig = inspect.signature(EvaluatorProvider.health_check)
        params = list(sig.parameters.keys())
        assert params == ["self"]
        assert sig.return_annotation == bool


class TestFactoryFunction:
    """Testes da factory create_evaluator_provider."""

    def test_factory_returns_openai(self, monkeypatch):
        """Factory deve retornar OpenAIEvaluatorProvider para 'openai'."""
        provider = create_evaluator_provider("openai", model="gpt-4o-mini")
        assert isinstance(provider, OpenAIEvaluatorProvider)

    def test_factory_returns_ollama(self, monkeypatch):
        """Factory deve retornar OllamaEvaluatorProvider para 'ollama'."""
        provider = create_evaluator_provider("ollama", model="llama3.1:8b")
        assert isinstance(provider, OllamaEvaluatorProvider)

    def test_factory_returns_anthropic(self, monkeypatch):
        """Factory deve retornar AnthropicEvaluatorProvider para 'anthropic'."""
        provider = create_evaluator_provider("anthropic", model="claude-3-haiku")
        assert isinstance(provider, AnthropicEvaluatorProvider)

    def test_factory_raises_for_unknown(self):
        """Factory deve lançar ValueError para provider desconhecido."""
        with pytest.raises(ValueError, match="Unknown evaluator provider"):
            create_evaluator_provider("unknown")

    def test_factory_case_insensitive(self, monkeypatch):
        """Factory deve ser case-insensitive."""
        provider = create_evaluator_provider("OPENAI", model="gpt-4o-mini")
        assert isinstance(provider, OpenAIEvaluatorProvider)


class TestEvaluatorProviderBasicBehavior:
    """Testes de comportamento básico (sem chamar LLM real)."""

    @pytest.mark.asyncio
    async def test_openai_provider_instantiation(self):
        """OpenAIEvaluatorProvider deve instanciar sem erro."""
        provider = OpenAIEvaluatorProvider(model="gpt-4o-mini", api_key="test-key")
        assert provider.provider_name == "openai"
        assert provider.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_ollama_provider_instantiation(self):
        """OllamaEvaluatorProvider deve instanciar sem erro."""
        provider = OllamaEvaluatorProvider(model="llama3.1:8b")
        assert provider.provider_name == "ollama"
        assert provider.model == "llama3.1:8b"

    @pytest.mark.asyncio
    async def test_anthropic_provider_instantiation(self):
        """AnthropicEvaluatorProvider deve instanciar sem erro."""
        provider = AnthropicEvaluatorProvider(model="claude-3-haiku", api_key="test-key")
        assert provider.provider_name == "anthropic"
        assert provider.model == "claude-3-haiku"

    @pytest.mark.asyncio
    async def test_health_check_returns_bool(self):
        """health_check deve retornar bool (pode ser True/False dependendo de config)."""
        provider = OpenAIEvaluatorProvider(model="gpt-4o-mini", api_key="test-key")
        result = await provider.health_check()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_eval_methods_return_float(self):
        """Todos os métodos de eval devem retornar float (mock ou real)."""
        provider = OpenAIEvaluatorProvider(model="gpt-4o-mini", api_key="test-key")

        # Mock das chamadas internas se necessário
        # Aqui testamos apenas que o método existe e é chamável
        assert callable(provider.eval_faithfulness)
        assert callable(provider.eval_answer_relevancy)
        assert callable(provider.eval_context_precision)
        assert callable(provider.eval_context_recall)