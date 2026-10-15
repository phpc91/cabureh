from datetime import date

from camara_etl import atividade, cotas, emendas, pauta, senado
from camara_etl.carga import carregar_eventos, carregar_projetos, carregar_votacoes, carregar_votos
from camara_etl.deputados import carregar_deputados, ids_das_legislaturas, legislaturas_no_periodo, montar_deputado, nome_legivel
from camara_etl.periodo import Periodo, periodo_padrao

from .conftest import HISTORICOS

PERIODO = Periodo(date(2025, 1, 1), date(2025, 3, 31))


def _rodar(fonte):
    legs = legislaturas_no_periodo(fonte, PERIODO)
    eventos, presencas = carregar_eventos(fonte, PERIODO)
    meta = carregar_votacoes(fonte, PERIODO)
    votos = carregar_votos(fonte, PERIODO, meta)
    projetos = carregar_projetos(fonte, PERIODO)
    ids = ids_das_legislaturas(fonte, legs)
    deps = carregar_deputados(fonte, ids)
    return legs, deps, atividade.montar(PERIODO, deps, ids, eventos, presencas, votos, projetos), meta, votos


def _linha(linhas, dep, mes, partido=None):
    achadas = [r for r in linhas if r["id_deputado"] == dep and r["mes"] == mes and (partido is None or r["partido"] == partido)]
    assert len(achadas) == 1, achadas
    return achadas[0]


def test_periodo():
    p = periodo_padrao(4, date(2026, 10, 9))
    assert p.ini == "2022-10-09" and p.fim_excl == "2026-10-10"
    assert p.meses[0] == "2022-10" and p.meses[-1] == "2026-10" and len(p.meses) == 49
    assert p.contem("2026-10-09T23:59:00") and not p.contem("2026-10-10T00:00:00") and not p.contem("")
    assert periodo_padrao(1, date(2028, 2, 29)).inicio == date(2027, 2, 28)


def test_exercicio_e_partido():
    d2 = montar_deputado(2, HISTORICOS[2])
    assert not d2.em("2025-01-15T14:00:00").exercicio
    assert d2.em("2025-02-10T14:00:00").exercicio
    assert d2.em("2020-01-01T00:00:00") is None
    d3 = montar_deputado(3, HISTORICOS[3])
    assert d3.em("2025-03-10T14:00:00").partido == "PSD" and d3.em("2025-03-10T14:00:00").exercicio
    assert montar_deputado(1, HISTORICOS[1]).nome == "FULANO DE TAL"
    assert nome_legivel("FULANO DE TAL") == "Fulano de Tal" and nome_legivel("Ciclano") == "Ciclano"


def test_presenca(fonte):
    legs, _, r, _, _ = _rodar(fonte)
    assert legs == [57]
    L = r.linhas
    # Sessões contadas: S1, S2, S3 (S4 sem lista, S9 fora do período)
    assert r.resumo["sessoes"] == 3 and r.resumo["votacoes_nominais"] == 2
    d1 = [_linha(L, 1, m) for m in ("2025-01", "2025-02", "2025-03")]
    assert [(x["sessoes"], x["presencas"]) for x in d1] == [(1, 1), (1, 1), (1, 0)]
    assert d1[0]["deputado"] == "Fulano de Tal" and d1[0]["uf"] == "SP" and d1[0]["projetos_autor"] == 1
    assert d1[1]["votou_sim"] == 1 and d1[2]["obstrucao"] == 1
    assert d1[1]["eventos_comissoes"] == 0  # teste do painel não conta
    # Suplente só é esperado depois de entrar em exercício
    d2_jan = _linha(L, 2, "2025-01")
    assert (d2_jan["sessoes"], d2_jan["votacoes"], d2_jan["projetos_coautor"]) == (0, 0, 1)
    d2 = _linha(L, 2, "2025-02")
    assert (d2["sessoes"], d2["presencas"], d2["votou_nao"]) == (1, 1, 1)
    # Troca de partido separa as linhas; ausente em votação conta como votação esperada
    d3_fev = _linha(L, 3, "2025-02", "MDB")
    assert (d3_fev["sessoes"], d3_fev["presencas"], d3_fev["votacoes"], d3_fev["votos_comissoes"], d3_fev["eventos_comissoes"]) == (1, 0, 1, 1, 1)
    d3_mar = _linha(L, 3, "2025-03", "PSD")
    assert (d3_mar["sessoes"], d3_mar["presencas"], d3_mar["votou_sim"], d3_mar["projetos_autor"]) == (1, 1, 1, 0)


