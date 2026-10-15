"""Senado Federal: presença, votos, pauta, projetos, cota (CEAPS) e emendas.

Gera os mesmos arquivos da Câmara, numa pasta própria, para o painel trocar de casa sem
mudar de formato. Diferenças de fonte:

- O Senado não publica lista de presença por sessão. A presença é deduzida das votações
  nominais: em cada uma, todos os senadores em exercício aparecem com o voto ou com o motivo
  de não ter votado (atividade parlamentar, missão, licença, "não compareceu"...). Uma sessão
  conta como presença quando o senador votou ou registrou presença em ao menos uma votação
  nominal dela; senão, vale o motivo informado, e "não compareceu" prevalece sobre os demais.
- Em votações secretas só se sabe que o senador votou, não o voto.
- Não há registro de presença em comissões; entram as votações em comissões.
- O tema das matérias vem da classificação da Câmara, pela numeração única dos projetos.
"""

from __future__ import annotations

import bisect
import csv
import io
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import cotas, emendas
from .emendas import norm
from .fonte import DIA, Fonte
from .pauta import etapa, limpar_ementa
from .periodo import Periodo

log = logging.getLogger(__name__)

PRESENTE = {"Sim", "Não", "Abstenção", "Votou", "P-NRV", "Obstrução", "P-OD"}
VOTO_CAMPO = {"Sim": "votou_sim", "Não": "votou_nao", "Abstenção": "abstencao", "Obstrução": "obstrucao", "P-OD": "obstrucao"}
TIPOS_VOTO = ["Sim", "Não", "Abstenção", "Obstrução"]
# Fora do exercício naquela votação: não conta como esperado
NAO_ESPERADO = {"AFO", "EP", "EPR", "LCS", "FAL", "CAS", "DJ", "DIS", "IMP", "NA", "NH"}
MOTIVOS = {
    "AP": "Atividade parlamentar",
    "MIS": "Missão oficial", "L1": "Missão oficial", "L4": "Missão oficial", "L6": "Missão oficial", "MER": "Missão oficial",
    "LS": "Licença saúde", "L2": "Licença saúde", "LSP": "Licença saúde", "LAF": "Licença saúde", "GR": "Licença saúde",
    "LP": "Licença particular", "L3": "Licença particular", "LPA": "Licença particular",
    "NCom": "Não compareceu",
}
OUTROS_MOTIVOS = "Outros motivos"
NAO_COMPARECEU = "Não compareceu"
TIPOS_PROJETO = {"PL", "PLP", "PEC", "PDL", "PRS"}
TEMA_FIXO = {"MSF": "Indicação de autoridades", "OFS": "Indicação de autoridades", "RQS": "Requerimentos",
             "REQ": "Requerimentos", "PRS": "Resoluções do Senado"}
TIPOS_CAMARA = {"PL", "PLP", "PEC", "PDL", "MPV"}
ORIENTACAO = {"SIM": "Sim", "NAO": "Não", "ABSTENCAO": "Abstenção", "OBSTRUCAO": "Obstrução"}
APELIDO_PARTIDO = {"REPUBLICA": "REPUBLICANOS", "PROGRESSISTAS": "PP", "PODE": "PODEMOS", "UNIAO BRASIL": "UNIAO"}
SEM_PARTIDO = "Sem partido"


def presidente(cod: str) -> bool:
    return (cod or "").startswith("Presidente")


def motivo(cod: str) -> str:
    return MOTIVOS.get(cod, OUTROS_MOTIVOS)


def partido_norm(p: str) -> str:
    n = norm(p)
    return APELIDO_PARTIDO.get(n, n)


