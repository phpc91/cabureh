"""Cadastro dos deputados e linha do tempo de exercício do mandato."""

from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass, field

from .fonte import DIA, Fonte
from .periodo import Periodo

log = logging.getLogger(__name__)

# Situações que tiram o deputado do exercício quando não há descrição de entrada/saída.
FORA = {"SUPLENCIA", "Licença", "VACANCIA", "FIM_MANDATO", "SUSPENSO", "Afastado"}


@dataclass
class Evento:
    t: str          # data-hora ISO com segundos
    situacao: str
    descricao: str
    partido: str | None
    uf: str | None
    exercicio: bool = False


@dataclass
class Deputado:
    id: int
    nome: str
    uf: str
    eventos: list[Evento] = field(default_factory=list)
    _tempos: list[str] = field(default_factory=list, repr=False)
    nomes: set[str] = field(default_factory=set, repr=False)  # todos os nomes que já usou

    def em(self, t: str) -> Evento | None:
        """Último evento com data-hora <= t."""
        i = bisect.bisect_right(self._tempos, t) - 1
        return self.eventos[i] if i >= 0 else None

    def exerceu_entre(self, ini: str, fim: str) -> bool:
        """Esteve em exercício em algum momento entre ini e fim (datas-hora ISO)."""
        e = self.em(ini)
        if e is not None and e.exercicio:
            return True
        i = bisect.bisect_right(self._tempos, ini)
        j = bisect.bisect_right(self._tempos, fim)
        return any(ev.exercicio for ev in self.eventos[i:j])

    def partido_em(self, t: str) -> str | None:
        """Partido no instante t; antes do primeiro registro, o primeiro partido conhecido."""
        e = self.em(t)
        return (e.partido if e else None) or self.primeiro_partido

    @property
    def primeiro_partido(self) -> str | None:
        return self.eventos[0].partido if self.eventos else None


def _t(data_hora: str) -> str:
    return data_hora + ":00" if len(data_hora) == 16 else data_hora


def montar_deputado(dep_id: int, historico: list[dict]) -> Deputado:
    """Ordena o histórico e marca, evento a evento, se o deputado estava em exercício.

    Entrada/Saída na descrição definem o estado; alteração de partido o mantém; sem
    descrição clara, vale a situação (Exercício entra, licença/suplência/fim de mandato sai).
    """
    validos = [(i, r) for i, r in enumerate(historico) if r.get("situacao") is not None and r.get("dataHora")]
    validos.sort(key=lambda x: (_t(x[1]["dataHora"]), x[0]))
    eventos, ex = [], False
    for _, r in validos:
        sit, desc = r["situacao"], str(r.get("descricaoStatus") or "")
        if desc.startswith("Entrada"):
            ex = True
        elif desc.startswith("Saída"):
            ex = False
        elif desc.startswith("Alteração de partido"):
            pass
        elif sit == "Exercício":
            ex = True
        elif sit in FORA:
            ex = False
        eventos.append(Evento(_t(r["dataHora"]), sit, desc, r.get("siglaPartido"), r.get("siglaUf"), ex))
    com_data = sorted((r for r in historico if r.get("dataHora")), key=lambda r: r["dataHora"])
    ultimo = com_data[-1] if com_data else {}
    nome = ultimo.get("nome") or ultimo.get("nomeEleitoral") or ""
    nomes = {str(r.get(k)) for r in historico for k in ("nome", "nomeEleitoral") if r.get(k)}
    return Deputado(dep_id, nome, ultimo.get("siglaUf") or "", eventos, [e.t for e in eventos], nomes)


def legislaturas_no_periodo(fonte: Fonte, periodo: Periodo) -> list[int]:
    legs = fonte.api_lista("/legislaturas", {"ordem": "DESC", "ordenarPor": "id"}, ttl=30 * DIA)
    out = [int(l["id"]) for l in legs
           if str(l.get("dataFim", ""))[:10] >= periodo.ini and str(l.get("dataInicio", ""))[:10] < periodo.fim_excl]
    log.info("legislaturas no período: %s", out)
    return sorted(out)


def ids_das_legislaturas(fonte: Fonte, legislaturas: list[int]) -> set[int]:
    ids: set[int] = set()
    for leg in legislaturas:
        for d in fonte.api_lista("/deputados", {"idLegislatura": leg, "ordem": "ASC", "ordenarPor": "nome"}, ttl=20 * 3600):
            ids.add(int(d["id"]))
    return ids


def carregar_deputados(fonte: Fonte, ids: set[int]) -> dict[int, Deputado]:
    def um(dep_id: int) -> Deputado:
        j = fonte.api(f"/deputados/{dep_id}/historico", ttl=20 * 3600) or {}
        dep = montar_deputado(dep_id, j.get("dados", []))
        if not dep.nome:
            d = (fonte.api(f"/deputados/{dep_id}", ttl=7 * DIA) or {}).get("dados") or {}
            st = d.get("ultimoStatus") or {}
            dep.nome = st.get("nome") or d.get("nomeCivil") or f"Deputado {dep_id}"
            dep.uf = st.get("siglaUf") or d.get("ufNascimento") or ""
            dep.nomes |= {x for x in (st.get("nome"), d.get("nomeCivil")) if x}
        return dep

    lista = fonte.em_paralelo(um, sorted(ids))
    log.info("históricos carregados: %d", len(lista))
    return {d.id: d for d in lista}


MINUSCULAS = {"de", "da", "do", "das", "dos", "e"}


def nome_legivel(nome: str) -> str:
    """Nomes que vêm todos em maiúsculas passam para iniciais maiúsculas."""
    if nome != nome.upper():
        return nome
    partes = nome.lower().split()
    return " ".join(p if (p in MINUSCULAS and i) else p[:1].upper() + p[1:] for i, p in enumerate(partes))
