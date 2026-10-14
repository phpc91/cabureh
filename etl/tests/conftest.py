import csv
import io
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from camara_etl.fonte import Fonte  # noqa: E402


def _csv(path: Path, header: list[str], rows: list[list]) -> Path:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL)
        w.writerow(header)
        w.writerows(rows)
    return path


HISTORICOS = {
    1: [{"dataHora": "2023-02-01T00:00", "situacao": None, "descricaoStatus": "Nome no início da legislatura", "siglaPartido": "PL", "siglaUf": "SP", "nome": "FULANO DE TAL"},
        {"dataHora": "2023-02-01T12:00", "situacao": "Exercício", "descricaoStatus": "Entrada - Posse de Eleito Titular", "siglaPartido": "PL", "siglaUf": "SP", "nome": "FULANO DE TAL"}],
    2: [{"dataHora": "2023-02-01T12:00", "situacao": "SUPLENCIA", "descricaoStatus": "DIVERSO - Suplente", "siglaPartido": "PT", "siglaUf": "BA", "nome": "Beltrana Souza"},
        {"dataHora": "2025-02-01T10:00", "situacao": "Exercício", "descricaoStatus": "Entrada - Posse de Suplente", "siglaPartido": "PT", "siglaUf": "BA", "nome": "Beltrana Souza"}],
    3: [{"dataHora": "2023-02-01T12:00", "situacao": "Exercício", "descricaoStatus": "Entrada - Posse de Eleito Titular", "siglaPartido": "MDB", "siglaUf": "RJ", "nome": "Ciclano"},
        {"dataHora": "2025-03-01T00:00", "situacao": "Exercício", "descricaoStatus": "Alteração de partido", "siglaPartido": "PSD", "siglaUf": "RJ", "nome": "Ciclano"}],
}


class FonteFalsa(Fonte):
    """Fonte que lê arquivos de uma pasta de teste e responde a API a partir de dicionários."""

    def __init__(self, pasta: Path):
        super().__init__(pasta / "cache", offline=True, workers=2)
        self.pasta = pasta

    def arquivo(self, conjunto, ano):
        p = self.pasta / f"{conjunto}-{ano}.csv"
        return p if p.exists() else None

    def cotas(self, ano):
        p = self.pasta / f"cotas-{ano}.csv.zip"
        return p if p.exists() else None

    def api(self, caminho, params=None, ttl=0):
        params = params or {}
        if caminho == "/legislaturas":
            return {"dados": [{"id": 57, "dataInicio": "2023-02-01", "dataFim": "2027-01-31"},
                              {"id": 56, "dataInicio": "2019-02-01", "dataFim": "2023-01-31"}]} if params.get("pagina", 1) == 1 else {"dados": []}
        if caminho == "/deputados":
            if params.get("idLegislatura") == 57 and params.get("pagina", 1) == 1:
                return {"dados": [{"id": 1}, {"id": 2}, {"id": 3}]}
            return {"dados": []}
        if caminho.startswith("/deputados/") and caminho.endswith("/historico"):
            return {"dados": HISTORICOS.get(int(caminho.split("/")[2]), [])}
        if caminho == "/proposicoes/100/temas":
            return {"dados": [{"tema": "Economia"}, {"tema": "Finanças Públicas e Orçamento"}]}
        if caminho.startswith("/proposicoes/"):
            return {"dados": []}
        return None