# ------------------------------------------------------------------ senadores
@dataclass
class Senador:
    id: int
    nome: str = ""
    uf: str = ""
    nomes: set[str] = field(default_factory=set)
    _datas: list[str] = field(default_factory=list, repr=False)      # datas (AAAA-MM-DD) em que aparece em votações
    _partidos: list[str] = field(default_factory=list, repr=False)
    partido_lista: str = ""

    def registrar(self, data: str, partido: str, nome: str, uf: str) -> None:
        i = bisect.bisect_right(self._datas, data)
        self._datas.insert(i, data)
        self._partidos.insert(i, partido)
        if i == len(self._datas) - 1:
            self.nome, self.uf = nome or self.nome, uf or self.uf
        if nome:
            self.nomes.add(nome)

    def exerceu_entre(self, ini: str, fim: str) -> bool:
        i = bisect.bisect_left(self._datas, ini[:10])
        return i < len(self._datas) and self._datas[i] <= fim[:10]

    def partido_em(self, t: str) -> str:
        i = bisect.bisect_right(self._datas, t[:10]) - 1
        if i >= 0 and self._partidos[i]:
            return self._partidos[i]
        if self._partidos:
            return next((p for p in self._partidos if p), "") or self.partido_lista or SEM_PARTIDO
        return self.partido_lista or SEM_PARTIDO


