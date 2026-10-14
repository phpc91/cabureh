"""Leitura dos arquivos anuais da Câmara para estruturas em memória."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field

from .fonte import Fonte, ler_csv
from .periodo import Periodo

log = logging.getLogger(__name__)

TIPOS_PROJETO = {"PL", "PLP", "PEC", "PDL", "PRC"}


@dataclass
class Evento:
    inicio: str
    tipo: str
    descricao: str


@dataclass
class Votacao:
    id: str
    data: str
    registro: str
    orgao: str
    aprovacao: str
    descricao: str


@dataclass
class VotacaoPlenario:
    """Votação nominal do Plenário: momento do primeiro voto e votos por deputado."""
    id: str
    t: str = ""
    votos: dict[int, str] = field(default_factory=dict)
    partidos: dict[int, str] = field(default_factory=dict)


@dataclass
class Votos:
    plenario: dict[str, VotacaoPlenario]
    comissoes: Counter            # (deputado, dia) -> votos em outros órgãos
    partido_no_mes: dict          # (deputado, 'AAAA-MM') -> partido no primeiro voto do mês
    tipos: Counter


def carregar_eventos(fonte: Fonte, periodo: Periodo) -> tuple[dict[str, Evento], dict[str, set[int]]]:
    eventos: dict[str, Evento] = {}
    presencas: dict[str, set[int]] = {}
    for ano in periodo.anos:
        for id_, ini, tipo, desc in ler_csv(fonte.arquivo("eventos", ano), ["id", "dataHoraInicio", "descricaoTipo", "descricao"]):
            eventos[id_] = Evento(ini, tipo, desc)
        n = 0
        for id_ev, id_dep in ler_csv(fonte.arquivo("eventosPresencaDeputados", ano), ["idEvento", "idDeputado"]):
            if id_dep:
                presencas.setdefault(id_ev, set()).add(int(id_dep))
                n += 1
        log.info("eventos %d: %d presenças", ano, n)
    return eventos, presencas


def carregar_votacoes(fonte: Fonte, periodo: Periodo) -> dict[str, Votacao]:
    meta: dict[str, Votacao] = {}
    for ano in periodo.anos:
        cols = ["id", "data", "dataHoraRegistro", "siglaOrgao", "aprovacao", "descricao"]
        for id_, data, reg, org, aprov, desc in ler_csv(fonte.arquivo("votacoes", ano), cols):
            meta[id_] = Votacao(id_, data, reg, org, aprov, desc)
    log.info("votações (todos os órgãos): %d", len(meta))
    return meta


def carregar_votos(fonte: Fonte, periodo: Periodo, meta: dict[str, Votacao]) -> Votos:
    plen: dict[str, VotacaoPlenario] = {}
    comissoes: Counter = Counter()
    partido_no_mes: dict = {}
    tipos: Counter = Counter()
    for ano in periodo.anos:
        cols = ["idVotacao", "dataHoraVoto", "voto", "deputado_id", "deputado_siglaPartido"]
        n = 0
        for id_v, dt, voto, dep, partido in ler_csv(fonte.arquivo("votacoesVotos", ano), cols):
            if not dep:
                continue
            dep_i = int(dep)
            m = meta.get(id_v)
            tipos[voto] += 1
            n += 1
            if m is not None and m.orgao == "PLEN":
                v = plen.get(id_v)
                if v is None:
                    v = plen[id_v] = VotacaoPlenario(id_v, dt)
                if dt and (not v.t or dt < v.t):
                    v.t = dt
                v.votos[dep_i] = voto
                v.partidos[dep_i] = partido
            else:
                dia = (dt or (m.registro if m else ""))[:10]
                comissoes[(dep_i, dia)] += 1
            chave = (dep_i, (dt or "")[:7])
            if chave not in partido_no_mes:
                partido_no_mes[chave] = partido
        log.info("votos %d: %d", ano, n)
    return Votos(plen, comissoes, partido_no_mes, tipos)


def carregar_projetos(fonte: Fonte, periodo: Periodo) -> list[tuple[int, str, str, bool]]:
    """Autorias de deputados em projetos (proponente): (deputado, tipo, data de apresentação, é primeiro autor)."""
    props: dict[str, tuple[str, str]] = {}
    for ano in periodo.anos:
        for id_, tipo, data in ler_csv(fonte.arquivo("proposicoes", ano), ["id", "siglaTipo", "dataApresentacao"]):
            if tipo in TIPOS_PROJETO:
                props[id_] = (tipo, data)
    out = []
    for ano in periodo.anos:
        cols = ["idProposicao", "idDeputadoAutor", "ordemAssinatura", "proponente"]
        for id_p, dep, ordem, proponente in ler_csv(fonte.arquivo("proposicoesAutores", ano), cols):
            p = props.get(id_p)
            if p is None or not dep or proponente != "1":
                continue
            out.append((int(dep), p[0], p[1], ordem == "1"))
    log.info("autorias de projetos: %d", len(out))
    return out
