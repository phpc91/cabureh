"""Pauta votada, votos por partido e alinhamento (pauta.csv, partidos-votacao.csv, alinhamento.csv)."""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass

from .carga import Votacao, Votos
from .fonte import DIA, Fonte, ler_csv
from .periodo import Periodo

log = logging.getLogger(__name__)

AUXILIARES = {"REQ", "REC", "SAP", "CMC", "MSC", "REP"}
ORIENTACOES = {"Sim", "Não", "Obstrução", "Abstenção"}
TIPOS = ["Sim", "Não", "Abstenção", "Obstrução"]
SEM_PARTIDO = "S.PART."

# Siglas de bancada que não batem com a sigla do partido
NOME_BANCADA = {"SOLIDARIED": "SOLIDARIEDADE", "REPUBLICAN": "REPUBLICANOS", "PODEMOS": "PODE"}
# Pedaços usados nas siglas abreviadas de blocos (ex.: "Bl UniPpFdrPsdbCid...")
TOKENS_BLOCO = [("Solid", ["SOLIDARIEDADE"]), ("Patri", ["PATRIOTA"]), ("Avan", ["AVANTE"]), ("PcdoB", ["PCdoB"]),
                ("Psdb", ["PSDB"]), ("Psol", ["PSOL"]), ("Pode", ["PODE"]), ("Pros", ["PROS"]), ("Rede", ["REDE"]),
                ("Novo", ["NOVO"]), ("Mdb", ["MDB"]), ("Psd", ["PSD"]), ("Rep", ["REPUBLICANOS"]), ("Psc", ["PSC"]),
                ("Prd", ["PRD"]), ("Ptb", ["PTB"]), ("Pdt", ["PDT"]), ("Psb", ["PSB"]), ("Uni", ["UNIÃO"]),
                ("Cid", ["CIDADANIA"]), ("Pp", ["PP"]), ("Pl", ["PL"]), ("Pt", ["PT"]), ("Pv", ["PV"]),
                ("Dem", ["DEM"]), ("Psl", ["PSL"])]
FEDERACOES = {"PT": ["PT", "PCdoB", "PV"], "PSDB": ["PSDB", "CIDADANIA"], "PSOL": ["PSOL", "REDE"]}

RE_REQUERIMENTO = re.compile(r"requerimento", re.I)
RE_DESTAQUE = re.compile(r"mantid[oa]|suprimid[oa]|prefer[êe]ncia|destaque|emenda(?! substitutiva global)|"
                         r"subemenda(?! substitutiva global)|dispositivo|express[aã]o|parte ", re.I)


def etapa(descricao: str) -> str:
    if RE_REQUERIMENTO.search(descricao):
        return "Requerimento"
    if RE_DESTAQUE.search(descricao):
        return "Destaque ou emenda"
    return "Texto principal"


def limpar_ementa(e: str) -> str:
    s = re.sub(r"\s+", " ", e or "").strip()
    m = re.search(r"NOVA EMENTA:", s, re.I)
    return (s[m.end():].strip() if m else s)[:420]


def membros_bloco(sigla: str) -> list[str]:
    """Partidos que aparecem na sigla abreviada de um bloco. Siglas cortadas ("...") podem omitir membros."""
    s = re.sub(r"^Bl\s*", "", sigla).removesuffix("...")
    baixo = s.lower()
    out, fed, i = [], False, 0
    while i < len(s):
        if baixo.startswith("fdr", i):
            fed, i = True, i + 3
            continue
        tok = next((t for t in TOKENS_BLOCO if baixo.startswith(t[0].lower(), i)), None)
        if tok is None:
            i += 1
            continue
        for p in tok[1]:
            out.append(p)
            if fed and p in FEDERACOES:
                out.extend(FEDERACOES[p])
        fed = False
        i += len(tok[0])
    return list(dict.fromkeys(out))


def orientacao_partido(orient: dict[str, str], partido: str) -> str | None:
    """Orientação que vale para o partido: a própria, a da federação ou a de um bloco que o inclui."""
    P = partido.upper()
    for b, o in orient.items():
        if NOME_BANCADA.get(b.upper(), b.upper()) == P:
            return o
    for b, o in orient.items():
        if b.startswith("Fdr ") and any(x.upper() == P for x in b[4:].split("-")):
            return o
    for b, o in orient.items():
        if b.startswith("Bl ") and any(x.upper() == P for x in membros_bloco(b)):
            return o
    return None


@dataclass
class Saida:
    pauta: list[dict]
    partidos: list[dict]
    alinhamento: list[dict]
    resumo: dict


