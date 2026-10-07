"""LLM-as-Judge Evaluator Providers - Strategy Pattern for RAG evaluation."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class EvaluatorProvider(ABC):
    """ABC para provedores de avaliação LLM-as-judge.

    Implementa as 4 métricas RAGAS-like:
    - faithfulness: a resposta é suportada pelo contexto?
    - answer_relevancy: a resposta responde à pergunta?
    - context_precision: os trechos relevantes estão no topo?
    - context_recall: todo o necessário para responder está no contexto?
    """

    def __init__(self, model: str, **kwargs):
        self.model = model
        self.kwargs = kwargs

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nome do provedor (openai, ollama, anthropic)."""
        pass

    @abstractmethod
    async def eval_faithfulness(self, query: str, context: List[str], answer: str) -> float:
        """Avalia fidelidade: resposta suportada pelo contexto?"""
        pass

    @abstractmethod
    async def eval_answer_relevancy(self, query: str, answer: str) -> float:
        """Avalia relevância: resposta responde à pergunta?"""
        pass

    @abstractmethod
    async def eval_context_precision(self, query: str, context: List[str], answer: str) -> float:
        """Avalia precisão do contexto: trechos relevantes no topo?"""
        pass

    @abstractmethod
    async def eval_context_recall(self, query: str, context: List[str], answer: str) -> float:
        """Avalia recall do contexto: toda info necessária presente?"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica se o provedor está disponível."""
        pass

    async def evaluate_all(
        self,
        query: str,
        context: List[str],
        answer: str,
    ) -> Dict[str, float]:
        """Avalia todas as 4 métricas em paralelo."""
        results = await asyncio.gather(
            self.eval_faithfulness(query, context, answer),
            self.eval_answer_relevancy(query, answer),
            self.eval_context_precision(query, context, answer),
            self.eval_context_recall(query, context, answer),
            return_exceptions=True,
        )

        metrics = {
            "faithfulness": 0.0,
            "answer_relevancy": 0.0,
            "context_precision": 0.0,
            "context_recall": 0.0,
        }

        keys = list(metrics.keys())
        for i, (key, result) in enumerate(zip(keys, results)):
            if isinstance(result, Exception):
                logger.error(f"Erro em {key}: {result}")
                metrics[key] = 0.0
            else:
                metrics[key] = max(0.0, min(1.0, float(result)))

        return metrics

    def _load_judge_prompt(self, metric: str) -> str:
        """Carrega prompt de few-shot para a métrica."""
        prompt_path = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "judge_prompts" / f"{metric}.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        # Fallback prompt mínimo
        return self._default_prompt(metric)

    def _default_prompt(self, metric: str) -> str:
        """Prompt padrão caso arquivo não exista."""
        prompts = {
            "faithfulness": (
                "Avalie se a resposta é fiel ao contexto. "
                "SCORE: <0.0-1.0> REASONING: <texto>"
            ),
            "answer_relevancy": (
                "Avalie se a resposta responde à pergunta. "
                "SCORE: <0.0-1.0> REASONING: <texto>"
            ),
            "context_precision": (
                "Avalie se trechos relevantes estão no topo. "
                "SCORE: <0.0-1.0> REASONING: <texto>"
            ),
            "context_recall": (
                "Avalie se toda info necessária está no contexto. "
                "SCORE: <0.0-1.0> REASONING: <texto>"
            ),
        }
        return prompts.get(metric, "SCORE: 0.5 REASONING: default")

    def _parse_score(self, response: str) -> float:
        """Extrai score da resposta do judge."""
        import re
        # Procura por SCORE: <numero>
        match = re.search(r"SCORE:\s*([0-9]*\.?[0-9]+)", response, re.IGNORECASE)
        if match:
            score = float(match.group(1))
            return max(0.0, min(1.0, score))
        # Fallback: primeiro número na resposta
        match = re.search(r"([0-9]*\.?[0-9]+)", response)
        if match:
            score = float(match.group(1))
            return max(0.0, min(1.0, score))
        logger.warning(f"Não foi possível extrair score de: {response}")
        return 0.5


