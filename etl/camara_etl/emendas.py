"""Emendas parlamentares ao Orçamento, do Portal da Transparência (CGU).

O Portal publica um zip único, aberto e sem chave, com três arquivos (Latin-1, ';'):
- EmendasParlamentares.csv: uma linha por emenda, ação e local, com valores acumulados
  (empenhado, pago, restos a pagar pagos);
- EmendasParlamentares_PorFavorecido.csv: o que cada favorecido recebeu, mês a mês;
- EmendasParlamentares_Convenios.csv: convênios (não usado aqui).

O autor vem só pelo nome registrado no SIAFI, então cada emenda individual é ligada a um
deputado pelo nome, conferindo que ele estava em exercício quando a emenda foi apresentada.
Emendas de bancada, de comissão e de relator não têm autor individual e entram só nos totais.

Saídas:
- emendas.csv: por deputado, ano da emenda, tipo, área e UF de destino;
- emendas-destinos.csv: os maiores destinos (município ou estado) de cada deputado em cada ano;
- emendas-mes.csv: pagamentos aos favorecidos por deputado e mês;
- emendas-favorecidos.csv: os maiores favorecidos de cada deputado em cada ano (pessoas físicas
  aparecem agrupadas, sem nome);
- emendas-tipos.csv: totais por ano e tipo de emenda, inclusive as coletivas.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from .deputados import Deputado
from .fonte import DIA, Fonte, ler_csv_zip
from .periodo import Periodo

log = logging.getLogger(__name__)

ARQ_EMENDAS = "EmendasParlamentares.csv"
ARQ_FAVORECIDOS = "EmendasParlamentares_PorFavorecido.csv"
ENCODING = "latin-1"
URL_SENADORES = "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/{ini}/{fim}.json"
MAX_DESTINOS = 10
MAX_FAVORECIDOS = 10

COL_EMENDAS = [
    "Código da Emenda", "Ano da Emenda", "Tipo de Emenda", "Nome do Autor da Emenda",
    ("Localidade de aplicação do recurso", "Localidade do gasto", "Localidade do Gasto"),
    "Município", "UF", "Nome Função", "Valor Empenhado", "Valor Pago", "Valor Restos A Pagar Pagos",
]
COL_FAVORECIDOS = [
    "Código da Emenda", "Nome do Autor da Emenda", "Tipo de Emenda", "Ano/Mês", "Código do Favorecido",
    "Favorecido", "Natureza Jurídica", "Tipo Favorecido", "UF Favorecido", "Município Favorecido", "Valor Recebido",
]

TIPOS = {  # chaves já normalizadas por norm()
    "EMENDA INDIVIDUAL TRANSFERENCIAS COM FINALIDADE DEFINIDA": "Finalidade definida",
    "EMENDA INDIVIDUAL TRANSFERENCIAS ESPECIAIS": "Transferência especial",
    "EMENDA DE BANCADA": "Bancada",
    "EMENDA DE COMISSAO": "Comissão",
    "EMENDA DE RELATOR": "Relator",
}
INDIVIDUAIS = {"Finalidade definida", "Transferência especial"}

UFS = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM", "BAHIA": "BA", "CEARA": "CE",
    "DISTRITO FEDERAL": "DF", "ESPIRITO SANTO": "ES", "GOIAS": "GO", "MARANHAO": "MA", "MATO GROSSO": "MT",
    "MATO GROSSO DO SUL": "MS", "MINAS GERAIS": "MG", "PARA": "PA", "PARAIBA": "PB", "PARANA": "PR",
    "PERNAMBUCO": "PE", "PIAUI": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS", "RONDONIA": "RO", "RORAIMA": "RR", "SANTA CATARINA": "SC", "SAO PAULO": "SP",
    "SERGIPE": "SE", "TOCANTINS": "TO",
}

# Palavras que não ajudam a distinguir pessoas ao comparar nomes de forma aproximada
TITULOS = {
    "DR", "DRA", "DOUTOR", "DOUTORA", "PASTOR", "PASTORA", "DELEGADO", "DELEGADA", "CAPITAO", "CAPITA",
    "CORONEL", "CEL", "GENERAL", "SARGENTO", "SGT", "CABO", "SUBTENENTE", "TENENTE", "MAJOR", "COMANDANTE",
    "PROFESSOR", "PROFESSORA", "PROF", "ENFERMEIRA", "ENFERMEIRO", "MISSIONARIO", "MISSIONARIA", "BISPO",
    "PADRE", "IRMAO", "IRMA", "DEPUTADO", "DEPUTADA", "JUNIOR", "JR", "FILHO", "NETO", "SOBRINHO",
    "DE", "DA", "DO", "DAS", "DOS", "E",
}
# Nome no SIAFI -> nome usado na Câmara, para casos que a comparação aproximada não resolve
APELIDOS = {
    "MARCIVANIA FLEXA": "PROFESSORA MARCIVANIA",
}
EX_PARLAMENTAR = re.compile(r"^(.*?)\s*\(\s*EX-?\s*PARLAMENTAR\b", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn").upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", s)).strip()


def tokens(nome_norm: str) -> frozenset[str]:
    return frozenset(t for t in nome_norm.split() if t not in TITULOS and len(t) > 1)


PREFIXO_CARGO = re.compile(r"^(DEP|DEPUTAD[OA]|SEN|SENADOR[A]?) ")


def nome_autor(nome: str) -> str:
    """Nome normalizado de quem responde pela emenda, sem prefixo de cargo e com apelidos resolvidos."""
    n = PREFIXO_CARGO.sub("", norm(titular(nome)))
    return APELIDOS.get(n, n)


def nome_autor_n(nome: str) -> str:  # alias: dentro do Casador, `nome_autor` é o nome do parâmetro
    return nome_autor(nome)


def titular(nome_autor: str) -> str:
    """Quem responde hoje pela emenda: 'FULANO (EX-PARLAMENTAR BELTRANO, NOS TERMOS ...)' -> FULANO."""
    m = EX_PARLAMENTAR.match(nome_autor or "")
    return (m.group(1) if m else nome_autor or "").strip()


def tipo(texto: str) -> str:
    return TIPOS.get(norm(texto), (texto or "Outro").strip())


def valor(texto: str) -> float:
    t = (texto or "").strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t or 0)
    except ValueError:
        return 0.0


def area(funcao: str, tp: str) -> str:
    f = (funcao or "").strip()
    if not f or f == "Sem informação" or norm(f) == "ENCARGOS ESPECIAIS":
        return "Sem área definida" if tp == "Transferência especial" or norm(f) == "ENCARGOS ESPECIAIS" else "Sem informação"
    return f


def nome_proprio(s: str) -> str:
    """CAMPINAS -> Campinas; RIO DE JANEIRO -> Rio de Janeiro."""
    partes = (s or "").strip().lower().split()
    return " ".join(p if (i and p in {"de", "da", "do", "das", "dos", "e"}) else p[:1].upper() + p[1:] for i, p in enumerate(partes))


def destino(localidade: str, municipio: str, uf_nome: str) -> tuple[str, str]:
    """(rótulo do destino, sigla da UF ou '')."""
    sigla = UFS.get(norm(uf_nome), "")
    mun, loc = norm(municipio), norm(localidade)
    if sigla:
        if mun and mun not in {"MULTIPLO", "SEM INFORMACAO"}:
            return f"{nome_proprio(municipio)} - {sigla}", sigla
        if "MULTIPLO" in mun or "MULTIPLO" in loc:
            return f"Vários municípios - {sigla}", sigla
        return f"{nome_proprio(uf_nome)} (estado)", sigla
    if "NACIONAL" in loc:
        return "Nacional", ""
    if "MULTIPLO" in loc:
        return "Vários locais", ""
    m = re.search(r"^(.*?)\s*-\s*([A-Z]{2})$", (localidade or "").strip())
    if m and m.group(2) in UFS.values():
        return f"{nome_proprio(m.group(1))} - {m.group(2)}", m.group(2)
    return nome_proprio(localidade) or "Sem informação", ""


def documento(codigo: str, tipo_favorecido: str) -> str:
    if norm(tipo_favorecido).startswith("PESSOA F"):
        return "Pessoa física"
    d = re.sub(r"\D", "", codigo or "")
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return "Pessoa física"
    return (codigo or "").strip()


# ----------------------------------------------------------------- casamento
class Casador:
    """Liga o nome do autor (SIAFI) ao deputado, conferindo o exercício na época da emenda.

    As emendas de um ano são apresentadas entre setembro e dezembro do ano anterior. Primeiro
    procura quem estava em exercício nesse intervalo; se ninguém, aceita quem esteve em exercício
    de julho do ano anterior ao fim do ano da emenda (caso de quem herdou emendas de outro).
    Em cada janela:
    1. nome igual (sem acentos e pontuação) a algum nome que o deputado usou;
    2. se não houver, comparação aproximada: um nome contido no outro, ignorando títulos como
       Dr. e Pastor e sufixos como Júnior, com candidato único e autor que não seja homônimo de
       senador, exigindo pelo menos duas palavras dos dois lados (nomes de uma palavra só, como
       "Vicentinho", casariam com pessoas diferentes). Os poucos casos assim estão em APELIDOS.
    """

    def __init__(self, deputados: dict[int, Deputado], senadores: set[str] | None):
        # `deputados`: os parlamentares da casa analisada; `senadores`: nomes da OUTRA casa (homônimos a evitar)
        self.deputados = deputados
        self.senadores = senadores
        self.por_nome: dict[str, list[int]] = defaultdict(list)
        self.toks: dict[int, list[frozenset[str]]] = {}
        for d in deputados.values():
            ns = {norm(n) for n in (d.nomes | {d.nome}) if n}
            for n in ns:
                if d.id not in self.por_nome[n]:
                    self.por_nome[n].append(d.id)
            self.toks[d.id] = [t for t in {tokens(n) for n in ns} if t]
        self.cache: dict[tuple[str, int], int | None] = {}
        self.exatos: dict[str, int] = {}
        self.aproximados: dict[str, int] = {}
        self.ambiguos: set[str] = set()
        self.nao_casados: dict[str, float] = defaultdict(float)
        self.de_senadores: dict[str, float] = defaultdict(float)

    def _ativo(self, dep_id: int, ano: int, estreito: bool) -> bool:
        if estreito:
            return self.deputados[dep_id].exerceu_entre(f"{ano - 1}-09-01T00:00:00", f"{ano - 1}-12-31T23:59:59")
        return self.deputados[dep_id].exerceu_entre(f"{ano - 1}-07-01T00:00:00", f"{ano}-12-31T23:59:59")

    @staticmethod
    def _parecido(t: frozenset[str], d: frozenset[str]) -> bool:
        return len(d) >= 2 and len(t) >= 2 and (t <= d or d <= t)

    def __call__(self, nome_autor: str, ano: int) -> int | None:
        chave = (nome_autor, ano)
        if chave in self.cache:
            return self.cache[chave]
        n = nome_autor_n(nome_autor)
        achado = None
        homonimos = self.por_nome.get(n, [])
        for estreito in (True, False):
            exatos = [i for i in homonimos if self._ativo(i, ano, estreito)]
            if len(exatos) == 1:
                achado = exatos[0]
                self.exatos[n] = achado
                break
            if len(exatos) > 1:
                self.ambiguos.add(n)
                break
        if achado is None and not homonimos and self.senadores is not None and n not in self.senadores:
            t = tokens(n)
            cands_todos = {i for i, ts in self.toks.items() if any(self._parecido(t, d) for d in ts)}
            for estreito in (True, False):
                cands = {i for i in cands_todos if self._ativo(i, ano, estreito)}
                if len(cands) == 1:
                    achado = cands.pop()
                    self.aproximados[n] = achado
                    break
                if len(cands) > 1:
                    self.ambiguos.add(n)
                    break
        self.cache[chave] = achado
        return achado

    def anotar_falha(self, nome_autor: str, v: float) -> None:
        n = nome_autor_n(nome_autor)
        if self.senadores is not None and n in self.senadores:
            self.de_senadores[n] += v
        else:
            self.nao_casados[titular(nome_autor)] += v


def carregar_senadores(fonte: Fonte, legislaturas: list[int]) -> set[str] | None:
    if not legislaturas:
        return None
    j = fonte.json_externo(URL_SENADORES.format(ini=min(legislaturas), fim=max(legislaturas)), ttl=7 * DIA)
    try:
        ps = j["ListaParlamentarLegislatura"]["Parlamentares"]["Parlamentar"]
    except (TypeError, KeyError):
        log.warning("lista de senadores indisponível; casamento aproximado desligado")
        return None
    nomes = set()
    for p in ps if isinstance(ps, list) else [ps]:
        ident = p.get("IdentificacaoParlamentar") or {}
        for k in ("NomeParlamentar", "NomeCompletoParlamentar"):
            if ident.get(k):
                nomes.add(norm(ident[k]))
    log.info("senadores conhecidos: %d nomes", len(nomes))
    return nomes


# --------------------------------------------------------------------- montar
@dataclass
class SaidaEmendas:
    emendas: list[dict]
    destinos: list[dict]
    meses: list[dict]
    favorecidos: list[dict]
    tipos: list[dict]
    resumo: dict


def _partido(dep: Deputado, t: str) -> str:
    return dep.partido_em(t) or "Sem partido"


def montar(fonte: Fonte, periodo: Periodo, deputados: dict, outra_casa: set[str] | None) -> SaidaEmendas:
    """`deputados`: parlamentares da casa analisada (deputados ou senadores, com nome, nomes,
    exerceu_entre e partido_em); `outra_casa`: nomes normalizados dos parlamentares da outra casa."""
    arq = fonte.emendas()
    if arq is None:
        raise FileNotFoundError("zip de emendas não encontrado")
    casar = Casador(deputados, outra_casa)
    anos = {int(a) for a in periodo.anos}

    # 1) emendas: valores acumulados por emenda
    grupos: dict[tuple, list] = defaultdict(lambda: [0.0, 0.0])
    por_codigo: dict[str, tuple] = {}          # código -> (chave do grupo, empenhado) da maior linha
    dest: dict[tuple, list] = defaultdict(lambda: [0.0, 0.0, ""])
    tipos_ano: dict[tuple, list] = defaultdict(lambda: [0.0, 0.0, set()])
    for cod, ano_s, tp_s, autor, loc, mun, uf, func, emp, pago, rpp in ler_csv_zip(arq, COL_EMENDAS, ARQ_EMENDAS, ENCODING):
        try:
            ano = int(ano_s)
        except ValueError:
            continue
        if ano not in anos:
            continue
        tp, e, p = tipo(tp_s), valor(emp), valor(pago) + valor(rpp)
        t = tipos_ano[(ano, tp)]
        t[0] += e
        t[1] += p
        t[2].add(cod)
        if tp not in INDIVIDUAIS:
            continue
        dep_id = casar(autor, ano)
        if dep_id is None:
            casar.anotar_falha(autor, e)
            continue
        dep = deputados[dep_id]
        rotulo, sigla = destino(loc, mun, uf)
        chave = (dep_id, ano, _partido(dep, f"{ano - 1}-11-30T23:59:59"), tp, area(func, tp), sigla)
        g = grupos[chave]
        g[0] += e
        g[1] += p
        if cod not in por_codigo or e > por_codigo[cod][1]:
            por_codigo[cod] = (chave, e)
        d = dest[(dep_id, ano, rotulo)]
        d[0] += e
        d[1] += p
        d[2] = sigla
    contagem: dict[tuple, int] = defaultdict(int)
    for chave, _ in por_codigo.values():
        contagem[chave] += 1
    emendas = [{"id_deputado": d, "ano": a, "partido": pt, "tipo": tp, "area": ar, "uf_destino": uf,
                "emendas": contagem.get((d, a, pt, tp, ar, uf), 0), "empenhado": round(e, 2), "pago": round(p, 2)}
               for (d, a, pt, tp, ar, uf), (e, p) in sorted(grupos.items())]
    por_dep_ano: dict[tuple, list] = defaultdict(list)
    for (d, a, rot), (e, p, uf) in dest.items():
        por_dep_ano[(d, a)].append((e, p, rot, uf))
    destinos = []
    for (d, a), itens in sorted(por_dep_ano.items()):
        for e, p, rot, uf in sorted(itens, key=lambda x: -x[0])[:MAX_DESTINOS]:
            destinos.append({"id_deputado": d, "ano": a, "destino": rot, "uf": uf, "empenhado": round(e, 2), "pago": round(p, 2)})
    tipos = [{"ano": a, "tipo": tp, "emendas": len(cods), "empenhado": round(e, 2), "pago": round(p, 2)}
             for (a, tp), (e, p, cods) in sorted(tipos_ano.items())]

    # 2) pagamentos aos favorecidos, mês a mês
    meses_validos = set(periodo.meses)
    por_mes: dict[tuple, float] = defaultdict(float)
    forn: dict[tuple, list] = {}
    sem_autor = 0.0
    for cod, autor, tp_s, am, cod_fav, fav, nat, tipo_fav, uf_fav, mun_fav, v_s in ler_csv_zip(arq, COL_FAVORECIDOS, ARQ_FAVORECIDOS, ENCODING):
        mes = f"{am[:4]}-{am[4:6]}" if len(am) >= 6 else ""
        if mes not in meses_validos:
            continue
        tp = tipo(tp_s)
        if tp not in INDIVIDUAIS:
            continue
        try:
            ano_emenda = int(cod[:4])
        except ValueError:
            continue
        v = valor(v_s)
        dep_id = casar(autor, ano_emenda)
        if dep_id is None:
            sem_autor += v
            continue
        dep = deputados[dep_id]
        por_mes[(dep_id, mes, _partido(dep, f"{mes}-28T23:59:59"), tp)] += v
        doc = documento(cod_fav, tipo_fav)
        pf = doc == "Pessoa física"
        chave = (dep_id, mes[:4], "pf" if pf else (doc or norm(fav)))
        f = forn.get(chave)
        if f is None:
            nome = "Pessoas físicas (agrupadas)" if pf else (fav or "").strip()
            f = forn[chave] = [0.0, 0, nome, doc, "" if pf else (nat or "").strip(), "" if pf else uf_fav.strip(),
                               "" if pf else nome_proprio(mun_fav)]
        f[0] += v
        f[1] += 1
    meses = [{"id_deputado": d, "mes": m, "partido": p, "tipo": tp, "valor": round(v, 2)}
             for (d, m, p, tp), v in sorted(por_mes.items())]
    agrupado: dict[tuple, list] = defaultdict(list)
    for (d, a, _), item in forn.items():
        agrupado[(d, a)].append(item)
    favorecidos = []
    for (d, a), itens in sorted(agrupado.items()):
        for v, n, nome, doc, nat, uf, mun in sorted(itens, key=lambda x: -x[0])[:MAX_FAVORECIDOS]:
            favorecidos.append({"id_deputado": d, "ano": a, "favorecido": nome, "documento": doc, "natureza": nat,
                                "uf": uf, "municipio": mun, "valor": round(v, 2), "pagamentos": n})

    total_ind = sum(r["empenhado"] for r in tipos if r["tipo"] in INDIVIDUAIS)
    casado = sum(r["empenhado"] for r in emendas)
    de_senadores = sum(casar.de_senadores.values())
    resumo = {
        "anos": sorted(anos),
        "linhas_emendas": len(emendas), "linhas_mes": len(meses), "linhas_favorecidos": len(favorecidos),
        "deputados": len({r["id_deputado"] for r in emendas}),
        "individuais_empenhado": round(total_ind, 2),
        "individuais_casados": round(casado, 2),
        "individuais_da_outra_casa": round(de_senadores, 2),
        "individuais_sem_autor_identificado": round(total_ind - casado - de_senadores, 2),
        "pago_no_periodo": round(sum(r["valor"] for r in meses), 2),
        "pago_no_periodo_sem_autor": round(sem_autor, 2),
        "autores_casados_exato": len(casar.exatos),
        "autores_casados_aproximado": {k: deputados[v].nome for k, v in sorted(casar.aproximados.items())},
        "autores_ambiguos": sorted(casar.ambiguos),
        "autores_nao_casados": [f"{k} ({v / 1e6:.1f} mi)" for k, v in sorted(casar.nao_casados.items(), key=lambda x: -x[1])[:30]],
    }
    log.info("emendas: %s", {k: v for k, v in resumo.items() if not isinstance(v, (dict, list))})
    return SaidaEmendas(emendas, destinos, meses, favorecidos, tipos, resumo)