def carregar_proposicoes_votadas(fonte: Fonte, periodo: Periodo, ids: set[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    cols = ["idVotacao", "proposicao_id", "proposicao_titulo", "proposicao_ementa", "proposicao_siglaTipo"]
    for ano in periodo.anos:
        for id_v, pid, tit, em, sig in ler_csv(fonte.arquivo("votacoesProposicoes", ano), cols):
            if id_v in ids:
                out.setdefault(id_v, []).append({"pid": pid, "titulo": tit, "ementa": em, "sigla": sig})
    return out


def carregar_orientacoes(fonte: Fonte, periodo: Periodo, ids: set[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for ano in periodo.anos:
        for id_v, bancada, o in ler_csv(fonte.arquivo("votacoesOrientacoes", ano), ["idVotacao", "siglaBancada", "orientacao"]):
            if id_v in ids:
                out.setdefault(id_v, {})[bancada] = o
    return out


def carregar_temas(fonte: Fonte, pids: list[str]) -> dict[str, list[str]]:
    def um(pid: str) -> list[str]:
        j = fonte.api(f"/proposicoes/{pid}/temas", ttl=30 * DIA)
        return [t["tema"] for t in (j or {}).get("dados", [])]
    return dict(zip(pids, fonte.em_paralelo(um, pids)))


def montar(fonte: Fonte, periodo: Periodo, meta: dict[str, Votacao], votos: Votos) -> Saida:
    plen = {i: m for i, m in meta.items() if m.orgao == "PLEN" and periodo.contem(m.data)}
    nominais = {i: v for i, v in votos.plenario.items() if i in plen}
    ids = set(nominais)
    props = carregar_proposicoes_votadas(fonte, periodo, ids)
    orient = carregar_orientacoes(fonte, periodo, ids)
    principal = {}
    for i in ids:
        lista = props.get(i, [])
        principal[i] = next((p for p in lista if p["sigla"] not in AUXILIARES), lista[0] if lista else None)
    pids = sorted({p["pid"] for p in principal.values() if p})
    temas = carregar_temas(fonte, pids)

    # votos por votação e partido
    vp: dict[tuple[str, str], Counter] = {}
    totais: dict[str, Counter] = {}
    for i, v in nominais.items():
        tot = totais[i] = Counter()
        for dep, voto in v.votos.items():
            c = vp.setdefault((i, v.partidos.get(dep) or SEM_PARTIDO), Counter())
            chave = voto if voto in TIPOS else "outro"
            c[chave] += 1
            c["n"] += 1
            tot[chave] += 1
            tot["n"] += 1

    def maioria(c: Counter) -> str:
        melhor, n = None, -1
        for t in TIPOS:
            if c[t] > n:
                melhor, n = t, c[t]
        return melhor

    pauta = []
    for i, v in nominais.items():
        m, p, om = plen[i], principal.get(i), orient.get(i, {})
        tot = totais[i]
        ts = temas.get(p["pid"], []) if p else []
        pauta.append({
            "id_votacao": i, "data": m.data[:10], "proposicao": p["titulo"] if p else "",
            "id_proposicao": p["pid"] if p else "", "tipo": p["sigla"] if p else "",
            "ementa": limpar_ementa(p["ementa"]) if p else "", "tema": ts[0] if ts else "Sem tema",
            "temas": "; ".join(ts), "etapa": etapa(m.descricao),
            "votacao": re.sub(r"\s+", " ", m.descricao)[:260], "aprovada": 1 if m.aprovacao == "1" else 0,
            "sim": tot["Sim"], "nao": tot["Não"], "abstencoes": tot["Abstenção"], "obstrucoes": tot["Obstrução"],
            "votos": tot["n"], "orient_governo": om.get("Governo", ""), "orient_oposicao": om.get("Oposição", ""),
        })
    pauta.sort(key=lambda r: (r["data"], r["id_votacao"]))

    partidos = []
    for (i, P), c in vp.items():
        o = orientacao_partido(orient.get(i, {}), P)
        partidos.append({"id_votacao": i, "partido": "Sem partido" if P == SEM_PARTIDO else P, "sim": c["Sim"],
                         "nao": c["Não"], "abstencoes": c["Abstenção"], "obstrucoes": c["Obstrução"],
                         "outros": c["outro"], "orientacao": o if o in ORIENTACOES else ""})
    partidos.sort(key=lambda r: (r["id_votacao"], r["partido"]))

    alin: dict[tuple, dict] = {}
    for i, v in nominais.items():
        mes = plen[i].data[:7]
        om = orient.get(i, {})
        g = om.get("Governo")
        for dep, voto in v.votos.items():
            if voto == "Artigo 17":
                continue
            P = v.partidos.get(dep) or SEM_PARTIDO
            k = (dep, mes, P)
            a = alin.get(k)
            if a is None:
                a = alin[k] = {"id_deputado": dep, "mes": mes, "partido": "Sem partido" if P == SEM_PARTIDO else P,
                               "votos": 0, "base_bancada": 0, "com_bancada": 0, "base_governo": 0, "com_governo": 0,
                               "obstrucoes": 0, "obst_orientadas": 0, "obst_bancada": 0, "obst_isoladas": 0}
            a["votos"] += 1
            c = vp[(i, P)]
            if c["n"] >= 3 and P != SEM_PARTIDO:
                a["base_bancada"] += 1
                if voto == maioria(c):
                    a["com_bancada"] += 1
            if g in ("Sim", "Não"):
                a["base_governo"] += 1
                if voto == g:
                    a["com_governo"] += 1
            if voto == "Obstrução":
                a["obstrucoes"] += 1
                if orientacao_partido(om, P) == "Obstrução":
                    a["obst_orientadas"] += 1
                elif c["n"] >= 3 and c["Obstrução"] / c["n"] >= 0.5:
                    a["obst_bancada"] += 1
                else:
                    a["obst_isoladas"] += 1
    alinhamento = sorted(alin.values(), key=lambda r: (r["id_deputado"], r["mes"], r["partido"]))

    resumo = {"votacoes": len(pauta), "proposicoes": len(pids), "linhas_partidos": len(partidos),
              "linhas_alinhamento": len(alinhamento), "obstrucoes": sum(a["obstrucoes"] for a in alinhamento),
              "obst_orientadas": sum(a["obst_orientadas"] for a in alinhamento),
              "ultima_votacao": pauta[-1]["data"] if pauta else None, "sem_tema": sum(r["tema"] == "Sem tema" for r in pauta)}
    log.info("pauta: %s", resumo)
    return Saida(pauta, partidos, alinhamento, resumo)