class OpenAIEvaluatorProvider(EvaluatorProvider):
    """Provedor de avaliação usando OpenAI API."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: int = 30,
        max_retries: int = 3,
        **kwargs,
    ):
        super().__init__(model, **kwargs)
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = None

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_client(self):
        """Lazy initialization do cliente OpenAI."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def _call_judge(self, prompt: str) -> str:
        """Chama o modelo judge com retry."""
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
        import openai

        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError)),
            reraise=True,
        )
        async def _call():
            client = self._get_client()
            resp = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return resp.choices[0].message.content or ""

        return await _call()

    async def eval_faithfulness(self, query: str, context: List[str], answer: str) -> float:
        prompt = self._load_judge_prompt("faithfulness")
        context_str = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context))
        full_prompt = f"{prompt}\n\nPergunta: {query}\n\nContexto:\n{context_str}\n\nResposta: {answer}\n\nSCORE:"
        response = await self._call_judge(full_prompt)
        return self._parse_score(response)

    async def eval_answer_relevancy(self, query: str, answer: str) -> float:
        prompt = self._load_judge_prompt("answer_relevancy")
        full_prompt = f"{prompt}\n\nPergunta: {query}\n\nResposta: {answer}\n\nSCORE:"
        response = await self._call_judge(full_prompt)
        return self._parse_score(response)

    async def eval_context_precision(self, query: str, context: List[str], answer: str) -> float:
        prompt = self._load_judge_prompt("context_precision")
        context_str = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context))
        full_prompt = f"{prompt}\n\nPergunta: {query}\n\nContextos:\n{context_str}\n\nResposta: {answer}\n\nSCORE:"
        response = await self._call_judge(full_prompt)
        return self._parse_score(response)

    async def eval_context_recall(self, query: str, context: List[str], answer: str) -> float:
        prompt = self._load_judge_prompt("context_recall")
        context_str = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context))
        full_prompt = f"{prompt}\n\nPergunta: {query}\n\nContextos:\n{context_str}\n\nResposta: {answer}\n\nSCORE:"
        response = await self._call_judge(full_prompt)
        return self._parse_score(response)

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            await client.models.list()
            return True
        except Exception as e:
            logger.warning(f"OpenAI health check falhou: {e}")
            return False


class OllamaEvaluatorProvider(EvaluatorProvider):
    """Provedor de avaliação usando Ollama local."""

    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,
        timeout: int = 60,
        **kwargs,
    ):
        super().__init__(model, **kwargs)
        self.base_url = base_url
        self.temperature = temperature
        self.timeout = timeout
        self._client = None

    @property
    def provider_name(self) -> str:
        return "ollama"

    def _get_client(self):
        """Lazy initialization do cliente Ollama."""
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self._client

    async def _call_judge(self, prompt: str) -> str:
        """Chama Ollama generate endpoint."""
        import httpx
        client = self._get_client()
        resp = await client.post(
            "/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "temperature": self.temperature,
                "stream": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")

    async def eval_faithfulness(self, query: str, context: List[str], answer: str) -> float:
        prompt = self._load_judge_prompt("faithfulness")
        context_str = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context))
        full_prompt = f"{prompt}\n\nPergunta: {query}\n\nContexto:\n{context_str}\n\nResposta: {answer}\n\nSCORE:"
        response = await self._call_judge(full_prompt)
        return self._parse_score(response)

    async def eval_answer_relevancy(self, query: str, answer: str) -> float:
        prompt = self._load_judge_prompt("answer_relevancy")
        full_prompt = f"{prompt}\n\nPergunta: {query}\n\nResposta: {answer}\n\nSCORE:"
        response = await self._call_judge(full_prompt)
        return self._parse_score(response)

    async def eval_context_precision(self, query: str, context: List[str], answer: str) -> float:
        prompt = self._load_judge_prompt("context_precision")
        context_str = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context))
        full_prompt = f"{prompt}\n\nPergunta: {query}\n\nContextos:\n{context_str}\n\nResposta: {answer}\n\nSCORE:"
        response = await self._call_judge(full_prompt)
        return self._parse_score(response)

    async def eval_context_recall(self, query: str, context: List[str], answer: str) -> float:
        prompt = self._load_judge_prompt("context_recall")
        context_str = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context))
        full_prompt = f"{prompt}\n\nPergunta: {query}\n\nContextos:\n{context_str}\n\nResposta: {answer}\n\nSCORE:"
        response = await self._call_judge(full_prompt)
        return self._parse_score(response)

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            resp = await client.get("/api/tags")
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"Ollama health check falhou: {e}")
            return False