@pytest.fixture
def fonte(tmp_path: Path) -> FonteFalsa:
    d = tmp_path
    _csv(d / "eventos-2025.csv", ["id", "dataHoraInicio", "descricaoTipo", "descricao"], [
        ["S1", "2025-01-15T14:00:00", "Sessão Deliberativa", "Sessão Deliberativa Extraordinária"],
        ["S2", "2025-02-10T14:00:00", "Sessão Deliberativa", "Sessão Deliberativa Extraordinária"],
        ["S3", "2025-03-10T14:00:00", "Sessão Deliberativa", "Sessão Deliberativa Extraordinária"],
        ["S4", "2025-03-11T14:00:00", "Sessão Deliberativa", "Cancelada, sem lista"],
        ["C1", "2025-02-11T10:00:00", "Reunião Deliberativa", "CCJC"],
        ["T1", "2025-02-12T10:00:00", "Teste do Painel Eletrônico", "teste"],
        ["S9", "2025-04-02T14:00:00", "Sessão Deliberativa", "fora do período"],
    ])
    _csv(d / "eventosPresencaDeputados-2025.csv", ["idEvento", "dataHoraInicio", "idDeputado"], [
        ["S1", "", "1"], ["S2", "", "1"], ["S2", "", "2"], ["S3", "", "2"], ["S3", "", "3"],
        ["C1", "", "3"], ["T1", "", "1"], ["S9", "", "1"],
    ])
    _csv(d / "votacoes-2025.csv", ["id", "data", "dataHoraRegistro", "siglaOrgao", "aprovacao", "descricao"], [
        ["V1", "2025-02-10", "2025-02-10T16:00:00", "PLEN", "1", "Aprovado o Projeto de Lei nº 1, de 2025."],
        ["V2", "2025-03-10", "2025-03-10T16:00:00", "PLEN", "0", "Rejeitado o Requerimento de retirada de pauta."],
        ["VC", "2025-02-11", "2025-02-11T11:00:00", "CCJC", "1", "Aprovado o Parecer."],
    ])
    _csv(d / "votacoesVotos-2025.csv", ["idVotacao", "dataHoraVoto", "voto", "deputado_id", "deputado_siglaPartido"], [
        ["V1", "2025-02-10T16:00:05", "Sim", "1", "PL"],
        ["V1", "2025-02-10T16:00:01", "Não", "2", "PT"],
        ["V2", "2025-03-10T16:00:01", "Obstrução", "1", "PL"],
        ["V2", "2025-03-10T16:00:02", "Sim", "2", "PT"],
        ["V2", "2025-03-10T16:00:03", "Sim", "3", "PSD"],
        ["VC", "2025-02-11T11:00:00", "Sim", "3", "MDB"],
    ])
    _csv(d / "votacoesProposicoes-2025.csv", ["idVotacao", "proposicao_id", "proposicao_titulo", "proposicao_ementa", "proposicao_siglaTipo"], [
        ["V1", "100", "PL 1/2025", "Dispõe sobre algo.  NOVA EMENTA: Altera a lei de algo.", "PL"],
        ["V2", "200", "REQ 5/2025", "Requer retirada de pauta.", "REQ"],
        ["V2", "100", "PL 1/2025", "Dispõe sobre algo.", "PL"],
    ])
    _csv(d / "votacoesOrientacoes-2025.csv", ["idVotacao", "siglaBancada", "orientacao"], [
        ["V1", "Governo", "Sim"], ["V1", "PL", "Não"], ["V1", "Fdr PT-PCdoB-PV", "Sim"],
        ["V2", "Governo", "Não"], ["V2", "PL", "Obstrução"], ["V2", "Bl MdbPsdRepPode", "Sim"],
    ])
    _csv(d / "proposicoes-2025.csv", ["id", "siglaTipo", "dataApresentacao"], [
        ["100", "PL", "2025-01-20T10:00:00"], ["300", "PEC", "2025-03-05T10:00:00"], ["400", "REQ", "2025-03-05T10:00:00"],
    ])
    _csv(d / "proposicoesAutores-2025.csv", ["idProposicao", "idDeputadoAutor", "ordemAssinatura", "proponente"], [
        ["100", "1", "1", "1"], ["100", "2", "2", "1"], ["300", "3", "1", "0"], ["400", "3", "1", "1"],
    ])
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL)
    w.writerow(["txNomeParlamentar", "cpf", "ideCadastro", "sgPartido", "txtDescricao", "txtFornecedor", "txtCNPJCPF", "vlrLiquido", "numMes", "numAno"])
    w.writerows([
        ["FULANO", "x", "1", "PL", "COMBUSTÍVEIS E LUBRIFICANTES.", "Posto X", "12.345.678/0001-90", "100.5", "2", "2025"],
        ["FULANO", "x", "1", "PL", "PASSAGEM AÉREA - SIGEPA", "Cia Aérea", "98765432000110", "500", "2", "2025"],
        ["BELTRANA", "x", "2", "PT", "MANUTENÇÃO DE ESCRITÓRIO DE APOIO À ATIVIDADE PARLAMENTAR", "Fulano Locador", "123.456.789-01", "1000", "3", "2025"],
        ["LID.GOV-CD", "", "", "", "TELEFONIA", "Operadora", "11222333000144", "50", "3", "2025"],
        ["FULANO", "x", "1", "PL", "TELEFONIA", "Operadora", "11222333000144", "70", "4", "2025"],
    ])
    with zipfile.ZipFile(d / "cotas-2025.csv.zip", "w") as z:
        z.writestr("Ano-2025.csv", "﻿" + buf.getvalue())
    return FonteFalsa(d)
