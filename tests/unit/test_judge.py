"""Juiz LLM: parsing, roteamento por categoria, resumo, concordância e amostragem."""

from unittest.mock import MagicMock

import pytest

from anchor_rag.cli import _familia
from anchor_rag.evaluation.judge import (
    MAX_AFIRMACOES,
    Contexto,
    amostra_afirmacoes,
    amostra_estratificada,
    citacao_confere,
    cohen_kappa,
    concordancia,
    dimensoes_do_item,
    julgar,
    julgar_fidelidade_por_afirmacao,
    julgar_relatorio,
    parse_afirmacoes,
    parse_veredito,
    resumo_juiz,
)
from anchor_rag.synthesis.llm import LLMProvider, LLMResponse


class LLMRoteiro(LLMProvider):
    """Devolve respostas em sequência; registra prompts e temperatura."""

    def __init__(self, respostas):
        super().__init__(MagicMock())
        self.respostas = list(respostas)
        self.chamadas = []

    async def complete(self, messages, temperature=None, max_tokens=None):
        self.chamadas.append({"prompt": messages[-1]["content"], "temperature": temperature})
        texto = self.respostas.pop(0) if self.respostas else '{"veredito": "invalido"}'
        return LLMResponse(content=texto, input_tokens=1, output_tokens=1, model="roteiro")

    async def complete_stream(self, messages, temperature=None, max_tokens=None):
        yield ""

    async def health_check(self):
        return True

    def count_tokens(self, text):
        return 1


@pytest.mark.parametrize("texto,dim,esperado", [
    ('{"veredito": "correta", "justificativa": "ok"}', "exatidao", "correta"),
    ('Claro! Aqui está:\n{"veredito": "Parcial"}\nEspero ter ajudado.', "exatidao", "parcial"),
    ('{"veredito": "não fiel", "afirmacao": "3%"}', "fidelidade", "nao_fiel"),
    ('{"veredito": "nao_fiel"}', "fidelidade", "nao_fiel"),
    ('{"veredito": "corrige"}', "premissa", "corrige"),
])
def test_parse_veredito_valido(texto, dim, esperado):
    assert parse_veredito(texto, dim)["veredito"] == esperado


@pytest.mark.parametrize("texto,dim", [
    ("sem json nenhum", "exatidao"),
    ('{"veredito": "talvez"}', "exatidao"),
    ('{"veredito": "correta"}', "fidelidade"),  # veredito de outra dimensão
    ('{veredito: correta', "exatidao"),
])
def test_parse_veredito_invalido(texto, dim):
    assert parse_veredito(texto, dim) is None


def test_dimensoes_por_categoria():
    base = {"resposta": "x", "recusou": False, "erro": None}
    assert dimensoes_do_item({**base, "subtipo": "respondivel"}) == ("exatidao", "fidelidade")
    assert dimensoes_do_item({**base, "subtipo": "premissa_falsa"}) == ("premissa", "fidelidade")
    assert dimensoes_do_item({**base, "subtipo": "sem_resposta"}) == ("fidelidade",)
    assert dimensoes_do_item({**base, "subtipo": "vazamento"}) == ()
    assert dimensoes_do_item({**base, "subtipo": "respondivel", "recusou": True}) == ()
    assert dimensoes_do_item({**base, "subtipo": "respondivel", "resposta": None}) == ()


@pytest.mark.asyncio
async def test_julgar_tenta_de_novo_e_usa_temperatura_zero():
    llm = LLMRoteiro(["texto sem json", '{"veredito": "incorreta"}'])
    v = await julgar(llm, "exatidao", "p", "r", "ouro", [])
    assert v["veredito"] == "incorreta"
    assert len(llm.chamadas) == 2
    assert all(c["temperature"] == 0.0 for c in llm.chamadas)


@pytest.mark.asyncio
async def test_julgar_marca_invalido_apos_tentativas():
    llm = LLMRoteiro(["lixo", "lixo"])
    v = await julgar(llm, "fidelidade", "p", "r", None, ["t"])
    assert v["veredito"] == "invalido"


