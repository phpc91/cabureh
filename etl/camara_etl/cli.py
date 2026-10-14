"""Linha de comando: `python -m camara_etl build --out web/public/data`."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from . import atividade, cotas, pauta
from .carga import carregar_eventos, carregar_projetos, carregar_votacoes, carregar_votos
from .deputados import carregar_deputados, ids_das_legislaturas, legislaturas_no_periodo
from .fonte import Fonte
from .periodo import periodo_padrao

log = logging.getLogger("camara_etl")


def escrever_csv(caminho: Path, linhas: list[dict], colunas: list[str]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)
    tmp.replace(caminho)
    log.info("escrito %s (%d linhas, %.0f KB)", caminho.name, len(linhas), caminho.stat().st_size / 1024)


def build(args: argparse.Namespace) -> int:
    inicio_execucao = time.time()
    periodo = periodo_padrao(args.anos, date.fromisoformat(args.fim) if args.fim else None)
    log.info("período: %s a %s", periodo.inicio, periodo.fim)
    fonte = Fonte(Path(args.cache), offline=args.offline, workers=args.workers)
    out = Path(args.out)

    legislaturas = legislaturas_no_periodo(fonte, periodo)
    eventos, presencas = carregar_eventos(fonte, periodo)
    meta = carregar_votacoes(fonte, periodo)
    votos = carregar_votos(fonte, periodo, meta)
    projetos = carregar_projetos(fonte, periodo)

    ids = ids_das_legislaturas(fonte, legislaturas)
    extras = {d for i, e in eventos.items() if periodo.contem(e.inicio) for d in presencas.get(i, ())} - ids
    log.info("deputados das legislaturas: %d; outros presentes em eventos: %d", len(ids), len(extras))
    ids |= extras
    deputados = carregar_deputados(fonte, ids)

    ativ = atividade.montar(periodo, deputados, ids, eventos, presencas, votos, projetos)
    escrever_csv(out / "presenca.csv", ativ.linhas,
                 ["id_deputado", "deputado", "uf", "partido", "mes", *atividade.CAMPOS])

    pt = pauta.montar(fonte, periodo, meta, votos)
    escrever_csv(out / "pauta.csv", pt.pauta, list(pt.pauta[0].keys()) if pt.pauta else ["id_votacao"])
    escrever_csv(out / "partidos-votacao.csv", pt.partidos,
                 ["id_votacao", "partido", "sim", "nao", "abstencoes", "obstrucoes", "outros", "orientacao"])
    escrever_csv(out / "alinhamento.csv", pt.alinhamento,
                 ["id_deputado", "mes", "partido", "votos", "base_bancada", "com_bancada", "base_governo",
                  "com_governo", "obstrucoes", "obst_orientadas", "obst_bancada", "obst_isoladas"])

    resumo_cotas = None
    if not args.sem_cotas:
        ct = cotas.montar(fonte, periodo)
        escrever_csv(out / "gastos-mes.csv", ct.meses, ["id_deputado", "mes", "partido", "valor", "documentos"])
        escrever_csv(out / "gastos-categoria.csv", ct.categorias, ["id_deputado", "ano", "partido", "categoria", "valor"])
        escrever_csv(out / "fornecedores.csv", ct.fornecedores,
                     ["id_deputado", "ano", "fornecedor", "documento", "categoria", "valor", "documentos"])
        resumo_cotas = ct.resumo

    meta_saida = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "periodo": {"inicio": periodo.ini, "fim": periodo.fim.isoformat()},
        "ultima_sessao": ativ.sessoes[-1][1][:10] if ativ.sessoes else None,
        "ultima_votacao": pt.resumo.get("ultima_votacao"),
        "presenca": ativ.resumo,
        "pauta": pt.resumo,
        "cotas": resumo_cotas,
        "duracao_s": round(time.time() - inicio_execucao),
    }
    (out / "meta.json").write_text(json.dumps(meta_saida, ensure_ascii=False, indent=1))
    log.info("pronto em %ds", meta_saida["duracao_s"])
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="camara_etl", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="baixa as fontes e gera os arquivos do painel")
    b.add_argument("--out", default="../web/public/data", help="pasta de saída")
    b.add_argument("--cache", default=".cache", help="pasta de cache dos downloads")
    b.add_argument("--anos", type=int, default=4, help="tamanho da janela, em anos")
    b.add_argument("--fim", help="último dia do período (AAAA-MM-DD); padrão: hoje")
    b.add_argument("--workers", type=int, default=6, help="chamadas simultâneas à API")
    b.add_argument("--offline", action="store_true", help="usa só o cache, sem rede")
    b.add_argument("--sem-cotas", action="store_true", help="não processa a cota parlamentar")
    b.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return build(args)


if __name__ == "__main__":
    sys.exit(main())
