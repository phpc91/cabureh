"""Acesso às fontes: arquivos anuais e API de dados abertos da Câmara, com cache em disco.

Os arquivos anuais são baixados de novo só quando o servidor indica mudança (ETag ou
Last-Modified). As respostas da API ficam em cache por um prazo que depende do recurso.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable, Iterator

import requests

log = logging.getLogger(__name__)

BASE_ARQUIVOS = "https://dadosabertos.camara.leg.br/arquivos"
BASE_API = "https://dadosabertos.camara.leg.br/api/v2"
URL_COTAS = "https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"
USER_AGENT = "presenca-camara/0.1 (+painel de dados abertos)"

csv.field_size_limit(1 << 30)

HORA = 3600
DIA = 24 * HORA


class FonteIndisponivel(RuntimeError):
    pass


class Fonte:
    """Baixa e guarda em cache os dados da Câmara."""

    def __init__(self, cache: Path, offline: bool = False, workers: int = 6):
        self.cache = Path(cache)
        self.offline = offline
        self.workers = workers
        self.sessao = requests.Session()
        self.sessao.headers["User-Agent"] = USER_AGENT
        (self.cache / "arquivos").mkdir(parents=True, exist_ok=True)
        (self.cache / "api").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ arquivos
    def arquivo(self, conjunto: str, ano: int) -> Path | None:
        """CSV anual de um conjunto (ex.: votacoesVotos, 2025). None se o ano não existe."""
        url = f"{BASE_ARQUIVOS}/{conjunto}/csv/{conjunto}-{ano}.csv"
        return self._baixar(url, self.cache / "arquivos" / f"{conjunto}-{ano}.csv")

    def cotas(self, ano: int) -> Path | None:
        """Zip anual da cota parlamentar (CEAP)."""
        return self._baixar(URL_COTAS.format(ano=ano), self.cache / "arquivos" / f"cotas-{ano}.csv.zip")

    def _baixar(self, url: str, destino: Path) -> Path | None:
        meta_path = destino.with_suffix(destino.suffix + ".meta.json")
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        if self.offline:
            return destino if destino.exists() else None
        headers = {}
        if destino.exists():
            if meta.get("etag"):
                headers["If-None-Match"] = meta["etag"]
            if meta.get("last_modified"):
                headers["If-Modified-Since"] = meta["last_modified"]
        for tentativa in range(5):
            try:
                with self.sessao.get(url, headers=headers, stream=True, timeout=(15, 300)) as r:
                    if r.status_code == 304:
                        log.info("sem mudança: %s", destino.name)
                        return destino
                    if r.status_code == 404:
                        log.info("não existe (404): %s", url)
                        return None
                    r.raise_for_status()
                    tmp = destino.with_suffix(destino.suffix + ".part")
                    with open(tmp, "wb") as f:
                        for bloco in r.iter_content(1 << 20):
                            f.write(bloco)
                    tmp.replace(destino)
                    meta_path.write_text(json.dumps({
                        "url": url,
                        "etag": r.headers.get("ETag"),
                        "last_modified": r.headers.get("Last-Modified"),
                        "baixado_em": time.time(),
                    }))
                    log.info("baixado: %s (%.1f MB)", destino.name, destino.stat().st_size / 1e6)
                    return destino
            except requests.RequestException as e:
                espera = 5 * (tentativa + 1)
                log.warning("falha ao baixar %s (%s); nova tentativa em %ss", url, e, espera)
                time.sleep(espera)
        if destino.exists():
            log.warning("usando cópia em cache de %s", destino.name)
            return destino
        raise FonteIndisponivel(url)

    # ----------------------------------------------------------------------- API
    def api(self, caminho: str, params: dict | None = None, ttl: float = DIA) -> dict | None:
        """GET na API v2 com cache em disco. None para 404."""
        params = params or {}
        chave = caminho + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
        arq = self.cache / "api" / (hashlib.sha1(chave.encode()).hexdigest() + ".json")
        if arq.exists() and (self.offline or time.time() - arq.stat().st_mtime < ttl):
            return json.loads(arq.read_text())
        if self.offline:
            raise FonteIndisponivel(chave)
        for tentativa in range(5):
            try:
                r = self.sessao.get(BASE_API + caminho, params=params, timeout=(15, 60),
                                    headers={"Accept": "application/json"})
                if r.status_code == 404:
                    dados = None
                else:
                    r.raise_for_status()
                    dados = r.json()
                arq.write_text(json.dumps(dados))
                return dados
            except (requests.RequestException, ValueError) as e:
                espera = 2 * (tentativa + 1)
                log.warning("falha na API %s (%s); nova tentativa em %ss", chave, e, espera)
                time.sleep(espera)
        if arq.exists():
            return json.loads(arq.read_text())
        raise FonteIndisponivel(chave)

    def api_lista(self, caminho: str, params: dict | None = None, ttl: float = DIA) -> list[dict]:
        """Percorre todas as páginas de um recurso paginado."""
        out, pagina = [], 1
        while True:
            j = self.api(caminho, {**(params or {}), "itens": 100, "pagina": pagina}, ttl=ttl) or {}
            dados = j.get("dados", [])
            out.extend(dados)
            if len(dados) < 100:
                return out
            pagina += 1

    def em_paralelo(self, fn: Callable, itens: Iterable) -> list:
        with ThreadPoolExecutor(self.workers) as ex:
            return list(ex.map(fn, itens))


# ------------------------------------------------------------------- leitura CSV
def ler_csv(caminho: Path | None, colunas: list[str]) -> Iterator[tuple[str, ...]]:
    """Lê um CSV da Câmara (separador ';') devolvendo só as colunas pedidas, na ordem pedida."""
    if caminho is None:
        return
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        yield from _ler(f, colunas, caminho.name)


def ler_csv_zip(caminho: Path | None, colunas: list[str]) -> Iterator[tuple[str, ...]]:
    if caminho is None:
        return
    with zipfile.ZipFile(caminho) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(nome) as bruto:
            f = io.TextIOWrapper(bruto, encoding="utf-8-sig", newline="")
            yield from _ler(f, colunas, nome)


def _ler(f, colunas: list[str], nome: str) -> Iterator[tuple[str, ...]]:
    leitor = csv.reader(f, delimiter=";")
    cab = [c.strip() for c in next(leitor)]
    faltam = [c for c in colunas if c not in cab]
    if faltam:
        raise ValueError(f"{nome}: colunas ausentes {faltam}; colunas do arquivo: {cab}")
    idx = [cab.index(c) for c in colunas]
    n = len(cab)
    for linha in leitor:
        if not linha or (len(linha) == 1 and not linha[0]):
            continue
        if len(linha) < n:
            linha = linha + [""] * (n - len(linha))
        yield tuple(linha[i] for i in idx)