@pytest.mark.asyncio
async def test_julgar_relatorio_usa_ouro_e_trechos_certos():
    rel = {"itens": [
        {"id": "a", "subtipo": "respondivel", "pergunta": "Qual o prazo?", "resposta": "60 meses [1]",
         "recusou": False, "erro": None, "recuperados": ["n:art4"]},
        {"id": "b", "subtipo": "sem_resposta", "pergunta": "IOF?", "resposta": "Não encontrei.",
         "recusou": True, "erro": None, "recuperados": ["n:art1"]},
        {"id": "c", "subtipo": "sem_resposta", "pergunta": "IOF?", "resposta": "É 3%.",
         "recusou": False, "erro": None, "recuperados": ["n:art1"]},
    ]}
    ctx = Contexto(ouro_por_id={"a": "sessenta meses"},
                   texto_por_chunk={"n:art4": "Art. 4 após sessenta meses", "n:art1": "Art. 1 escopo"})
    llm = LLMRoteiro(['{"veredito": "correta"}', '{"veredito": "fiel"}', '{"veredito": "nao_fiel", "afirmacao": "3%"}'])

    itens = await julgar_relatorio(llm, rel, ctx)

    assert itens[0]["juiz"] == {"exatidao": {"veredito": "correta"}, "fidelidade": {"veredito": "fiel"}}
    assert "juiz" not in itens[1]  # recusou: nada a julgar
    assert itens[2]["juiz"]["fidelidade"]["veredito"] == "nao_fiel"
    assert "sessenta meses" in llm.chamadas[0]["prompt"]          # ouro no prompt de exatidão
    assert "Art. 4 após sessenta meses" in llm.chamadas[1]["prompt"]  # trecho no de fidelidade
    assert "Art. 1 escopo" in llm.chamadas[2]["prompt"]

    resumo = resumo_juiz(itens)
    assert resumo["respondivel"]["exatidao:correta"] == 1.0
    assert resumo["sem_resposta"]["fidelidade:nao_fiel"] == 1.0
    assert resumo["sem_resposta"]["recusou"] == 1


def test_cohen_kappa():
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == 0.0
    assert cohen_kappa(["a", "a"], ["a", "a"]) is None  # sem variação: indefinido
    # exemplo clássico: po=0.7, pe=0.5 -> 0.4
    j = ["s"] * 5 + ["n"] * 5
    h = ["s"] * 4 + ["n"] + ["s"] * 2 + ["n"] * 3
    assert cohen_kappa(j, h) == pytest.approx(0.4, abs=1e-3)


def test_concordancia_ignora_invalidos():
    pares = [
        {"dimensao": "fidelidade", "juiz": "fiel", "humano": "fiel"},
        {"dimensao": "fidelidade", "juiz": "nao_fiel", "humano": "fiel"},
        {"dimensao": "fidelidade", "juiz": "invalido", "humano": "fiel"},
    ]
    c = concordancia(pares)
    assert c["fidelidade"]["n"] == 2
    assert c["fidelidade"]["acordo"] == 0.5


def test_amostra_estratificada_traz_as_duas_classes():
    itens = [{"id": str(i), "juiz": {"fidelidade": {"veredito": "fiel"}}} for i in range(20)]
    itens += [{"id": f"x{i}", "juiz": {"fidelidade": {"veredito": "nao_fiel"}}} for i in range(3)]
    am = amostra_estratificada(itens, {"fidelidade": 6}, seed=1)
    vs = [it["juiz"]["fidelidade"]["veredito"] for it, _ in am]
    assert len(am) == 6
    assert vs.count("nao_fiel") == 3 and vs.count("fiel") == 3
    assert amostra_estratificada(itens, {"fidelidade": 6}, seed=1) == am  # reprodutível


@pytest.mark.parametrize("modelo,familia", [
    ("ollama:qwen2.5:7b", "qwen"),
    ("qwen2.5:7b", "qwen"),
    ("llama3.1:8b", "llama"),
    ("openai:gpt-4o-mini", "gpt"),
])
def test_familia(modelo, familia):
    assert _familia(modelo) == familia


@pytest.mark.asyncio
async def test_ollama_respeita_temperatura_zero(monkeypatch):
    from anchor_rag.synthesis.llm import LLMConfig
    from anchor_rag.synthesis.ollama_llm import OllamaLLMProvider

    p = OllamaLLMProvider(LLMConfig(provider="ollama", model="m", temperature=0.7))
    enviado = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "ok"}, "model": "m"}

    async def post(url, json):
        enviado.update(json)
        return Resp()

    monkeypatch.setattr(p._client, "post", post)
    await p.complete([{"role": "user", "content": "x"}], temperature=0.0)
    assert enviado["options"]["temperature"] == 0.0  # antes: 0.0 virava 0.7 (falsy)


# --------------------------------------------------------------------------- fidelidade por afirmação

