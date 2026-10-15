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

    def emendas(self):
        p = self.pasta / "emendas.zip"
        return p if p.exists() else None

    def ceaps(self, ano):
        p = self.pasta / f"ceaps-{ano}.csv"
        return p if p.exists() else None

    def senado(self, caminho, params=None, ttl=0):
        params = params or {}
        if caminho == "/votacao":
            return [v for v in SEN_VOTACOES if params["dataInicio"] <= v["dataSessao"] <= params["dataFim"]]
        if caminho.startswith("/plenario/votacao/orientacaoBancada/"):
            return {"votacoes": [{"sequencialVotacao": 101, "orientacoesLideranca": [
                {"partido": "Governo", "voto": "SIM"}, {"partido": "PT", "voto": "SIM"}, {"partido": "Republica", "voto": "NÃO"},
                {"partido": "MDB", "voto": "LIVRE"}]}]}
        if caminho.startswith("/senador/lista/legislatura/"):
            return {"ListaParlamentarLegislatura": {"Parlamentares": {"Parlamentar": [
                {"IdentificacaoParlamentar": {"CodigoParlamentar": "10", "NomeParlamentar": "Ana", "NomeCompletoParlamentar": "Ana Souza", "UfParlamentar": "SP"}},
                {"IdentificacaoParlamentar": {"CodigoParlamentar": "17", "NomeParlamentar": "Hugo", "SiglaPartidoParlamentar": "PP", "UfParlamentar": "PI"}}]}}}
        if caminho == "/processo":
            proj = {"id": 1, "identificacao": "PL 7/2025", "dataApresentacao": "2025-02-15", "autoria": "Senadora Ana (PT/SP), Senador Bruno (PL/RJ)"}
            req = {"id": 2, "identificacao": "RQS 9/2025", "dataApresentacao": "2025-02-15", "autoria": "Senadora Ana (PT/SP)"}
            return {10: [proj, req], 11: [proj]}.get(params["codigoParlamentarAutor"], [])
        if caminho == "/votacaoComissao/parlamentar/10" and params["dataInicio"].startswith("2025"):
            return {"VotacoesComissao": {"Votacoes": {"Votacao": {"DataHoraInicioReuniao": "2025-03-11T10:00:00"}}}}
        return None

    def json_externo(self, url, ttl=0):
        if "senador/lista/legislatura/57/57" in url:
            return {"ListaParlamentarLegislatura": {"Parlamentares": {"Parlamentar": [
                {"IdentificacaoParlamentar": {"NomeParlamentar": "Alan Rick", "NomeCompletoParlamentar": "Alan Rick Miranda"}}]}}}
        return None

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
        if caminho == "/proposicoes":
            return {"dados": [{"id": 100}]} if (params.get("siglaTipo"), params.get("numero")) == ("PL", "1") else {"dados": []}
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
    _zip_emendas(d / "emendas.zip")
    (d / "ceaps-2025.csv").write_bytes((
        '"ULTIMA ATUALIZACAO";"14/10/2026 02:03"\r\n'
        '"ANO";"MES";"SENADOR";"TIPO_DESPESA";"CNPJ_CPF";"FORNECEDOR";"DOCUMENTO";"DATA";"DETALHAMENTO";"VALOR_REEMBOLSADO";"COD_DOCUMENTO"\r\n'
        '"2025";"2";"ANA";"Passagens aéreas, aquáticas e terrestres nacionais";"02.012.862/0001-60";"LATAM";"1";"01/02/2025";"trecho\r\ncom quebra";"100,50";"1"\r\n'
        '"2025";"3";"BRUNO";"Locomoção, hospedagem, alimentação, combustíveis e lubrificantes";"123.456.789-01";"JOSE";"2";"01/03/2025";"";"50,00";"2"\r\n'
        '"2025";"3";"DESCONHECIDO";"Divulgação da atividade parlamentar";"11222333000144";"GRAFICA";"3";"01/03/2025";"";"10,00";"3"\r\n'
    ).encode("latin-1"))
    return FonteFalsa(d)