def test_blocos_e_orientacao():
    assert pauta.membros_bloco("Bl UniPpFdrPsdbCid...") == ["UNIÃO", "PP", "PSDB", "CIDADANIA"]
    assert pauta.membros_bloco("Bl PlFdrPTUniPp...") == ["PL", "PT", "PCdoB", "PV", "UNIÃO", "PP"]
    assert pauta.membros_bloco("Bl MdbPsdRepPodePsc") == ["MDB", "PSD", "REPUBLICANOS", "PODE", "PSC"]
    o = {"Governo": "Sim", "Solidaried": "Não", "Fdr PT-PCdoB-PV": "Sim", "Bl MdbPsdRepPode": "Obstrução"}
    assert pauta.orientacao_partido(o, "SOLIDARIEDADE") == "Não"
    assert pauta.orientacao_partido(o, "PCdoB") == "Sim"
    assert pauta.orientacao_partido(o, "PSD") == "Obstrução"
    assert pauta.orientacao_partido(o, "NOVO") is None
    assert pauta.etapa("Mantido o texto. Sim: 3") == "Destaque ou emenda"
    assert pauta.etapa("Aprovada a Subemenda Substitutiva Global") == "Texto principal"
    assert pauta.etapa("Rejeitado o Requerimento.") == "Requerimento"
    assert pauta.limpar_ementa("Antiga. NOVA EMENTA:  Nova  ementa.") == "Nova ementa."


def test_pauta(fonte):
    _, _, _, meta, votos = _rodar(fonte)
    s = pauta.montar(fonte, PERIODO, meta, votos)
    p = {r["id_votacao"]: r for r in s.pauta}
    assert set(p) == {"V1", "V2"}
    assert p["V2"]["proposicao"] == "PL 1/2025" and p["V2"]["etapa"] == "Requerimento"
    assert p["V1"]["tema"] == "Economia" and p["V1"]["ementa"] == "Altera a lei de algo."
    assert (p["V2"]["sim"], p["V2"]["obstrucoes"], p["V2"]["votos"]) == (2, 1, 3)
    assert p["V1"]["orient_governo"] == "Sim" and p["V1"]["aprovada"] == 1
    part = {(r["id_votacao"], r["partido"]): r for r in s.partidos}
    assert part[("V2", "PSD")]["orientacao"] == "Sim" and part[("V1", "PT")]["orientacao"] == "Sim"
    al = {(r["id_deputado"], r["mes"]): r for r in s.alinhamento}
    assert (al[(1, "2025-03")]["obstrucoes"], al[(1, "2025-03")]["obst_orientadas"]) == (1, 1)
    assert (al[(1, "2025-02")]["base_governo"], al[(1, "2025-02")]["com_governo"]) == (1, 1)
    assert al[(2, "2025-02")]["com_governo"] == 0
    assert al[(1, "2025-02")]["base_bancada"] == 0  # bancada com menos de 3 votantes


def test_cotas(fonte):
    assert cotas.categoria("PASSAGEM AÉREA - SIGEPA") == "Passagens aéreas"
    assert cotas.categoria("COMBUSTÍVEIS E LUBRIFICANTES.") == "Combustíveis"
    assert cotas.categoria("ALGO NOVO.") == "Algo novo"
    assert cotas.documento("123.456.789-01") == "Pessoa física"
    assert cotas.documento("12345678000190") == "12.345.678/0001-90"
    s = cotas.montar(fonte, PERIODO)
    meses = {(r["id_deputado"], r["mes"]): r for r in s.meses}
    assert meses[(1, "2025-02")]["valor"] == 600.5 and meses[(1, "2025-02")]["documentos"] == 2
    assert (1, "2025-04") not in meses           # fora do período
    assert s.resumo["despesas_de_liderancas_ignoradas"] == 1
    cats = {(r["id_deputado"], r["categoria"]): r["valor"] for r in s.categorias}
    assert cats[(1, "Passagens aéreas")] == 500 and cats[(2, "Escritório de apoio")] == 1000
    forn = [r for r in s.fornecedores if r["id_deputado"] == 2]
    assert forn[0]["documento"] == "Pessoa física" and "123" not in forn[0]["documento"]
    assert s.fornecedores[0]["valor"] >= s.fornecedores[1]["valor"]


