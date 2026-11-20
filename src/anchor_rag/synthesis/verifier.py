"""Verificador determinístico de citações (variante C da ablação).

Confere a resposta do redator contra os trechos que ele recebeu, sem LLM:

1. citacao_inexistente  — [N] aponta para um trecho que não foi entregue (N fora de 1..k)
2. sem_citacao          — a resposta afirma algo (não é recusa) e não cita nenhum trecho
3. artigo_nao_citado    — a resposta menciona "art. X" que não aparece em nenhum trecho citado
4. numero_nao_citado    — um número da resposta (prazo, percentual, valor) não aparece,
                          nem em algarismos nem por extenso, em nenhum trecho citado

O verificador não julga se o trecho sustenta o sentido da frase: isso é a camada
semântica (juiz), que ainda não foi validada. Ele só garante que as referências e os
números da resposta existem nos trechos citados.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field

from anchor_rag.synthesis.prompt import RECUSA_PADRAO


@dataclass
class Problema:
    tipo: str
    detalhe: str

    def __str__(self) -> str:
        return f"{self.tipo}: {self.detalhe}"


@dataclass
class Verificacao:
    problemas: list[Problema] = field(default_factory=list)
    citados: list[int] = field(default_factory=list)
    recusa: bool = False

    @property
    def ok(self) -> bool:
        return not self.problemas


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s)


_RECUSA_NORM = _norm(RECUSA_PADRAO)[:30]


def eh_recusa(resposta: str) -> bool:
    """Mesma regra da avaliação: a recusa é decidida pela primeira frase."""
    primeira = re.split(r"(?<=[.!?])\s", (resposta or "").strip(), maxsplit=1)[0]
    p = _norm(primeira)
    return _RECUSA_NORM in p or p.startswith("nao encontrei")


# ---------------------------------------------------------------- números por extenso
_UNIDADES = ["zero", "um", "dois", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove",
             "dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete",
             "dezoito", "dezenove"]
_DEZENAS = {20: "vinte", 30: "trinta", 40: "quarenta", 50: "cinquenta", 60: "sessenta",
            70: "setenta", 80: "oitenta", 90: "noventa"}
_CENTENAS = {100: "cento", 200: "duzentos", 300: "trezentos", 400: "quatrocentos",
             500: "quinhentos", 600: "seiscentos", 700: "setecentos", 800: "oitocentos",
             900: "novecentos"}
_FEMININO = {"um": "uma", "dois": "duas", "duzentos": "duzentas", "trezentos": "trezentas",
             "quatrocentos": "quatrocentas", "quinhentos": "quinhentas", "seiscentos": "seiscentas",
             "setecentos": "setecentas", "oitocentos": "oitocentas", "novecentos": "novecentas"}


def _por_extenso(n: int) -> list[str]:
    """Formas por extenso de 0 a 999 (masculino e feminino; 'catorze' e 'quatorze')."""
    if n < 0 or n > 999:
        return []
    if n < 20:
        base = _UNIDADES[n]
    elif n < 100:
        d, u = divmod(n, 10)
        base = _DEZENAS[d * 10] + ("" if u == 0 else " e " + _UNIDADES[u])
    elif n == 100:
        base = "cem"
    else:
        c, resto = divmod(n, 100)
        base = _CENTENAS[c * 100] + ("" if resto == 0 else " e " + _por_extenso(resto)[0])
    formas = {base}
    fem = " ".join(_FEMININO.get(p, p) for p in base.split(" "))
    formas.add(fem)
    for f in list(formas):
        if "quatorze" in f:
            formas.add(f.replace("quatorze", "catorze"))
    return sorted(formas)


# ---------------------------------------------------------------- extração
# [1], e também [1, 2], [1 e 2], [1-3] (formatos que os modelos usam)
_CITACAO = re.compile(r"\[(\d+(?:\s*(?:,|e|-|–)\s*\d+)*)\]")
# "art. 6º", "artigo 15", "arts. 3", "Art 2o"
_ARTIGO = re.compile(r"\bart(?:igo)?s?\.?\s*(\d+)\s*(?:[ºo°]|-[a-z])?", re.IGNORECASE)
# números que são rótulos de estrutura ou de norma, não fatos a conferir
_ROTULO_ANTES = re.compile(
    r"(?:\bart(?:igo)?s?\.?|§+|\bpar[aá]grafo|\binciso|\bal[ií]nea|\bn[ºo°.]|\bn[uú]mero|"
    r"\bresolu[cç][aã]o(?:\s+(?:cmn|bcb))?|\bcircular|\blei|\bdecreto|\bcap[ií]tulo|\bse[cç][aã]o|"
    r"\bcmn|\bbcb|\bportaria|\binstru[cç][aã]o\s+normativa)\s*$",
    re.IGNORECASE,
)
_NUMERO = re.compile(r"(?<![\w.,])(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?(?:\s*%)?(?![\w])")


def _numeros_a_conferir(resposta: str) -> list[str]:
    sem_citacoes = _CITACAO.sub(" ", resposta)
    achados = []
    for m in _NUMERO.finditer(sem_citacoes):
        antes = sem_citacoes[max(0, m.start() - 40):m.start()]
        if _ROTULO_ANTES.search(antes):
            continue
        # ordinais de lista ("1. ...", "2) ...") no começo da linha
        if re.search(r"(^|\n)\s*$", antes) and re.match(r"\s*[.)]", sem_citacoes[m.end():m.end() + 2]):
            continue
        achados.append(m.group(0).strip())
    return achados


def _variantes_do_numero(token: str) -> list[str]:
    """Formas aceitas no texto do trecho para um número da resposta."""
    pct = token.endswith("%")
    t = token.rstrip("%").strip()
    inteiro, _, decimal = t.partition(",")
    digitos = inteiro.replace(".", "")
    formas = {t, digitos, inteiro}
    if decimal:
        formas.add(f"{digitos},{decimal}")
        formas.add(f"{digitos}.{decimal}")
    elif digitos.isdigit():
        n = int(digitos)
        if n >= 1000:
            formas.add(f"{n:,}".replace(",", "."))
        formas.update(_por_extenso(n))
    if pct:
        formas.update({f"{f}%" for f in list(formas)})
    return [f for f in formas if f]


def _contem(texto_norm: str, forma: str) -> bool:
    f = _norm(forma)
    if f.replace(".", "").replace(",", "").replace("%", "").isdigit():
        # número: não pode estar colado a outros dígitos
        return re.search(rf"(?<![\d.,]){re.escape(f)}(?![\d]|[.,]\d)", texto_norm) is not None
    return re.search(rf"\b{re.escape(f)}\b", texto_norm) is not None


# ---------------------------------------------------------------- verificação
def _numeros_citados(resposta: str) -> list[int]:
    nums: list[int] = []
    for grupo in _CITACAO.findall(resposta):
        partes = [int(x) for x in re.findall(r"\d+", grupo)]
        if re.search(r"[-–]", grupo) and len(partes) == 2 and partes[0] < partes[1] <= partes[0] + 10:
            partes = list(range(partes[0], partes[1] + 1))
        nums.extend(partes)
    return nums


def verificar(
    resposta: str,
    trechos: Sequence[str],
    artigos_dos_trechos: Sequence[str] = (),
    pergunta: str = "",
) -> Verificacao:
    """
    resposta: texto do redator.
    trechos: texto de cada trecho entregue, na ordem dos números [1], [2], ...
    artigos_dos_trechos: artigo de cada trecho (ex.: "6" para 'res_4557:art6-p1'), se conhecido.
    pergunta: números e artigos que já estão na pergunta podem ser repetidos (ex.: para
        corrigir uma premissa falsa: "não são 30 meses, são 60 [1]").
    """
    v = Verificacao()
    resposta = resposta or ""
    if eh_recusa(resposta):
        v.recusa = True
        return v

    k = len(trechos)
    numeros = _numeros_citados(resposta)
    for n in sorted(set(numeros)):
        if 1 <= n <= k:
            v.citados.append(n)
        else:
            v.problemas.append(Problema("citacao_inexistente", f"[{n}] (só existem os trechos 1 a {k})"))
    if not v.citados:
        if not any(p.tipo == "citacao_inexistente" for p in v.problemas):
            v.problemas.append(Problema("sem_citacao", "a resposta não cita nenhum trecho"))
        return v

    citados_texto = [_norm(trechos[i - 1]) for i in v.citados]
    texto = " ".join(citados_texto)
    artigos_citados = {str(artigos_dos_trechos[i - 1]) for i in v.citados
                       if i - 1 < len(artigos_dos_trechos) and artigos_dos_trechos[i - 1]}
    artigos_no_texto = {m.group(1) for m in _ARTIGO.finditer(texto)}
    artigos_na_pergunta = {m.group(1) for m in _ARTIGO.finditer(pergunta or "")}
    pergunta_norm = _norm(pergunta)

    artigos_na_resposta = {m.group(1) for m in _ARTIGO.finditer(resposta)}
    # "artigos 11 e 19": o segundo número também é artigo
    for m in re.finditer(r"\bart(?:igo)?s?\.?\s*\d+[ºo°]?((?:\s*(?:,|e)\s*\d+[ºo°]?)+)", resposta, re.IGNORECASE):
        artigos_na_resposta.update(re.findall(r"\d+", m.group(1)))
    for art in sorted(artigos_na_resposta, key=int):
        if art not in artigos_citados and art not in artigos_no_texto and art not in artigos_na_pergunta:
            v.problemas.append(Problema("artigo_nao_citado", f"art. {art} não aparece nos trechos citados"))

    vistos = set()
    for tok in _numeros_a_conferir(resposta):
        if tok in vistos or tok in artigos_na_resposta:  # artigo já conferido acima
            continue
        vistos.add(tok)
        formas = _variantes_do_numero(tok)
        if not any(_contem(texto, f) for f in formas) and not any(_contem(pergunta_norm, f) for f in formas):
            v.problemas.append(Problema("numero_nao_citado", f"{tok} não aparece nos trechos citados"))
    return v


def artigo_do_chunk_id(chunk_id: str | None) -> str | None:
    """'res_4557:art54' -> '54'; 'res_bcb_85:art3-p1' -> '3'."""
    m = re.search(r":art(\d+)", chunk_id or "")
    return m.group(1) if m else None


def mensagem_de_reparo(v: Verificacao) -> str:
    linhas = "\n".join(f"- {p}" for p in v.problemas)
    return (
        "Sua resposta anterior foi rejeitada pelo verificador de citações:\n"
        f"{linhas}\n\n"
        "Reescreva a resposta usando apenas os trechos fornecidos. Cite com [N] somente "
        "trechos que existem e que contêm o que você afirma; não mencione artigos nem números "
        "que não estejam nos trechos citados. Se os trechos não respondem à pergunta, "
        f'responda exatamente: "{RECUSA_PADRAO}"'
    )
