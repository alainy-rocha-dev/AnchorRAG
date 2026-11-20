"""Verificador determinístico de citações (variante C) e o laço de reparo no sintetizador."""

import asyncio
from unittest.mock import MagicMock
from uuid import uuid4

from anchor_rag.domain.models import Chunk
from anchor_rag.synthesis.llm import LLMProvider, LLMResponse
from anchor_rag.synthesis.prompt import RECUSA_PADRAO
from anchor_rag.synthesis.synthesizer import RAGSynthesizer, SynthesizerConfig
from anchor_rag.synthesis.verifier import (
    _por_extenso,
    artigo_do_chunk_id,
    mensagem_de_reparo,
    verificar,
)

T1 = ("Art. 67. As instituições referidas no art. 1º devem manter à disposição do Banco Central "
      "do Brasil e conservar pelo período mínimo de dez anos os registros.")
T2 = ("Art. 68. As instituições devem manter à disposição do Banco Central do Brasil, pelo prazo "
      "mínimo de 5 (cinco) anos, os documentos. A alíquota é de 2,5% ao ano.")
TRECHOS = [T1, T2]
ARTIGOS = ["67", "68"]


def tipos(v):
    return sorted(p.tipo for p in v.problemas)


# ------------------------------------------------------------------ verificar()
def test_resposta_correta_passa():
    v = verificar("Os registros são guardados por dez anos [1].", TRECHOS, ARTIGOS)
    assert v.ok and v.citados == [1]


def test_recusa_nao_precisa_de_citacao():
    v = verificar(RECUSA_PADRAO, TRECHOS, ARTIGOS)
    assert v.ok and v.recusa


def test_sem_citacao():
    assert tipos(verificar("Os registros são guardados por dez anos.", TRECHOS)) == ["sem_citacao"]


def test_citacao_para_trecho_que_nao_existe():
    v = verificar("Prazo de dez anos [3].", TRECHOS, ARTIGOS)
    assert tipos(v) == ["citacao_inexistente"]


def test_formatos_de_citacao_multipla():
    assert verificar("Prazos de 10 e 5 anos [1, 2].", TRECHOS, ARTIGOS).citados == [1, 2]
    assert verificar("Prazos de 10 e 5 anos [1 e 2].", TRECHOS, ARTIGOS).citados == [1, 2]
    assert verificar("Prazos de 10 e 5 anos [1-2].", TRECHOS, ARTIGOS).citados == [1, 2]


def test_artigo_que_nao_esta_no_trecho_citado():
    # o art. 68 existe, mas no trecho [2]; a resposta cita [1]
    v = verificar("Segundo o art. 68, o prazo é de dez anos [1].", TRECHOS, ARTIGOS)
    assert tipos(v) == ["artigo_nao_citado"]


def test_artigo_mencionado_dentro_do_trecho_passa():
    # "art. 1º" aparece no texto do trecho [1] como remissão
    assert verificar("Vale para as instituições do art. 1º [1].", TRECHOS, ARTIGOS).ok


def test_artigos_em_lista():
    v = verificar("Conforme os artigos 67 e 19, o prazo é de dez anos [1].", TRECHOS, ARTIGOS)
    assert [str(p) for p in v.problemas] == ["artigo_nao_citado: art. 19 não aparece nos trechos citados"]


def test_numero_inventado():
    v = verificar("O prazo é de 15 anos [1].", TRECHOS, ARTIGOS)
    assert tipos(v) == ["numero_nao_citado"]


def test_numero_por_extenso_no_trecho():
    # o trecho diz "dez anos"; a resposta escreve "10 anos"
    assert verificar("O prazo é de 10 anos [1].", TRECHOS, ARTIGOS).ok


def test_percentual_e_decimal():
    assert verificar("A alíquota é de 2,5% ao ano [2].", TRECHOS, ARTIGOS).ok
    assert tipos(verificar("A alíquota é de 3% ao ano [2].", TRECHOS, ARTIGOS)) == ["numero_nao_citado"]


def test_numero_do_trecho_nao_citado_reprova():
    # 5 anos está no trecho [2], mas a resposta só cita [1]
    assert tipos(verificar("O prazo é de 5 anos [1].", TRECHOS, ARTIGOS)) == ["numero_nao_citado"]


def test_numero_da_pergunta_pode_ser_repetido():
    pergunta = "O prazo mínimo é de 30 anos?"
    resposta = "Não: o prazo não é de 30 anos, e sim de dez anos [1]."
    assert verificar(resposta, TRECHOS, ARTIGOS, pergunta).ok
    assert not verificar(resposta, TRECHOS, ARTIGOS).ok


