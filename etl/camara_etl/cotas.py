"""Cota parlamentar (CEAP): gastos de gabinete reembolsados pela Câmara.

Saídas:
- gastos-mes.csv: valor por deputado, mês de competência e partido;
- gastos-categoria.csv: valor por deputado, ano, partido e categoria (só meses dentro do período);
- fornecedores.csv: os maiores fornecedores de cada deputado em cada ano.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from .fonte import Fonte, ler_csv_zip
from .periodo import Periodo

log = logging.getLogger(__name__)

COLUNAS = ["ideCadastro", "sgPartido", "txtDescricao", "txtFornecedor", "txtCNPJCPF", "vlrLiquido", "numMes", "numAno"]
MAX_FORNECEDORES = 10

# (palavras que precisam aparecer, rótulo) — a primeira regra que casa vence
CATEGORIAS = [
    (("locomoc",), "Locomoção, hospedagem e alimentação"),   # categoria agrupada do Senado
    (("passag", "aere"), "Passagens aéreas"),
    (("bilhete", "aere"), "Passagens aéreas"),
    (("passag", "terrestr"), "Passagens terrestres e fluviais"),
    (("escritorio",), "Escritório de apoio"),
    (("combust",), "Combustíveis"),
    (("divulga",), "Divulgação do mandato"),
    (("veicul",), "Aluguel de veículos"),
    (("aeronave",), "Fretamento de aeronaves"),
    (("embarca",), "Fretamento de embarcações"),
    (("telefon",), "Telefonia"),
    (("posta",), "Correios"),
    (("consultor",), "Consultorias e pesquisas"),
    (("seguranca",), "Segurança"),
    (("hosped",), "Hospedagem"),
    (("alimenta",), "Alimentação"),
    (("taxi",), "Táxi, pedágio e estacionamento"),
    (("curso",), "Cursos e eventos"),
    (("assinatura",), "Assinaturas"),
]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower()


def categoria(descricao: str) -> str:
    n = _norm(descricao)
    for palavras, rotulo in CATEGORIAS:
        if all(p in n for p in palavras):
            return rotulo
    texto = re.sub(r"[\s.]+$", "", (descricao or "").strip()).lower()
    return texto[:1].upper() + texto[1:] if texto else "Outros"


def documento(doc: str) -> str:
    """CNPJ formatado; CPF (pessoa física) não é publicado."""
    digitos = re.sub(r"\D", "", doc or "")
    if len(digitos) == 14:
        d = digitos
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(digitos) == 11:
        return "Pessoa física"
    return ""


def valor(texto: str) -> float:
    try:
        return float((texto or "0").replace(",", "."))
    except ValueError:
        return 0.0


@dataclass
class SaidaCotas:
    meses: list[dict]
    categorias: list[dict]
    fornecedores: list[dict]
    resumo: dict


def montar(fonte: Fonte, periodo: Periodo) -> SaidaCotas:
    ignoradas = 0

    def registros():
        nonlocal ignoradas
        for ano in periodo.anos:
            n = 0
            for dep, partido, desc, forn, doc, vlr, mes, ano_c in ler_csv_zip(fonte.cotas(ano), COLUNAS):
                if not dep:  # despesas de lideranças, sem deputado
                    ignoradas += 1
                    continue
                try:
                    competencia = f"{int(ano_c)}-{int(mes):02d}"
                except ValueError:
                    continue
                n += 1
                yield int(dep), competencia, partido or "Sem partido", desc, forn, doc, valor(vlr)
            log.info("cotas %d: %d despesas", ano, n)

    saida = agregar(registros(), periodo)
    saida.resumo["despesas_de_liderancas_ignoradas"] = ignoradas
    log.info("cotas: %s", saida.resumo)
    return saida


def agregar(registros, periodo: Periodo) -> SaidaCotas:
    """Agrega despesas (id, competência AAAA-MM, partido, descrição, fornecedor, CNPJ/CPF, valor)."""
    meses_validos = set(periodo.meses)
    por_mes: dict[tuple, list] = defaultdict(lambda: [0.0, 0])
    por_cat: dict[tuple, float] = defaultdict(float)
    por_forn: dict[tuple, list] = {}
    for dep_i, competencia, part, desc, forn, doc, v in registros:
        if competencia not in meses_validos:
            continue
        cat = categoria(desc)
        m = por_mes[(dep_i, competencia, part)]
        m[0] += v
        m[1] += 1
        por_cat[(dep_i, competencia[:4], part, cat)] += v
        doc_fmt = documento(doc)
        chave_forn = (dep_i, competencia[:4], doc_fmt if doc_fmt and doc_fmt != "Pessoa física" else "pf:" + (forn or "").strip().upper())
        f = por_forn.get(chave_forn)
        if f is None:
            f = por_forn[chave_forn] = [0.0, 0, (forn or "").strip(), doc_fmt, defaultdict(float)]
        f[0] += v
        f[1] += 1
        f[4][cat] += v

    meses = [{"id_deputado": d, "mes": m, "partido": p, "valor": round(v, 2), "documentos": n}
             for (d, m, p), (v, n) in sorted(por_mes.items())]
    categorias = [{"id_deputado": d, "ano": a, "partido": p, "categoria": c, "valor": round(v, 2)}
                  for (d, a, p, c), v in sorted(por_cat.items())]
    agrupado: dict[tuple, list] = defaultdict(list)
    for (d, a, _), (v, n, nome, doc, cats) in por_forn.items():
        agrupado[(d, a)].append((v, n, nome, doc, max(cats, key=cats.get)))
    fornecedores = []
    for (d, a), itens in sorted(agrupado.items()):
        for v, n, nome, doc, cat in sorted(itens, key=lambda x: -x[0])[:MAX_FORNECEDORES]:
            fornecedores.append({"id_deputado": d, "ano": a, "fornecedor": nome, "documento": doc,
                                 "categoria": cat, "valor": round(v, 2), "documentos": n})
    resumo = {"linhas_mes": len(meses), "linhas_categoria": len(categorias), "linhas_fornecedores": len(fornecedores),
              "total": round(sum(r["valor"] for r in meses), 2), "deputados": len({r["id_deputado"] for r in meses}),
              }
    return SaidaCotas(meses, categorias, fornecedores, resumo)
