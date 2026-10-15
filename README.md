# Presença no Congresso

**Site: https://phpc91.github.io/cabureh/**

Painel sobre o trabalho de deputados federais e senadores: presença, votações, pauta, projetos,
gastos da cota parlamentar e emendas ao Orçamento. Tudo vem de dados públicos, é coletado de novo
todos os dias e pode ser filtrado por ano, partido, estado e parlamentar.

## Por que este projeto existe

Os dados sobre o que acontece no Congresso são públicos, mas ficam espalhados em APIs, planilhas
anuais e portais diferentes, em formatos difíceis de cruzar. Este projeto junta essas fontes num
lugar só, com três compromissos:

- **Comparar com justiça.** Os números são medidos em proporção ao tempo de mandato de cada um e
  à mesma régua para todos, para que um suplente que ficou três meses não seja comparado em
  números absolutos com quem cumpriu quatro anos.
- **Mostrar como cada número é feito.** A metodologia está na aba *Como ler* do painel e no código
  deste repositório. Quando a fonte tem limites (faltas que podem ser justificadas, votos secretos,
  nomes que precisam ser casados), o painel diz isso em vez de esconder.
- **Não tomar partido.** O painel mede atividade registrada, não a qualidade de um mandato.
  Articulação política, relatorias e trabalho na base eleitoral não aparecem nos dados, e nenhum
  indicador aqui deve ser lido como nota final de um parlamentar.

É um projeto independente, sem vínculo com a Câmara dos Deputados, o Senado Federal ou partidos.

## O que tem no painel

O seletor no topo troca entre **Câmara** e **Senado**; as abas são as mesmas nas duas casas.

| Aba | O que mostra |
|---|---|
| Presença | presença nas sessões, distribuição, rankings, partidos; no Senado, os motivos das ausências |
| Votações | como cada partido votou, participação, abstenções, obstruções |
| Pauta | o que foi votado, por tema, com resultado e orientação do governo |
| Projetos | projetos apresentados como autor e coautor |
| Gastos | cota parlamentar por mês, categoria, partido e fornecedor |
| Emendas | emendas ao Orçamento por ano, área, destino, quem recebeu, emendas Pix |
| Trabalho | nota de 0 a 100 que combina critérios com pesos ajustáveis |
| Deputados / Senadores, Partidos | tabelas completas, ordenáveis |

O recorte escolhido fica no endereço da página, então dá para compartilhar um link já filtrado.

## Como contribuir

As contribuições começam sempre por uma **issue**. Pode ser uma pergunta que o painel ainda não
responde, uma melhoria em algo que já existe, um número que parece errado ou um problema no site.