def test_rotulos_de_norma_e_estrutura_nao_sao_conferidos():
    r = "A Resolução CMN 4.966, no § 2º, inciso III, prevê dez anos [1]."
    assert verificar(r, TRECHOS, ARTIGOS).ok


def test_lista_numerada_nao_conta_como_numero():
    r = "Deve:\n1. manter os registros [1];\n2. conservar por dez anos [1]."
    assert verificar(r, TRECHOS, ARTIGOS).ok


def test_por_extenso():
    assert "dez" in _por_extenso(10)
    assert "cento e oitenta" in _por_extenso(180)
    assert "duas" in _por_extenso(2) and "dois" in _por_extenso(2)
    assert "catorze" in _por_extenso(14)


def test_artigo_do_chunk_id():
    assert artigo_do_chunk_id("res_4557:art54") == "54"
    assert artigo_do_chunk_id("res_bcb_85:art3-p1") == "3"
    assert artigo_do_chunk_id(None) is None


def test_mensagem_de_reparo_lista_os_problemas():
    msg = mensagem_de_reparo(verificar("O prazo é de 15 anos [3].", TRECHOS, ARTIGOS))
    assert "[3]" in msg and RECUSA_PADRAO in msg


# ------------------------------------------------------------------ laço no sintetizador
class RoteiroLLM(LLMProvider):
    """Devolve as respostas na ordem e guarda as mensagens recebidas."""

    def __init__(self, respostas):
        super().__init__(MagicMock())
        self.respostas = list(respostas)
        self.chamadas = []

    async def complete(self, messages, temperature=None, max_tokens=None):
        self.chamadas.append(messages)
        texto = self.respostas[min(len(self.chamadas) - 1, len(self.respostas) - 1)]
        return LLMResponse(content=texto, input_tokens=100, output_tokens=20, model="roteiro")

    async def complete_stream(self, messages, temperature=None, max_tokens=None):
        yield ""

    async def health_check(self):
        return True

    def count_tokens(self, text):
        return len(text.split())


def _chunks():
    return [
        Chunk(id=uuid4(), document_id=uuid4(), content=t, chunk_index=i, page_number=None,
              start_char=0, end_char=len(t), token_count=None, embedding=None,
              metadata={"chunk_id": f"circ_3978:art{a}"})
        for i, (t, a) in enumerate(zip(TRECHOS, ARTIGOS))
    ]


def _sintetizar(llm, verificador=True, voltas_max=2):
    s = RAGSynthesizer(llm, SynthesizerConfig(verificador=verificador, voltas_max=voltas_max))
    return asyncio.run(s.synthesize("Qual o prazo?", _chunks(), [0.9, 0.8]))


def test_laco_corrige_na_segunda_tentativa():
    llm = RoteiroLLM(["O prazo é de 15 anos [1].", "O prazo é de dez anos [1]."])
    r = _sintetizar(llm)
    assert r.answer == "O prazo é de dez anos [1]."
    assert r.metadata["verificador"]["resultado"] == "corrigida"
    assert r.metadata["verificador"]["voltas"] == 1
    assert r.metadata["input_tokens"] == 200  # soma das duas chamadas
    # o re-prompt leva a resposta rejeitada e o problema encontrado
    ultima = llm.chamadas[1]
    assert ultima[-2] == {"role": "assistant", "content": "O prazo é de 15 anos [1]."}
    assert "15" in ultima[-1]["content"]


def test_laco_recusa_depois_das_voltas():
    llm = RoteiroLLM(["O prazo é de 15 anos [1]."])
    r = _sintetizar(llm, voltas_max=2)
    assert r.answer == RECUSA_PADRAO
    assert r.metadata["verificador"]["resultado"] == "recusada"
    assert len(llm.chamadas) == 3  # 1 resposta + 2 reescritas
    assert r.citations == []


def test_resposta_valida_nao_gasta_chamada_extra():
    llm = RoteiroLLM(["O prazo é de dez anos [1]."])
    r = _sintetizar(llm)
    assert r.metadata["verificador"] == {"resultado": "aprovada", "voltas": 0, "problemas": [[]]}
    assert len(llm.chamadas) == 1


def test_sem_verificador_nada_muda():
    llm = RoteiroLLM(["O prazo é de 15 anos [1]."])
    r = _sintetizar(llm, verificador=False)
    assert r.answer == "O prazo é de 15 anos [1]."
    assert "verificador" not in r.metadata