class AnthropicEvaluatorProvider(EvaluatorProvider):
    """Provedor de avaliação usando Anthropic API."""

    def __init__(
        self,
        model: str = "claude-3-haiku-20240307",
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: int = 30,
        max_retries: int = 3,
        **kwargs,
    ):
        super().__init__(model, **kwargs)
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = None

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _get_client(self):
        """Lazy initialization do cliente Anthropic."""
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(
                api_key=self.api_key,
                timeout=self.timeout,
            )
        return self._client

    async def _call_judge(self, prompt: str) -> str:
        """Chama o modelo judge Anthropic com retry."""
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
        import anthropic

        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APITimeoutError, anthropic.APIConnectionError)),
            reraise=True,
        )
        async def _call():
            client = self._get_client()
            resp = await client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text if resp.content else ""

        return await _call()

    async def eval_faithfulness(self, query: str, context: List[str], answer: str) -> float:
        prompt = self._load_judge_prompt("faithfulness")
        context_str = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context))
        full_prompt = f"{prompt}\n\nPergunta: {query}\n\nContexto:\n{context_str}\n\nResposta: {answer}\n\nSCORE:"
        response = await self._call_judge(full_prompt)
        return self._parse_score(response)

    async def eval_answer_relevancy(self, query: str, answer: str) -> float:
        prompt = self._load_judge_prompt("answer_relevancy")
        full_prompt = f"{prompt}\n\nPergunta: {query}\n\nResposta: {answer}\n\nSCORE:"
        response = await self._call_judge(full_prompt)
        return self._parse_score(response)

    async def eval_context_precision(self, query: str, context: List[str], answer: str) -> float:
        prompt = self._load_judge_prompt("context_precision")
        context_str = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context))
        full_prompt = f"{prompt}\n\nPergunta: {query}\n\nContextos:\n{context_str}\n\nResposta: {answer}\n\nSCORE:"
        response = await self._call_judge(full_prompt)
        return self._parse_score(response)

    async def eval_context_recall(self, query: str, context: List[str], answer: str) -> float:
        prompt = self._load_judge_prompt("context_recall")
        context_str = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context))
        full_prompt = f"{prompt}\n\nPergunta: {query}\n\nContextos:\n{context_str}\n\nResposta: {answer}\n\nSCORE:"
        response = await self._call_judge(full_prompt)
        return self._parse_score(response)

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            await client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception as e:
            logger.warning(f"Anthropic health check falhou: {e}")
            return False


# Registry
_PROVIDER_REGISTRY: Dict[str, type[EvaluatorProvider]] = {
    "openai": OpenAIEvaluatorProvider,
    "ollama": OllamaEvaluatorProvider,
    "anthropic": AnthropicEvaluatorProvider,
}


def create_evaluator_provider(provider: str, **kwargs) -> EvaluatorProvider:
    """Factory para criar provedor de avaliação.

    Args:
        provider: Nome do provedor ('openai', 'ollama', 'anthropic')
        **kwargs: Argumentos passados para o construtor do provedor

    Returns:
        Instância de EvaluatorProvider

    Raises:
        ValueError: Se provedor não for reconhecido
    """
    provider_lower = provider.lower().strip()
    if provider_lower not in _PROVIDER_REGISTRY:
        available = ", ".join(_PROVIDER_REGISTRY.keys())
        raise ValueError(f"Unknown evaluator provider: {provider}. Available: {available}")

    provider_class = _PROVIDER_REGISTRY[provider_lower]
    return provider_class(**kwargs)


def register_evaluator_provider(name: str, provider_class: type[EvaluatorProvider]) -> None:
    """Registra um novo provedor customizado."""
    _PROVIDER_REGISTRY[name.lower()] = provider_class


def list_evaluator_providers() -> List[str]:
    """Lista provedores disponíveis."""
    return list(_PROVIDER_REGISTRY.keys())