@pytest.mark.parametrize("texto,esperado", [
    ('{"afirmacoes": ["O prazo é de 60 meses.", "Cabe à diretoria."]}', ["O prazo é de 60 meses.", "Cabe à diretoria."]),
    ('Aqui:\n{"afirmacoes": []}', []),
    ('{"afirmacoes": ["  ", "x"]}', ["x"]),
    ('{"lista": ["x"]}', None),
    ("sem json", None),
])
def test_parse_afirmacoes(texto, esperado):
    assert parse_afirmacoes(texto) == esperado


def test_parse_afirmacoes_corta_no_maximo():
    lista = [f"a{i}" for i in range(MAX_AFIRMACOES + 5)]
    assert len(parse_afirmacoes('{"afirmacoes": %s}' % str(lista).replace("'", '"'))) == MAX_AFIRMACOES


@pytest.mark.parametrize("texto,esperado", [
    ('{"veredito": "apoiada", "trecho": 2}', "apoiada"),
    ('{"veredito": "não apoiada"}', "nao_apoiada"),
    ('{"veredito": "nao-apoiada"}', "nao_apoiada"),
])
def test_parse_veredito_afirmacao(texto, esperado):
    assert parse_veredito(texto, "afirmacao")["veredito"] == esperado


@pytest.mark.asyncio
async def test_fidelidade_por_afirmacao_marca_nao_fiel_e_aponta_a_afirmacao():
    llm = LLMRoteiro([
        '{"afirmacoes": ["O prazo é de 60 meses.", "A multa é de 3%."]}',
        '{"veredito": "apoiada", "trecho": 1, "citacao": "o novo pedido só cabe após sessenta meses"}',
        '{"veredito": "nao_apoiada", "trecho": null}',
    ])
    v = await julgar_fidelidade_por_afirmacao(llm, "Prazo de 60 meses [1]; multa de 3%.",
                                              ["Art. 4 O novo pedido só cabe após sessenta meses da exclusão."])
    assert v["veredito"] == "nao_fiel"
    assert v["afirmacao"] == "A multa é de 3%."
    assert [a["veredito"] for a in v["afirmacoes"]] == ["apoiada", "nao_apoiada"]
    assert v["afirmacoes"][0]["trecho"] == 1
    # cada afirmação é julgada com os trechos no prompt, e só ela
    assert "Art. 4 O novo pedido" in llm.chamadas[1]["prompt"]
    assert "A multa é de 3%." in llm.chamadas[2]["prompt"] and "60 meses" not in llm.chamadas[2]["prompt"].split("AFIRMAÇÃO:")[1]
    assert all(c["temperature"] == 0.0 for c in llm.chamadas)


@pytest.mark.asyncio
async def test_fidelidade_por_afirmacao_sem_afirmacoes_e_fiel():
    llm = LLMRoteiro(['{"afirmacoes": []}'])
    v = await julgar_fidelidade_por_afirmacao(llm, "Não encontrei essa informação.", ["t"])
    assert v["veredito"] == "fiel" and v["afirmacoes"] == []
    assert len(llm.chamadas) == 1


@pytest.mark.asyncio
async def test_fidelidade_por_afirmacao_invalida_se_extracao_falha():
    llm = LLMRoteiro(["lixo", "lixo"])
    v = await julgar_fidelidade_por_afirmacao(llm, "r", ["t"])
    assert v["veredito"] == "invalido" and v["etapa"] == "extracao"


@pytest.mark.asyncio
async def test_fidelidade_por_afirmacao_invalida_se_afirmacao_fica_sem_veredito():
    llm = LLMRoteiro(['{"afirmacoes": ["a", "b"]}',
                      '{"veredito": "apoiada", "trecho": 1, "citacao": "a política deve ser revisada anualmente"}',
                      "lixo", "lixo"])
    v = await julgar_fidelidade_por_afirmacao(llm, "r", ["Art. 2 A política deve ser revisada anualmente."])
    assert v["veredito"] == "invalido"  # não dá para dizer que é fiel com uma afirmação sem julgamento
    assert [a["veredito"] for a in v["afirmacoes"]] == ["apoiada", "invalido"]