1. **Abra uma issue** em [*Issues → New issue*](https://github.com/phpc91/cabureh/issues/new/choose)
   usando o formulário *Proposta*. Ele pede o que você quer saber, de onde viriam os dados e
   como saber que ficou pronto. Antes, procure nas issues abertas se já não existe uma parecida.
2. **Triagem.** Toda issue nova entra com o rótulo `proposta`. Ela é discutida nos comentários:
   se os dados existem, se a métrica é justa, se cabe no painel.
3. **Aprovação.** Quando a proposta está clara e faz sentido para o projeto, ela recebe o rótulo
   `aprovada`. Só issues aprovadas são implementadas.
4. **Implementação.** A mudança é feita num pull request que cita a issue (`Fecha #123`). Os
   testes da coleta precisam passar.
5. **Publicação.** Ao entrar na `main`, o site é reconstruído e publicado automaticamente.

### O que ajuda uma proposta a ser aprovada

- Uma pergunta concreta ("quem mais faltou em votações de PEC?") em vez de um pedido genérico
  ("mais gráficos").
- A fonte dos dados, com link para a API, o arquivo ou a página oficial.
- Um critério de pronto que dê para conferir: o que deve aparecer, onde e com que número de
  referência.
- Para números errados: o link do painel já filtrado mostrando o problema e, se possível, o valor
  certo na fonte oficial.

Pull requests sem issue aprovada podem ser fechados para que a discussão aconteça antes do código.

## Como funciona

```
etl/                               coleta em Python: baixa as fontes e gera CSVs agregados
web/                               site estático (Vite + d3) que lê esses CSVs
.github/workflows/atualizar.yml    todo dia: testes → coleta → build → publica no Pages
.github/ISSUE_TEMPLATE/            formulário de proposta
```

- **Fontes**:
  - [Dados Abertos da Câmara](https://dadosabertos.camara.leg.br): arquivos anuais e API v2;
  - [API de Dados Abertos do Senado](https://legis.senado.leg.br/dadosabertos/api-docs/swagger-ui/index.html);
  - cota dos senadores (CEAPS) no [portal de transparência do Senado](https://www12.senado.leg.br/transparencia);
  - emendas no [Portal da Transparência da CGU](https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares).

  Nenhuma das fontes exige chave de acesso.
- **Janela**: os últimos 4 anos até a data da coleta.
- **Atualização**: automática todo dia às 06:17 (Brasília). Para atualizar na hora, vá em
  *Actions → Atualizar dados e publicar → Run workflow*.
- **Cache**: arquivos só são baixados de novo quando mudam (ETag); respostas de API ficam em cache
  por um prazo que depende do recurso. O cache é guardado entre execuções do Actions.
- **Barreiras**: se a Câmara vier com dados incompletos, nada é publicado. Se o Senado ou o Portal
  da Transparência falharem, a Câmara é publicada mesmo assim e a parte afetada fica indisponível.

## Rodar localmente

```bash
# coleta (precisa de acesso às fontes acima)
cd etl
pip install -r requirements-dev.txt
python -m pytest -q
python -m camara_etl build --cache .cache --out ../web/public/data   # ~20–30 min na primeira vez

# site
cd ../web
npm install
npm run dev          # Câmara em /, Senado em /?casa=senado
```

Opções úteis da coleta:
- `--fim AAAA-MM-DD` fixa o último dia, para reproduzir um período;
- `--anos N` muda o tamanho da janela;
- `--offline` usa só o cache;
- `--sem-cotas`, `--sem-emendas` e `--sem-senado` pulam partes da coleta.

## Arquivos gerados (`web/public/data`)

Os do Senado ficam em `web/public/data/senado/`, com os mesmos nomes e colunas.

| Arquivo | Uma linha por |
|---|---|
| `presenca.csv` | parlamentar × mês × partido: sessões esperadas, presenças, votos por tipo, comissões, projetos |
| `ausencias.csv` (só Senado) | senador × mês × partido × motivo da ausência |
| `pauta.csv` | votação nominal do Plenário: proposição, tema, etapa, resultado, orientação do governo |
| `partidos-votacao.csv` | votação × partido: votos e orientação da bancada |
| `alinhamento.csv` | parlamentar × mês × partido: votos com a bancada, com o governo, obstruções |
| `gastos-mes.csv`, `gastos-categoria.csv`, `fornecedores.csv` | cota parlamentar por mês, por tipo de despesa e maiores fornecedores |
| `emendas.csv`, `emendas-destinos.csv`, `emendas-mes.csv`, `emendas-favorecidos.csv`, `emendas-tipos.csv` | emendas individuais por área e destino, pagamentos por mês, maiores favorecidos, totais por tipo |
| `meta.json` | data da coleta, período e totais de conferência |

A metodologia de cada número está na aba **Como ler** do painel.

## Publicar no GitHub Pages

1. *Settings → Pages → Build and deployment → Source: GitHub Actions*.
2. Rode o workflow uma vez (*Actions → Atualizar dados e publicar → Run workflow*).
3. O endereço aparece no resumo da execução, no passo *deploy*.

## Licença

© 2026 phpc91. Código, textos, metodologia e visualizações sob
[Creative Commons Atribuição-NãoComercial 4.0 (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/deed.pt-br):
pode copiar e adaptar, dando crédito com link para este repositório e sem uso comercial. Texto completo em [LICENSE](LICENSE).

Os dados de origem são públicos e seguem os termos das fontes: Câmara dos Deputados, Senado Federal
e Portal da Transparência (CGU).
