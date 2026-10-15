# Presença na Câmara

Painel com presença, votações, pauta, gastos da cota parlamentar e atividade dos deputados federais,
montado a partir dos [Dados Abertos da Câmara dos Deputados](https://dadosabertos.camara.leg.br).
Os dados são coletados de novo todos os dias e o site é publicado no GitHub Pages.

## Como funciona

```
etl/   coleta em Python: baixa os arquivos anuais e a API da Câmara e gera CSVs agregados
web/   site estático (Vite + d3) que lê esses CSVs
.github/workflows/atualizar.yml   todo dia: coleta → testes → build → publica no Pages
```

- **Janela**: os últimos 4 anos até a data da coleta.
- **Atualização**: automática todo dia às 06:17 (Brasília). Para atualizar na hora,
  vá em *Actions → Atualizar dados e publicar → Run workflow*.
- **Cache**: os arquivos da Câmara só são baixados de novo quando mudam (ETag); a cópia anterior
  fica no cache do Actions entre execuções.
- **Filtros na URL**: o recorte escolhido (anos, partido, estado, deputado) fica no endereço,
  então dá para compartilhar um link já filtrado.

## Rodar localmente

```bash
# coleta (precisa de acesso a dadosabertos.camara.leg.br e www.camara.leg.br)
cd etl
pip install -r requirements-dev.txt
python -m pytest -q
python -m camara_etl build --cache .cache --out ../web/public/data   # ~10–20 min na primeira vez

# site
cd ../web
npm install
npm run dev
```

Opções úteis da coleta: `--fim AAAA-MM-DD` (fixa o último dia, para reproduzir um período),
`--anos N` (tamanho da janela), `--offline` (usa só o cache), `--sem-cotas`.

## Arquivos gerados (`web/public/data`)

| Arquivo | Uma linha por | Origem |
|---|---|---|
| `presenca.csv` | deputado × mês × partido: sessões esperadas, presenças, votos por tipo, reuniões de comissão, projetos | eventos, presenças, votações, votos, proposições, autores, histórico dos deputados |
| `pauta.csv` | votação nominal do Plenário: proposição, tema, etapa, resultado, orientação do governo | votações, proposições votadas, orientações, temas |
| `partidos-votacao.csv` | votação × partido: votos e orientação da bancada | votos, orientações |
| `alinhamento.csv` | deputado × mês × partido: votos com a bancada, com o governo, obstruções por origem | votos, orientações |
| `gastos-mes.csv`, `gastos-categoria.csv`, `fornecedores.csv` | cota parlamentar (CEAP) por mês, por tipo de despesa e maiores fornecedores | arquivos anuais da cota |
| `meta.json` | data da coleta, período, totais de conferência | — |

A metodologia de cada número está na aba **Como ler** do painel.

## Publicar no GitHub Pages

1. *Settings → Pages → Build and deployment → Source: GitHub Actions*.
2. Rode o workflow uma vez (*Actions → Atualizar dados e publicar → Run workflow*).
3. O endereço aparece no resumo da execução, no passo *deploy*.

Projeto independente, sem vínculo com a Câmara dos Deputados.

## Licença

© 2026 phpc91. Código, textos, metodologia e visualizações sob
[Creative Commons Atribuição-NãoComercial 4.0 (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/deed.pt-br):
pode copiar e adaptar, dando crédito com link para este repositório e sem uso comercial. Texto completo em [LICENSE](LICENSE).

Os dados de origem são públicos e seguem os termos das fontes: Dados Abertos da Câmara dos Deputados e Portal da Transparência (CGU).
