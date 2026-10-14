"""Presença, votos e projetos por deputado, mês e partido (arquivo presenca.csv)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .carga import Evento, Votos
from .deputados import Deputado, nome_legivel
from .periodo import Periodo

log = logging.getLogger(__name__)

CAMPOS = ["sessoes", "presencas", "votacoes", "votou_sim", "votou_nao", "abstencao", "obstrucao",
          "outros_votos", "votos_comissoes", "eventos_comissoes", "projetos_autor", "projetos_coautor"]
SESSAO = "Sessão Deliberativa"
FORA_DE_COMISSOES = {SESSAO, "Teste do Painel Eletrônico"}
TIPO_VOTO = {"Sim": "votou_sim", "Não": "votou_nao", "Abstenção": "abstencao", "Obstrução": "obstrucao"}
SEM_PARTIDO = "S.PART."


@dataclass
class Resultado:
    linhas: list[dict]
    sessoes: list[tuple[str, str]]      # (id, início) das sessões deliberativas contadas
    votacoes: list[str]                 # ids das votações nominais do Plenário contadas
    resumo: dict


class Acumulador:
    def __init__(self, periodo: Periodo, deputados: dict[int, Deputado], votos: Votos):
        self.meses = set(periodo.meses)
        self.deps = deputados
        self.votos = votos
        self.celulas: dict[tuple[int, str, str], dict[str, int]] = {}

    def partido_em(self, dep_id: int, t: str) -> str:
        dep = self.deps.get(dep_id)
        ev = dep.em(t) if dep else None
        if ev and ev.partido:
            return ev.partido
        p = self.votos.partido_no_mes.get((dep_id, t[:7]))
        if p:
            return p
        if dep and dep.primeiro_partido:
            return dep.primeiro_partido
        return SEM_PARTIDO

    def celula(self, dep_id: int, t: str) -> dict[str, int] | None:
        mes = t[:7]
        if mes not in self.meses:
            return None
        chave = (dep_id, mes, self.partido_em(dep_id, t))
        c = self.celulas.get(chave)
        if c is None:
            c = self.celulas[chave] = dict.fromkeys(CAMPOS, 0)
        return c


def em_exercicio(deputados: dict[int, Deputado], ids: set[int], t: str) -> set[int]:
    out = set()
    for i in ids:
        d = deputados.get(i)
        ev = d.em(t) if d else None
        if ev and ev.exercicio:
            out.add(i)
    return out


def montar(periodo: Periodo, deputados: dict[int, Deputado], ids: set[int],
           eventos: dict[str, Evento], presencas: dict[str, set[int]], votos: Votos,
           projetos: list[tuple[int, str, str, bool]]) -> Resultado:
    acc = Acumulador(periodo, deputados, votos)

    # Sessões deliberativas do Plenário com lista de presença
    sessoes = sorted(((i, e.inicio) for i, e in eventos.items()
                      if e.tipo == SESSAO and periodo.contem(e.inicio) and presencas.get(i)), key=lambda x: x[1])
    for id_ev, ini in sessoes:
        presentes = presencas[id_ev]
        for dep in presentes | em_exercicio(deputados, ids, ini):
            c = acc.celula(dep, ini)
            if c is None:
                continue
            c["sessoes"] += 1
            if dep in presentes:
                c["presencas"] += 1

    # Votações nominais do Plenário
    plen = sorted((v for v in votos.plenario.values() if periodo.contem(v.t)), key=lambda v: v.t)
    for v in plen:
        for dep in set(v.votos) | em_exercicio(deputados, ids, v.t):
            c = acc.celula(dep, v.t)
            if c is None:
                continue
            c["votacoes"] += 1
            voto = v.votos.get(dep)
            if voto is not None:
                c[TIPO_VOTO.get(voto, "outros_votos")] += 1

    # Votos em comissões e outros órgãos
    for (dep, dia), n in votos.comissoes.items():
        if dia and periodo.contem(dia):
            c = acc.celula(dep, dia + "T12:00:00")
            if c is not None:
                c["votos_comissoes"] += n

    # Presença em reuniões de comissão, audiências e outros eventos
    for id_ev, e in eventos.items():
        if e.tipo in FORA_DE_COMISSOES or not periodo.contem(e.inicio):
            continue
        for dep in presencas.get(id_ev, ()):
            c = acc.celula(dep, e.inicio)
            if c is not None:
                c["eventos_comissoes"] += 1

    # Projetos apresentados
    for dep, _tipo, data, primeiro in projetos:
        if not periodo.contem(data):
            continue
        c = acc.celula(dep, data if len(data) >= 19 else data[:10] + "T12:00:00")
        if c is not None:
            c["projetos_autor" if primeiro else "projetos_coautor"] += 1

    # Linhas de saída: só quem teve sessão ou votação no período
    por_dep: dict[int, list] = {}
    for (dep, mes, partido), c in acc.celulas.items():
        por_dep.setdefault(dep, []).append((mes, partido, c))
    linhas = []
    for dep, itens in por_dep.items():
        if not any(c["sessoes"] or c["votacoes"] for _, _, c in itens):
            continue
        d = deputados.get(dep)
        nome = nome_legivel(d.nome) if d and d.nome else f"Deputado {dep}"
        uf = d.uf if d else ""
        for mes, partido, c in sorted(itens, key=lambda x: (x[0], x[1])):
            if not any(c.values()):
                continue
            linhas.append({"id_deputado": dep, "deputado": nome, "uf": uf,
                           "partido": "Sem partido" if partido == SEM_PARTIDO else partido, "mes": mes, **c})
    linhas.sort(key=lambda r: (r["deputado"], r["id_deputado"], r["mes"], r["partido"]))
    soma = {k: sum(r[k] for r in linhas) for k in CAMPOS}
    resumo = {"sessoes": len(sessoes), "votacoes_nominais": len(plen),
              "deputados": len({r["id_deputado"] for r in linhas}), "linhas": len(linhas), "somas": soma}
    log.info("presença: %s", resumo)
    return Resultado(linhas, sessoes, [v.id for v in plen], resumo)