def _latin1(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue().encode("latin-1")


FD = "Emenda Individual - Transferências com Finalidade Definida"
TE = "Emenda Individual - Transferências Especiais"


def _zip_emendas(path: Path):
    cab = ["Código da Emenda", "Ano da Emenda", "Tipo de Emenda", "Código do Autor da Emenda", "Nome do Autor da Emenda",
           "Número da emenda", "Localidade de aplicação do recurso", "Código Município IBGE", "Município", "Código UF IBGE", "UF",
           "Região", "Código Função", "Nome Função", "Nome Subfunção", "Valor Empenhado", "Valor Liquidado", "Valor Pago",
           "Valor Restos A Pagar Inscritos", "Valor Restos A Pagar Cancelados", "Valor Restos A Pagar Pagos"]

    def linha(cod, ano, tp, autor, loc, mun, uf, func, emp, pago, rpp):
        return [cod, ano, tp, cod[4:8], autor, cod[8:], loc, "", mun, "", uf, "", "", func, "", emp, "0,00", pago, "0,00", "0,00", rpp]

    emendas = [
        linha("202510010001", "2025", FD, "FULANO DE TAL", "CAMPINAS - SP", "CAMPINAS", "SÃO PAULO", "Saúde", "1000,50", "500,00", "100,00"),
        linha("202510010001", "2025", FD, "FULANO DE TAL", "CAMPINAS - SP", "CAMPINAS", "SÃO PAULO", "Educação", "200,00", "0,00", "0,00"),
        linha("202510020001", "2025", TE, "DR. BELTRANA SOUZA", "BAHIA (UF)", "Sem informação", "BAHIA", "Encargos especiais", "300,00", "300,00", "0,00"),
        linha("202510030001", "2025", FD, "ALAN RICK", "Nacional", "", "Sem informação", "Saúde", "700,00", "0,00", "0,00"),
        linha("202510040001", "2025", FD, "CICLANO (EX-PARLAMENTAR FULANO, NOS TERMOS ART. 78 LDO 2025)", "MÚLTIPLO", "", "RIO DE JANEIRO", "Cultura", "400,00", "0,00", "0,00"),
        linha("202571240001", "2025", "Emenda de Bancada", "BANCADA DE SAO PAULO", "SÃO PAULO (UF)", "", "SÃO PAULO", "Saúde", "5000,00", "1000,00", "0,00"),
        linha("202410010009", "2024", FD, "FULANO DE TAL", "Nacional", "", "", "Saúde", "999,00", "0,00", "0,00"),
        linha("202510050001", "2025", FD, "FULANO", "Nacional", "", "", "Saúde", "50,00", "0,00", "0,00"),
    ]
    cab_f = ["Código da Emenda", "Código do Autor da Emenda", "Nome do Autor da Emenda", "Número da emenda", "Tipo de Emenda",
             "Ano/Mês", "Código do Favorecido", "Favorecido", "Natureza Jurídica", "Tipo Favorecido", "UF Favorecido",
             "Município Favorecido", "Valor Recebido"]
    fav = [
        ["202510010001", "1001", "FULANO DE TAL", "0001", FD, "202502", "12345678000190", "MUNICIPIO DE CAMPINAS", "Município", "Pessoa Jurídica", "SP", "CAMPINAS", "100,00"],
        ["202510010001", "1001", "FULANO DE TAL", "0001", FD, "202503", "***.456.789-**", "JOAO DA SILVA", "Sem informação", "Pessoa Fisica", "SP", "CAMPINAS", "50,00"],
        ["202510020001", "1002", "DR. BELTRANA SOUZA", "0001", TE, "202503", "13937073000156", "ESTADO DA BAHIA", "Estado ou Distrito Federal", "Pessoa Jurídica", "BA", "SALVADOR", "300,00"],
        ["202571240001", "7124", "BANCADA DE SAO PAULO", "0001", "Emenda de Bancada", "202502", "12345678000190", "MUNICIPIO DE CAMPINAS", "Município", "Pessoa Jurídica", "SP", "CAMPINAS", "1000,00"],
        ["202510010001", "1001", "FULANO DE TAL", "0001", FD, "202504", "12345678000190", "MUNICIPIO DE CAMPINAS", "Município", "Pessoa Jurídica", "SP", "CAMPINAS", "77,00"],
    ]
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("EmendasParlamentares.csv", _latin1(cab, emendas))
        z.writestr("EmendasParlamentares_PorFavorecido.csv", _latin1(cab_f, fav))
        z.writestr("EmendasParlamentares_Convenios.csv", _latin1(["Código da Emenda"], []))


def _v(cod, nome, partido, uf, sig):
    return {"codigoParlamentar": cod, "nomeParlamentar": nome, "siglaPartidoParlamentar": partido, "siglaUFParlamentar": uf, "siglaVotoParlamentar": sig}


ANA, BRUNO, CARLA, DAVI, EVA = (10, "Ana", "PT", "SP"), (11, "Bruno", "REPUBLICANOS", "RJ"), (12, "Carla", "PT", "BA"), (13, "Davi", "PSD", "MG"), (14, "Eva", "PT", "SP")
SEN_VOTACOES = [
    {"sequencialVotacao": 50, "codigoSessao": 800, "dataSessao": "2024-11-20", "sigla": "PL", "numero": "9", "ano": 2024, "casaSessao": "SF",
     "votacaoSecreta": "N", "votos": [_v(*ANA, "Sim"), _v(*BRUNO, "Sim"), _v(16, "Gil", "PL", "GO", "Sim")]},
    {"sequencialVotacao": 101, "codigoSessao": 900, "dataSessao": "2025-02-10", "sigla": "PL", "numero": "1", "ano": 2025, "codigoMateria": 5001,
     "identificacao": "PL 1/2025", "ementa": "Dispõe sobre algo.", "descricaoVotacao": "Votação nominal do Projeto de Lei nº 1", "resultadoVotacao": "A",
     "casaSessao": "SF", "votacaoSecreta": "N", "totalVotosSim": 1, "totalVotosNao": 1, "totalVotosAbstencao": 0,
     "votos": [_v(*ANA, "Sim"), _v(*BRUNO, "Não"), _v(*CARLA, "AP"), _v(*DAVI, "NCom"), _v(*EVA, "Presidente (art. 51 RISF)")]},
    {"sequencialVotacao": 102, "codigoSessao": 900, "dataSessao": "2025-02-10", "sigla": "MSF", "numero": "3", "ano": 2025, "codigoMateria": 5002,
     "identificacao": "MSF 3/2025", "descricaoVotacao": "Votação da indicação", "resultadoVotacao": "A", "casaSessao": "SF", "votacaoSecreta": "S",
     "totalVotosSim": 2, "totalVotosNao": 0, "totalVotosAbstencao": 0,
     "votos": [_v(*ANA, "Votou"), _v(*BRUNO, "LS"), _v(*CARLA, "Votou"), _v(*DAVI, "NCom"), _v(*EVA, "P-NRV")]},
    {"sequencialVotacao": 103, "codigoSessao": 901, "dataSessao": "2025-03-05", "sigla": "PEC", "numero": "2", "ano": 2025, "codigoMateria": 5003,
     "identificacao": "PEC 2/2025", "descricaoVotacao": "Votação nominal da PEC", "resultadoVotacao": "A", "casaSessao": "SF", "votacaoSecreta": "N",
     "votos": [_v(*ANA, "Sim"), _v(*BRUNO, "MIS"), _v(*CARLA, "LP"), _v(*DAVI, "Sim"), _v(15, "Fabio", "PL", "AC", "AFO")]},
]
