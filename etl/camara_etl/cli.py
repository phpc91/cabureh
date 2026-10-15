"""Linha de comando: `python -m camara_etl build --out web/public/data`."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from . import atividade, cotas, emendas, pauta, senado
from .carga import carregar_eventos, carregar_projetos, carregar_votacoes, carregar_votos
from .deputados import carregar_deputados, ids_das_legislaturas, legislaturas_no_periodo
from .fonte import Fonte, FonteIndisponivel
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


def construir_senado(args, fonte, periodo, legislaturas, deputados, out: Path) -> dict:
    """Gera data/senado/. Se algo falhar, o painel da Câmara é publicado mesmo assim."""
    nomes_dep = {emendas.norm(n) for d in deputados.values() for n in (d.nomes | {d.nome}) if n}
    tmp = out / ".senado-tmp"
    try:
        sn = senado.montar(fonte, periodo, legislaturas, nomes_dep, com_cotas=not args.sem_cotas, com_emendas=not args.sem_emendas)
    except Exception as e:  # noqa: BLE001
        log.exception("Senado indisponível nesta atualização")
        return {"erro": str(e)}
    if sn.problemas:
        log.error("dados do Senado suspeitos, não publicados: %s", "; ".join(sn.problemas))
        return {"erro": "; ".join(sn.problemas)}
    shutil.rmtree(tmp, ignore_errors=True)
    for nome, (linhas, colunas) in sn.arquivos.items():
        escrever_csv(tmp / nome, linhas, colunas)
    meta = {"gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "periodo": {"inicio": periodo.ini, "fim": periodo.fim.isoformat()}, **sn.meta}
    (tmp / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    shutil.rmtree(out / "senado", ignore_errors=True)
    tmp.rename(out / "senado")
    return {k: sn.meta[k] for k in ("presenca", "ultima_votacao") if k in sn.meta}


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

    resumo_emendas = None
    if not args.sem_emendas:
        try:
            em = emendas.montar(fonte, periodo, deputados, emendas.carregar_senadores(fonte, legislaturas))
            escrever_csv(out / "emendas.csv", em.emendas,
                         ["id_deputado", "ano", "partido", "tipo", "area", "uf_destino", "emendas", "empenhado", "pago"])
            escrever_csv(out / "emendas-destinos.csv", em.destinos, ["id_deputado", "ano", "destino", "uf", "empenhado", "pago"])
            escrever_csv(out / "emendas-mes.csv", em.meses, ["id_deputado", "mes", "partido", "tipo", "valor"])
            escrever_csv(out / "emendas-favorecidos.csv", em.favorecidos,
                         ["id_deputado", "ano", "favorecido", "documento", "natureza", "uf", "municipio", "valor", "pagamentos"])
            escrever_csv(out / "emendas-tipos.csv", em.tipos, ["ano", "tipo", "emendas", "empenhado", "pago"])
            resumo_emendas = em.resumo
        except (FonteIndisponivel, FileNotFoundError, ValueError, KeyError) as e:
            # o Portal fora do ar não deve impedir a atualização do resto do painel
            log.error("emendas indisponíveis nesta atualização: %s", e)
            resumo_emendas = {"erro": str(e)}

    resumo_senado = None
    if not args.sem_senado:
        resumo_senado = construir_senado(args, fonte, periodo, legislaturas, deputados, out)

    meta_saida = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "periodo": {"inicio": periodo.ini, "fim": periodo.fim.isoformat()},
        "ultima_sessao": ativ.sessoes[-1][1][:10] if ativ.sessoes else None,
        "ultima_votacao": pt.resumo.get("ultima_votacao"),
        "presenca": ativ.resumo,
        "pauta": pt.resumo,
        "cotas": resumo_cotas,
        "emendas": resumo_emendas,
        "senado": resumo_senado,
        "duracao_s": round(time.time() - inicio_execucao),
    }
    (out / "meta.json").write_text(json.dumps(meta_saida, ensure_ascii=False, indent=1))
    log.info("pronto em %ds", meta_saida["duracao_s"])

    # Barreira contra publicar um painel vazio se alguma fonte da Câmara vier quebrada
    problemas = []
    if ativ.resumo["sessoes"] < 50:
        problemas.append(f"poucas sessões deliberativas ({ativ.resumo['sessoes']})")
    if ativ.resumo["votacoes_nominais"] < 100:
        problemas.append(f"poucas votações nominais ({ativ.resumo['votacoes_nominais']})")
    if ativ.resumo["deputados"] < 400:
        problemas.append(f"poucos deputados ({ativ.resumo['deputados']})")
    if resumo_cotas is not None and resumo_cotas["total"] <= 0:
        problemas.append("cota parlamentar sem valores")
    if resumo_emendas and "erro" not in resumo_emendas and resumo_emendas["deputados"] < 300:
        problemas.append(f"poucos deputados com emendas ({resumo_emendas['deputados']})")
    if problemas:
        log.error("dados suspeitos, nada será publicado: %s", "; ".join(problemas))
        return 1
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
    b.add_argument("--sem-senado", action="store_true", help="não gera os dados do Senado")
    b.add_argument("--sem-emendas", action="store_true", help="não processa as emendas parlamentares")
    b.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return build(args)


if __name__ == "__main__":
    sys.exit(main())