@pytest.mark.asyncio
async def test_julgar_relatorio_no_modo_afirmacoes():
    rel = {"itens": [
        {"id": "c", "subtipo": "sem_resposta", "pergunta": "IOF?", "resposta": "É 3%.",
         "recusou": False, "erro": None, "recuperados": ["n:art1"]},
    ]}
    ctx = Contexto(ouro_por_id={}, texto_por_chunk={"n:art1": "Art. 1 escopo"})
    llm = LLMRoteiro(['{"afirmacoes": ["O IOF é 3%."]}', '{"veredito": "nao_apoiada"}'])
    itens = await julgar_relatorio(llm, rel, ctx, fidelidade="afirmacoes")
    f = itens[0]["juiz"]["fidelidade"]
    assert f["veredito"] == "nao_fiel" and f["afirmacoes"][0]["afirmacao"] == "O IOF é 3%."
    resumo = resumo_juiz(itens)
    assert resumo["sem_resposta"]["afirmacoes_n"] == 1
    assert resumo["sem_resposta"]["afirmacao:nao_apoiada"] == 1.0

    with pytest.raises(ValueError):
        await julgar_relatorio(llm, rel, ctx, fidelidade="outro")


def _item_com_afirmacoes(id, vereditos):
    return {"id": id, "juiz": {"fidelidade": {"veredito": "x", "afirmacoes": [
        {"afirmacao": f"{id}-{k}", "veredito": v} for k, v in enumerate(vereditos)]}}}


def test_amostra_afirmacoes_equilibra_e_agrupa_por_item():
    itens = [_item_com_afirmacoes(f"i{n}", ["apoiada"] * 4) for n in range(10)]
    itens.append(_item_com_afirmacoes("ruim", ["nao_apoiada", "apoiada", "nao_apoiada", "invalido"]))
    am = amostra_afirmacoes(itens, 6, seed=3)

    vs = [it["juiz"]["fidelidade"]["afirmacoes"][k]["veredito"] for it, k in am]
    assert len(am) == 6
    assert vs.count("nao_apoiada") == 2  # todas as que existem; o resto completa com apoiada
    assert "invalido" not in vs
    # agrupada: cada item aparece num bloco contínuo
    ids = [it["id"] for it, _ in am]
    blocos = [i for n, i in enumerate(ids) if n == 0 or ids[n - 1] != i]
    assert len(blocos) == len(set(ids))
    assert amostra_afirmacoes(itens, 6, seed=3) == am  # reprodutível



@pytest.mark.parametrize("citacao,esperado", [
    ("O escopo da atividade de auditoria interna deve considerar todas as funções", True),
    ("o escopo da atividade de AUDITORIA interna deve considerar, todas as funcoes", True),  # caixa, acento, pontuação
    ("O escopo da atividade de auditoria interna (...) todas as funções da instituição", True),  # cópia com reticências
    ("O escopo da atividade de auditoria interna deve considerar todas as áreas da instituição", False),  # trocou palavra
    ("A auditoria interna pode avaliar suas próprias atividades recentes", False),  # inventada
    ("auditoria interna", False),  # curta demais para provar algo
    ("", False),
])
def test_citacao_confere(citacao, esperado):
    trecho = "Art. 11. O escopo da atividade de auditoria interna deve considerar todas as funções da instituição, incluindo as terceirizadas."
    assert citacao_confere(citacao, trecho) is esperado


@pytest.mark.asyncio
async def test_apoio_exige_citacao_existente_e_corrige_numero_do_trecho():
    textos = ["Art. 11. O escopo da atividade de auditoria interna deve considerar todas as funções da instituição.",
              "Art. 3 A auditoria deve atuar com independência, autonomia e imparcialidade."]
    llm = LLMRoteiro([
        '{"afirmacoes": ["A auditoria pode avaliar as próprias atividades.", "O escopo abrange todas as funções.", "x é y."]}',
        # a frase citada não está em trecho nenhum: rebaixa
        '{"veredito": "apoiada", "trecho": 2, "citacao": "a auditoria pode avaliar as próprias atividades"}',
        # "trecho 11" é o número do artigo; a citação existe no trecho 1: aceita e corrige
        '{"veredito": "apoiada", "trecho": 11, "citacao": "o escopo da atividade de auditoria interna deve considerar"}',
        '{"veredito": "apoiada", "trecho": 1, "citacao": "o escopo da atividade de auditoria interna deve considerar todas as funções"}',
    ])
    v = await julgar_fidelidade_por_afirmacao(llm, "r", textos)
    a0, a1, a2 = v["afirmacoes"]
    assert (a0["veredito"], a0["rebaixada"]) == ("nao_apoiada", "citação não encontrada nos trechos")
    assert (a1["veredito"], a1["trecho"], a1["trecho_informado"]) == ("apoiada", 1, 11)
    assert (a2["veredito"], a2["trecho"]) == ("apoiada", 1) and "trecho_informado" not in a2
    assert v["veredito"] == "nao_fiel"
    assert "de 1 a 2" in llm.chamadas[1]["prompt"]