def _lista(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


# ------------------------------------------------------------------ carga
def _intervalos(ini: date, fim: date):
    """Fatias de no máximo um ano civil (limite da API de votações)."""
    for ano in range(ini.year, fim.year + 1):
        yield max(ini, date(ano, 1, 1)), min(fim, date(ano, 12, 31))


def _ttl(fim_fatia: date) -> float:
    return 30 * DIA if fim_fatia < date.today() - timedelta(days=60) else 20 * 3600


def carregar_votacoes(fonte: Fonte, ini: date, fim: date) -> list[dict]:
    out = []
    for a, b in _intervalos(ini, fim):
        j = fonte.senado("/votacao", {"dataInicio": a.isoformat(), "dataFim": b.isoformat()}, ttl=_ttl(b)) or []
        n = 0
        for v in j:
            if v.get("casaSessao") not in (None, "SF") or not v.get("dataSessao"):
                continue
            out.append(v)
            n += 1
        log.info("votações do Senado %s a %s: %d", a, b, n)
    vistos, unicas = set(), []
    for v in sorted(out, key=lambda v: (v["dataSessao"], v.get("sequencialVotacao") or 0)):
        k = v.get("sequencialVotacao") or (v.get("codigoSessao"), v.get("descricaoVotacao"))
        if k not in vistos:
            vistos.add(k)
            unicas.append(v)
    return unicas


def carregar_orientacoes(fonte: Fonte, ini: date, fim: date) -> dict[int, dict[str, str]]:
    """sequencialVotacao -> {partido normalizado ou GOVERNO/OPOSICAO: Sim/Não/Abstenção/Obstrução}."""
    out: dict[int, dict[str, str]] = {}
    for a, b in _intervalos(ini, fim):
        j = fonte.senado(f"/plenario/votacao/orientacaoBancada/{a:%Y%m%d}/{b:%Y%m%d}", ttl=_ttl(b)) or {}
        for v in j.get("votacoes") or []:
            o = out.setdefault(v.get("sequencialVotacao"), {})
            for x in v.get("orientacoesLideranca") or []:
                voto = ORIENTACAO.get(norm(x.get("voto") or ""))
                if voto and x.get("partido"):
                    o[partido_norm(x["partido"])] = voto
    return out


def carregar_lista(fonte: Fonte, legislaturas: list[int]) -> list[dict]:
    if not legislaturas:
        return []
    j = fonte.senado(f"/senador/lista/legislatura/{min(legislaturas)}/{max(legislaturas)}", ttl=7 * DIA) or {}
    try:
        return _lista(j["ListaParlamentarLegislatura"]["Parlamentares"]["Parlamentar"])
    except (KeyError, TypeError):
        return []


def primeiro_autor(autoria: str) -> str:
    """'Senador Romário (PL/RJ), Senadora X (...)' -> 'ROMARIO'."""
    p = (autoria or "").split(",")[0]
    p = re.sub(r"\(.*?\)", "", p)
    p = re.sub(r"^\s*Senador[a]?\s+", "", p.strip(), flags=re.I)
    return norm(p)


def carregar_projetos(fonte: Fonte, periodo: Periodo, sen: Senador) -> list[tuple[str, bool]]:
    """(data de apresentação, é o primeiro autor) dos projetos assinados pelo senador."""
    j = fonte.senado("/processo", {"codigoParlamentarAutor": sen.id, "dataInicioApresentacao": periodo.ini,
                                   "dataFimApresentacao": periodo.fim.isoformat()}, ttl=20 * 3600) or []
    nomes = {norm(n) for n in sen.nomes | {sen.nome}}
    out, vistos = [], set()
    for p in j:
        sigla = (p.get("identificacao") or "").split(" ")[0]
        if sigla not in TIPOS_PROJETO or p.get("id") in vistos or not p.get("dataApresentacao"):
            continue
        vistos.add(p.get("id"))
        out.append((p["dataApresentacao"][:10], primeiro_autor(p.get("autoria")) in nomes))
    return out


def carregar_votos_comissao(fonte: Fonte, periodo: Periodo, sen_id: int) -> list[str]:
    datas = []
    for a, b in _intervalos(periodo.inicio, periodo.fim):
        j = fonte.senado(f"/votacaoComissao/parlamentar/{sen_id}", {"dataInicio": f"{a:%Y%m%d}", "dataFim": f"{b:%Y%m%d}"}, ttl=_ttl(b)) or {}
        try:
            vs = _lista(j["VotacoesComissao"]["Votacoes"]["Votacao"])
        except (KeyError, TypeError):
            vs = []
        datas.extend(str(v.get("DataHoraInicioReuniao") or "")[:10] for v in vs if v.get("DataHoraInicioReuniao"))
    return datas


def carregar_temas(fonte: Fonte, chaves: list[tuple[str, str, str]]) -> dict[tuple, list[str]]:
    """Temas da classificação da Câmara para (sigla, número, ano), pela numeração única dos projetos."""
    def um(k):
        sigla, numero, ano = k
        j = fonte.api("/proposicoes", {"siglaTipo": sigla, "numero": numero, "ano": ano}, ttl=30 * DIA) or {}
        dados = j.get("dados") or []
        if not dados:
            return []
        t = fonte.api(f"/proposicoes/{dados[0]['id']}/temas", ttl=30 * DIA) or {}
        return [x["tema"] for x in t.get("dados", [])]
    return dict(zip(chaves, fonte.em_paralelo(um, chaves)))


# ------------------------------------------------------------------ montar
@dataclass
class SaidaSenado:
    arquivos: dict[str, tuple[list[dict], list[str]]]
    meta: dict
    problemas: list[str]


CAMPOS = ["sessoes", "presencas", "votacoes", "votou_sim", "votou_nao", "abstencao", "obstrucao", "outros_votos",
          "votos_comissoes", "eventos_comissoes", "projetos_autor", "projetos_coautor"]


def montar(fonte: Fonte, periodo: Periodo, legislaturas: list[int], nomes_deputados: set[str],
           com_cotas: bool = True, com_emendas: bool = True) -> SaidaSenado:
    anos = [int(a) for a in periodo.anos]
    ini_roster = date(anos[0] - 1, 7, 1)          # exercício anterior ao período, para ligar emendas
    votacoes = carregar_votacoes(fonte, ini_roster, periodo.fim)
    no_periodo = [v for v in votacoes if periodo.contem(v["dataSessao"] + "T12:00:00")]

    sens: dict[int, Senador] = {}
    for v in votacoes:
        for x in v.get("votos") or []:
            cod = x.get("codigoParlamentar")
            if cod is None:
                continue
            s = sens.get(cod) or sens.setdefault(cod, Senador(int(cod)))
            if x.get("siglaVotoParlamentar") not in NAO_ESPERADO:
                s.registrar(v["dataSessao"], x.get("siglaPartidoParlamentar") or "", x.get("nomeParlamentar") or "", x.get("siglaUFParlamentar") or "")
    for p in carregar_lista(fonte, legislaturas):
        ident = p.get("IdentificacaoParlamentar") or {}
        try:
            cod = int(ident.get("CodigoParlamentar"))
        except (TypeError, ValueError):
            continue
        s = sens.get(cod) or sens.setdefault(cod, Senador(cod))
        for k in ("NomeParlamentar", "NomeCompletoParlamentar"):
            if ident.get(k):
                s.nomes.add(ident[k])
        s.nome = s.nome or ident.get("NomeParlamentar") or ""
        s.uf = s.uf or ident.get("UfParlamentar") or ""
        s.partido_lista = ident.get("SiglaPartidoParlamentar") or ""
    log.info("senadores conhecidos: %d", len(sens))

    # --- presença por sessão e votos
    lin: dict[tuple, Counter] = defaultdict(Counter)
    aus: dict[tuple, int] = defaultdict(int)
    por_sessao: dict[int, list[dict]] = defaultdict(list)
    for v in no_periodo:
        por_sessao[v.get("codigoSessao")].append(v)
    sessoes_meta = []
    for cs, vs in por_sessao.items():
        data = vs[0]["dataSessao"]
        mes = data[:7]
        sessoes_meta.append(data)
        estado: dict[int, dict] = {}
        for v in vs:
            for x in v.get("votos") or []:
                cod, sig = x.get("codigoParlamentar"), x.get("siglaVotoParlamentar") or ""
                if cod is None or sig in NAO_ESPERADO:
                    continue
                e = estado.setdefault(cod, {"partido": x.get("siglaPartidoParlamentar") or SEM_PARTIDO, "presente": False, "motivos": Counter()})
                c = lin[(cod, mes, e["partido"])]
                c["votacoes"] += 1
                if sig in VOTO_CAMPO:
                    c[VOTO_CAMPO[sig]] += 1
                elif sig == "Votou" or presidente(sig):
                    c["outros_votos"] += 1
                if sig in PRESENTE or presidente(sig):
                    e["presente"] = True
                else:
                    e["motivos"][motivo(sig)] += 1
        for cod, e in estado.items():
            c = lin[(cod, mes, e["partido"])]
            c["sessoes"] += 1
            if e["presente"]:
                c["presencas"] += 1
            else:
                m = NAO_COMPARECEU if e["motivos"][NAO_COMPARECEU] else (e["motivos"].most_common(1)[0][0] if e["motivos"] else OUTROS_MOTIVOS)
                aus[(cod, mes, e["partido"], m)] += 1
    ativos = {k[0] for k in lin}

    # --- projetos e votos em comissões (só de quem esteve em exercício no período)
    def extras(cod):
        s = sens[cod]
        return cod, carregar_projetos(fonte, periodo, s), carregar_votos_comissao(fonte, periodo, cod)
    for cod, projetos, comissao in fonte.em_paralelo(extras, sorted(ativos)):
        s = sens[cod]
        for data, primeiro in projetos:
            lin[(cod, data[:7], s.partido_em(data) or SEM_PARTIDO)]["projetos_autor" if primeiro else "projetos_coautor"] += 1
        for data in comissao:
            if periodo.contem(data + "T12:00:00"):
                lin[(cod, data[:7], s.partido_em(data) or SEM_PARTIDO)]["votos_comissoes"] += 1

    meses_validos = set(periodo.meses)
    linhas = []
    for (cod, mes, partido), c in sorted(lin.items()):
        if mes not in meses_validos or cod not in ativos:
            continue
        s = sens[cod]
        linhas.append({"id_deputado": cod, "deputado": s.nome, "uf": s.uf, "partido": partido or SEM_PARTIDO, "mes": mes,
                       **{k: c[k] for k in CAMPOS}})
    ausencias = [{"id_deputado": cod, "mes": mes, "partido": p, "motivo": m, "sessoes": n} for (cod, mes, p, m), n in sorted(aus.items())]

    # --- pauta, votos por partido e alinhamento
    orient = carregar_orientacoes(fonte, periodo.inicio, periodo.fim)
    temas_chaves = sorted({(v.get("sigla"), str(v.get("numero")), str(v.get("ano"))) for v in no_periodo if v.get("sigla") in TIPOS_CAMARA})
    temas = carregar_temas(fonte, temas_chaves)
    pauta, partidos, alin = [], [], {}
    for v in no_periodo:
        vid = str(v.get("sequencialVotacao") or v.get("codigoSessaoVotacao"))
        om = orient.get(v.get("sequencialVotacao"), {})
        secreta = v.get("votacaoSecreta") == "S"
        por_part: dict[str, Counter] = defaultdict(Counter)
        for x in v.get("votos") or []:
            sig = x.get("siglaVotoParlamentar") or ""
            if sig in NAO_ESPERADO:
                continue
            P = x.get("siglaPartidoParlamentar") or SEM_PARTIDO
            ch = "Obstrução" if sig == "P-OD" else sig
            if ch in TIPOS_VOTO:
                por_part[P][ch] += 1
                por_part[P]["n"] += 1
            elif sig == "Votou" or presidente(sig):
                por_part[P]["outro"] += 1
        sigla = v.get("sigla") or ""
        ts = TEMA_FIXO.get(sigla) and [TEMA_FIXO[sigla]] or temas.get((sigla, str(v.get("numero")), str(v.get("ano"))), [])
        tot = Counter()
        for c in por_part.values():
            tot.update(c)
        pauta.append({
            "id_votacao": vid, "data": v["dataSessao"], "proposicao": v.get("identificacao") or "",
            "id_proposicao": v.get("codigoMateria") or "", "tipo": sigla, "ementa": limpar_ementa(v.get("ementa") or ""),
            "tema": ts[0] if ts else "Sem tema", "temas": "; ".join(ts), "etapa": etapa(v.get("descricaoVotacao") or ""),
            "votacao": re.sub(r"\s+", " ", v.get("descricaoVotacao") or "")[:260], "aprovada": 1 if v.get("resultadoVotacao") == "A" else 0,
            "sim": v.get("totalVotosSim") or tot["Sim"], "nao": v.get("totalVotosNao") or tot["Não"],
            "abstencoes": v.get("totalVotosAbstencao") or tot["Abstenção"], "obstrucoes": tot["Obstrução"],
            "votos": tot["n"] + tot["outro"], "orient_governo": om.get("GOVERNO", ""), "orient_oposicao": om.get("OPOSICAO", ""),
            "secreta": 1 if secreta else 0,
        })
        for P, c in por_part.items():
            partidos.append({"id_votacao": vid, "partido": P, "sim": c["Sim"], "nao": c["Não"], "abstencoes": c["Abstenção"],
                             "obstrucoes": c["Obstrução"], "outros": c["outro"], "orientacao": om.get(partido_norm(P), "")})
        if secreta:
            continue
        g = om.get("GOVERNO")
        mes = v["dataSessao"][:7]
        for x in v.get("votos") or []:
            sig = x.get("siglaVotoParlamentar") or ""
            voto = "Obstrução" if sig == "P-OD" else sig
            if voto not in TIPOS_VOTO:
                continue
            P = x.get("siglaPartidoParlamentar") or SEM_PARTIDO
            k = (x["codigoParlamentar"], mes, P)
            a = alin.get(k)
            if a is None:
                a = alin[k] = {"id_deputado": x["codigoParlamentar"], "mes": mes, "partido": P, "votos": 0, "base_bancada": 0,
                               "com_bancada": 0, "base_governo": 0, "com_governo": 0, "obstrucoes": 0, "obst_orientadas": 0,
                               "obst_bancada": 0, "obst_isoladas": 0}
            a["votos"] += 1
            c = por_part[P]
            if c["n"] >= 3 and P != SEM_PARTIDO:
                a["base_bancada"] += 1
                if voto == max(TIPOS_VOTO, key=lambda t: c[t]):
                    a["com_bancada"] += 1
            if g in ("Sim", "Não"):
                a["base_governo"] += 1
                if voto == g:
                    a["com_governo"] += 1
            if voto == "Obstrução":
                a["obstrucoes"] += 1
                if om.get(partido_norm(P)) == "Obstrução":
                    a["obst_orientadas"] += 1
                elif c["n"] >= 3 and c["Obstrução"] / c["n"] >= 0.5:
                    a["obst_bancada"] += 1
                else:
                    a["obst_isoladas"] += 1
    pauta.sort(key=lambda r: (r["data"], r["id_votacao"]))
    alinhamento = sorted(alin.values(), key=lambda r: (r["id_deputado"], r["mes"], r["partido"]))

    arquivos = {
        "presenca.csv": (linhas, ["id_deputado", "deputado", "uf", "partido", "mes", *CAMPOS]),
        "ausencias.csv": (ausencias, ["id_deputado", "mes", "partido", "motivo", "sessoes"]),
        "pauta.csv": (pauta, ["id_votacao", "data", "proposicao", "id_proposicao", "tipo", "ementa", "tema", "temas", "etapa",
                              "votacao", "aprovada", "sim", "nao", "abstencoes", "obstrucoes", "votos", "orient_governo",
                              "orient_oposicao", "secreta"]),
        "partidos-votacao.csv": (partidos, ["id_votacao", "partido", "sim", "nao", "abstencoes", "obstrucoes", "outros", "orientacao"]),
        "alinhamento.csv": (alinhamento, ["id_deputado", "mes", "partido", "votos", "base_bancada", "com_bancada", "base_governo",
                                          "com_governo", "obstrucoes", "obst_orientadas", "obst_bancada", "obst_isoladas"]),
    }
    motivos_tot = Counter()
    for (_, _, _, m), n in aus.items():
        motivos_tot[m] += n
    meta = {
        "presenca": {"sessoes": len(por_sessao), "votacoes_nominais": len(no_periodo),
                     "votacoes_secretas": sum(r["secreta"] for r in pauta), "senadores": len(ativos),
                     "sessoes_esperadas": sum(r["sessoes"] for r in linhas), "presencas": sum(r["presencas"] for r in linhas),
                     "ausencias_por_motivo": dict(motivos_tot.most_common()),
                     "projetos_autor": sum(r["projetos_autor"] for r in linhas), "votos_comissoes": sum(r["votos_comissoes"] for r in linhas)},
        "pauta": {"votacoes": len(pauta), "sem_tema": sum(r["tema"] == "Sem tema" for r in pauta),
                  "com_orientacao_governo": sum(bool(r["orient_governo"]) for r in pauta)},
        "ultima_sessao": max(sessoes_meta) if sessoes_meta else None,
        "ultima_votacao": pauta[-1]["data"] if pauta else None,
    }

    # --- cota (CEAPS)
    if com_cotas:
        indice: dict[str, set[int]] = defaultdict(set)
        for s in sens.values():
            for n in s.nomes | {s.nome}:
                if n:
                    indice[norm(n)].add(s.id)
        sem_dono: Counter = Counter()
        toks = [(s.id, emendas.tokens(norm(n))) for s in sens.values() for n in s.nomes | {s.nome} if n]
        achados: dict[str, set[int]] = {}

        def achar(nome: str) -> set[int]:
            """Nome igual; senão, palavras de um contidas nas do outro (≥2 palavras), com candidato único."""
            if nome in achados:
                return achados[nome]
            n = norm(nome)
            ids = indice.get(n, set())
            if not ids:
                t = emendas.tokens(n)
                ids = {i for i, d in toks if len(t) >= 2 and len(d) >= 2 and (t <= d or d <= t)}
            achados[nome] = ids
            return ids

        def registros():
            for ano in anos:
                arq = fonte.ceaps(ano)
                if arq is None:
                    continue
                with open(arq, encoding="latin-1", newline="") as f:
                    texto = f.read()
                ini = texto.find('"ANO"')        # a primeira linha traz a data de atualização
                leitor = csv.DictReader(io.StringIO(texto[max(ini, 0):], newline=""), delimiter=";")
                for r in leitor:
                    ids = achar(r.get("SENADOR") or "")
                    v = emendas.valor(r.get("VALOR_REEMBOLSADO"))
                    if len(ids) != 1:
                        sem_dono[r.get("SENADOR") or ""] += v
                        continue
                    cod = next(iter(ids))
                    try:
                        comp = f"{int(r['ANO'])}-{int(r['MES']):02d}"
                    except (KeyError, ValueError):
                        continue
                    yield cod, comp, sens[cod].partido_em(comp + "-28") or SEM_PARTIDO, r.get("TIPO_DESPESA") or "", \
                        r.get("FORNECEDOR") or "", r.get("CNPJ_CPF") or "", v
        ct = cotas.agregar(registros(), periodo)
        ct.resumo["sem_senador_identificado"] = {k: round(v, 2) for k, v in sem_dono.most_common(10)}
        arquivos["gastos-mes.csv"] = (ct.meses, ["id_deputado", "mes", "partido", "valor", "documentos"])
        arquivos["gastos-categoria.csv"] = (ct.categorias, ["id_deputado", "ano", "partido", "categoria", "valor"])
        arquivos["fornecedores.csv"] = (ct.fornecedores, ["id_deputado", "ano", "fornecedor", "documento", "categoria", "valor", "documentos"])
        meta["cotas"] = ct.resumo
        log.info("CEAPS: %s", ct.resumo)

    # --- emendas
    if com_emendas:
        try:
            em = emendas.montar(fonte, periodo, sens, nomes_deputados)
            arquivos["emendas.csv"] = (em.emendas, ["id_deputado", "ano", "partido", "tipo", "area", "uf_destino", "emendas", "empenhado", "pago"])
            arquivos["emendas-destinos.csv"] = (em.destinos, ["id_deputado", "ano", "destino", "uf", "empenhado", "pago"])
            arquivos["emendas-mes.csv"] = (em.meses, ["id_deputado", "mes", "partido", "tipo", "valor"])
            arquivos["emendas-favorecidos.csv"] = (em.favorecidos, ["id_deputado", "ano", "favorecido", "documento", "natureza", "uf", "municipio", "valor", "pagamentos"])
            arquivos["emendas-tipos.csv"] = (em.tipos, ["ano", "tipo", "emendas", "empenhado", "pago"])
            meta["emendas"] = em.resumo
        except Exception as e:  # noqa: BLE001 — o Portal fora do ar não derruba o Senado
            log.error("emendas do Senado indisponíveis: %s", e)
            meta["emendas"] = {"erro": str(e)}

    problemas = []
    if meta["presenca"]["sessoes"] < 20:
        problemas.append(f"poucas sessões com votação nominal no Senado ({meta['presenca']['sessoes']})")
    if meta["presenca"]["votacoes_nominais"] < 50:
        problemas.append(f"poucas votações nominais no Senado ({meta['presenca']['votacoes_nominais']})")
    if meta["presenca"]["senadores"] < 70:
        problemas.append(f"poucos senadores ({meta['presenca']['senadores']})")
    return SaidaSenado(arquivos, meta, problemas)