def test_emendas_auxiliares():
    assert emendas.titular("ANA (EX-PARLAMENTAR BIA, NOS TERMOS DA DECISAO ADPF 854)") == "ANA"
    assert emendas.titular("JOSÉ") == "JOSÉ"
    assert emendas.valor("1.300.000,50") == 1300000.5 and emendas.valor("") == 0
    assert emendas.tipo("Emenda Individual - Transferências Especiais") == "Transferência especial"
    assert emendas.destino("CAMPINAS - SP", "CAMPINAS", "SÃO PAULO") == ("Campinas - SP", "SP")
    assert emendas.destino("MÚLTIPLO", "MÚLTIPLO", "SÃO PAULO") == ("Vários municípios - SP", "SP")
    assert emendas.destino("DUQUE DE CAXIAS - RJ", "", "Sem informação") == ("Duque de Caxias - RJ", "RJ")
    assert emendas.destino("BAHIA (UF)", "Sem informação", "BAHIA") == ("Bahia (estado)", "BA")
    assert emendas.destino("Nacional", "", "Sem informação") == ("Nacional", "")
    assert emendas.documento("***.456.789-**", "Pessoa Fisica") == "Pessoa física"
    assert emendas.documento("12345678000190", "Pessoa Jurídica") == "12.345.678/0001-90"


def test_emendas(fonte):
    legs, deps, _, _, _ = _rodar(fonte)
    s = emendas.montar(fonte, PERIODO, deps, emendas.carregar_senadores(fonte, legs))
    por = {(r["id_deputado"], r["area"]): r for r in s.emendas}
    # Fulano: código contado uma vez (na linha de maior valor), pago inclui restos a pagar
    assert por[(1, "Saúde")]["emendas"] == 1 and por[(1, "Saúde")]["pago"] == 600 and por[(1, "Saúde")]["uf_destino"] == "SP"
    assert por[(1, "Educação")]["emendas"] == 0 and por[(1, "Saúde")]["partido"] == "PL"
    # Beltrana casada de forma aproximada (título "Dr."), transferência especial sem área
    assert por[(2, "Sem área definida")]["tipo"] == "Transferência especial"
    # Ciclano herdou a emenda do ex-parlamentar
    assert por[(3, "Cultura")]["empenhado"] == 400 and por[(3, "Cultura")]["partido"] == "MDB"
    assert {r["id_deputado"] for r in s.emendas} == {1, 2, 3}
    r = s.resumo
    assert r["individuais_da_outra_casa"] == 700 and r["individuais_sem_autor_identificado"] == 50
    assert r["autores_casados_aproximado"] == {"DR BELTRANA SOUZA": "Beltrana Souza"}
    tipos = {(t["ano"], t["tipo"]): t for t in s.tipos}
    assert tipos[(2025, "Bancada")]["empenhado"] == 5000 and (2024, "Finalidade definida") not in tipos
    meses = {(m["id_deputado"], m["mes"]): m["valor"] for m in s.meses}
    assert meses == {(1, "2025-02"): 100, (1, "2025-03"): 50, (2, "2025-03"): 300}
    fav = [f for f in s.favorecidos if f["id_deputado"] == 1]
    assert fav[0]["documento"] == "12.345.678/0001-90"
    pf = next(f for f in fav if f["documento"] == "Pessoa física")
    assert pf["favorecido"] == "Pessoas físicas (agrupadas)" and "JOAO" not in str(pf)
    dest = {(d["id_deputado"], d["destino"]) for d in s.destinos}
    assert (1, "Campinas - SP") in dest and (2, "Bahia (estado)") in dest and (3, "Vários municípios - RJ") in dest


def test_casador_homonimos_e_janelas():
    h = lambda ent, sai=None: [{"dataHora": ent, "situacao": "Exercício", "descricaoStatus": "Entrada - Posse", "siglaPartido": "PP", "siglaUf": "PI", "nome": "Átila Lira"}] + (
        [{"dataHora": sai, "situacao": "FIM_MANDATO", "descricaoStatus": "Saída - Término", "siglaPartido": "PP", "siglaUf": "PI", "nome": "Átila Lira"}] if sai else [])
    antigo = montar_deputado(10, h("2019-02-01T12:00", "2023-01-31T23:59"))
    novo = montar_deputado(11, h("2023-02-01T12:00"))
    herdeiro = montar_deputado(12, [{"dataHora": "2025-11-01T12:00", "situacao": "Exercício", "descricaoStatus": "Entrada - Posse de Suplente", "siglaPartido": "PL", "siglaUf": "SC", "nome": "Professora Marcivania"}])
    c = emendas.Casador({10: antigo, 11: novo, 12: herdeiro}, {"ALAN RICK"})
    assert c("ATILA LIRA", 2023) == 10       # apresentada no fim de 2022, pelo mandato antigo
    assert c("ATILA LIRA", 2024) == 11
    # herdou em novembro do ano da emenda: só a janela larga encontra (nome via APELIDOS)
    assert c("MARCIVANIA FLEXA (EX-PARLAMENTAR MARIA GORETH, NOS TERMOS ART. 78 LDO 2025)", 2025) == 12
    assert c("MARCIVANIA FLEXA", 2023) is None
    assert c("ALAN RICK", 2025) is None
    vicentinho = montar_deputado(13, [{"dataHora": "2023-02-01T12:00", "situacao": "Exercício", "descricaoStatus": "Entrada - Posse", "siglaPartido": "PT", "siglaUf": "SP", "nome": "Vicentinho"}])
    c2 = emendas.Casador({13: vicentinho}, set())
    assert c2("VICENTINHO ALVES", 2024) is None   # nome de uma palavra não casa por aproximação


