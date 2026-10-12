import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import eval.build_dataset as bd


class Args:
    def __init__(self):
        self.chunks = "corpus/chunks.jsonl"
        self.cand = "eval/datasets/candidates.jsonl"
        self.v1 = "eval/datasets/v1.jsonl"
        self.rej = "eval/datasets/rejected.jsonl"
        self.categoria = None


def argparse_simple():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default=Args().chunks)
    parser.add_argument("--cand", default=Args().cand)
    parser.add_argument("--v1", default=Args().v1)
    parser.add_argument("--rej", default=Args().rej)
    parser.add_argument("--categoria", choices=bd.CATEGORIAS)
    return parser.parse_args([])


def test_openai_compat_normal_response():
    """Uma resposta normal devolve o JSON."""
    response_payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({"pergunta": "Qual o prazo?", "resposta_ouro": "30 dias"})
                }
            }
        ]
    }
    raw_bytes = json.dumps(response_payload).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = raw_bytes
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch.dict(os.environ, {"ANCHOR_GEN_PROVIDER": "openai", "ANCHOR_GEN_BASE_URL": "http://localhost:11434/v1", "ANCHOR_GEN_MODEL": "qwen2.5:7b"}):
        with patch("eval.build_dataset.urlopen", return_value=mock_resp) as mock_urlopen:
            resultado = bd.llm_json("prompt de teste")

            assert resultado == {"pergunta": "Qual o prazo?", "resposta_ouro": "30 dias"}
            assert mock_urlopen.call_count == 1
            req = mock_urlopen.call_args[0][0]
            assert req.full_url == "http://localhost:11434/v1/chat/completions"
            body = json.loads(req.data.decode("utf-8"))
            assert body["model"] == bd.MODEL
            assert body["response_format"] == {"type": "json_object"}


def test_openai_compat_retry_429_then_success():
    """Um 429 seguido de sucesso funciona."""
    response_payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({"pergunta": "O que é Pix?", "resposta_ouro": "Pagamento instantâneo"})
                }
            }
        ]
    }
    raw_bytes = json.dumps(response_payload).encode("utf-8")

    mock_resp_success = MagicMock()
    mock_resp_success.read.return_value = raw_bytes
    mock_resp_success.__enter__.return_value = mock_resp_success
    mock_resp_success.__exit__.return_value = None

    # HTTPError(url, code, msg, hdrs, fp)
    err_429 = HTTPError("http://localhost:11434/v1/chat/completions", 429, "Too Many Requests", {"Retry-After": "0.1"}, io.BytesIO(b"rate limit"))

    with patch.dict(os.environ, {"ANCHOR_GEN_PROVIDER": "openai"}):
        with patch("eval.build_dataset.urlopen", side_effect=[err_429, mock_resp_success]) as mock_urlopen:
            with patch("eval.build_dataset.time.sleep") as mock_sleep:
                resultado = bd.llm_json("prompt retry")
                assert resultado == {"pergunta": "O que é Pix?", "resposta_ouro": "Pagamento instantâneo"}
                assert mock_urlopen.call_count == 2
                mock_sleep.assert_called_once_with(0.1)


def test_openai_compat_does_not_import_anthropic():
    """PROVIDER='openai' não importa anthropic."""
    response_payload = {
        "choices": [
            {
                "message": {
                    "content": '{"pergunta": "P?", "resposta_ouro": "R"}'
                }
            }
        ]
    }
    raw_bytes = json.dumps(response_payload).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = raw_bytes
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    # Garante que anthropic não está em sys.modules durante o teste
    with patch.dict(os.environ, {"ANCHOR_GEN_PROVIDER": "openai"}):
        with patch.dict(sys.modules):
            sys.modules.pop("anthropic", None)
            with patch("eval.build_dataset.urlopen", return_value=mock_resp):
                bd.llm_json("teste sem anthropic")
                assert "anthropic" not in sys.modules


def test_cmd_review_require_tty(monkeypatch):
    """cmd_review aborta quando stdin não é terminal interativo."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    args = argparse_simple()
    with pytest.raises(SystemExit) as exc_info:
        bd.cmd_review(args)
    assert exc_info.value.code == "o review exige uma pessoa no terminal"