def test_senado(fonte):
    s = senado.montar(fonte, PERIODO, [57], {"FULANO DE TAL", "BELTRANA SOUZA", "CICLANO"})
    assert not s.problemas or all("poucas" in p or "poucos" in p for p in s.problemas)
    L = {(r["id_deputado"], r["mes"]): r for r in s.arquivos["presenca.csv"][0]}
    assert 15 not in {k[0] for k in L} and 16 not in {k[0] for k in L}   # fora do exercício / só antes do período
    ana_fev, ana_mar = L[(10, "2025-02")], L[(10, "2025-03")]
    assert (ana_fev["sessoes"], ana_fev["presencas"], ana_fev["votou_sim"], ana_fev["outros_votos"]) == (1, 1, 1, 1)
    assert ana_fev["projetos_autor"] == 1 and ana_mar["votos_comissoes"] == 1
    assert L[(11, "2025-02")]["projetos_coautor"] == 1 and L[(11, "2025-02")]["partido"] == "REPUBLICANOS"
    carla = L[(12, "2025-02")]
    assert (carla["sessoes"], carla["presencas"], carla["votacoes"]) == (1, 1, 2)      # votou na secreta
    assert L[(14, "2025-02")]["presencas"] == 1                                         # presidente e presente sem voto
    aus = {(r["id_deputado"], r["mes"]): r["motivo"] for r in s.arquivos["ausencias.csv"][0]}
    assert aus == {(13, "2025-02"): "Não compareceu", (11, "2025-03"): "Missão oficial", (12, "2025-03"): "Licença particular"}
    pauta = {r["id_votacao"]: r for r in s.arquivos["pauta.csv"][0]}
    assert pauta["101"]["tema"] == "Economia" and pauta["101"]["orient_governo"] == "Sim"
    assert pauta["102"]["tema"] == "Indicação de autoridades" and pauta["102"]["secreta"] == 1 and pauta["102"]["sim"] == 2
    pv = {(r["id_votacao"], r["partido"]): r for r in s.arquivos["partidos-votacao.csv"][0]}
    assert pv[("101", "REPUBLICANOS")]["orientacao"] == "Não" and pv[("101", "PT")]["orientacao"] == "Sim"
    al = {(r["id_deputado"], r["mes"]): r for r in s.arquivos["alinhamento.csv"][0]}
    assert (al[(10, "2025-02")]["base_governo"], al[(10, "2025-02")]["com_governo"]) == (1, 1)
    assert (11, "2025-02") in al and al[(11, "2025-02")]["com_governo"] == 0
    gm = {(r["id_deputado"], r["mes"]): r["valor"] for r in s.arquivos["gastos-mes.csv"][0]}
    assert gm == {(10, "2025-02"): 100.5, (11, "2025-03"): 50.0}
    cats = {r["categoria"] for r in s.arquivos["gastos-categoria.csv"][0]}
    assert cats == {"Passagens aéreas", "Locomoção, hospedagem e alimentação"}
    forn = {r["id_deputado"]: r for r in s.arquivos["fornecedores.csv"][0]}
    assert forn[11]["documento"] == "Pessoa física"
    assert "DESCONHECIDO" in s.meta["cotas"]["sem_senador_identificado"]
    assert s.meta["presenca"]["ausencias_por_motivo"] == {"Não compareceu": 1, "Missão oficial": 1, "Licença particular": 1}
    assert "emendas.csv" in s.arquivos and s.meta["emendas"]["individuais_da_outra_casa"] > 0
