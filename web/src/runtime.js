// Substitui o runtime do painel original: carrega os arquivos de /data, guarda os filtros
// na URL (para compartilhar um recorte) e redesenha a página quando algo muda.
import * as d3 from 'd3';

const NUMERICOS = /^-?\d+(\.\d+)?$/;

// Casa legislativa: ?casa=senado troca a pasta de dados; a Câmara é o padrão.
export const CASA = new URLSearchParams(location.search).get('casa') === 'senado' ? 'senado' : 'camara';
const BASE = CASA === 'senado' ? 'data/senado/' : 'data/';
const ARQUIVOS = {
  presenca: 'presenca.csv',
  pauta: 'pauta.csv',
  partidos_votacao: 'partidos-votacao.csv',
  alinhamento: 'alinhamento.csv',
  gastos_mes: 'gastos-mes.csv',
  gastos_categoria: 'gastos-categoria.csv',
  fornecedores: 'fornecedores.csv',
  emendas: 'emendas.csv',
  emendas_destinos: 'emendas-destinos.csv',
  emendas_mes: 'emendas-mes.csv',
  emendas_favorecidos: 'emendas-favorecidos.csv',
  emendas_tipos: 'emendas-tipos.csv',
  meta: 'meta.json',
};
if (CASA === 'senado') ARQUIVOS.ausencias = 'ausencias.csv';   // motivos das ausências, só no Senado
export const FONTES = Object.fromEntries(Object.entries(ARQUIVOS).map(([k, v]) => [k, BASE + v]));

const PADRAO = { anos: [], partido: null, uf: null, deputado: null, minimo: 25 };

function lerUrl() {
  const q = new URLSearchParams(location.search);
  const p = { ...PADRAO };
  if (q.get('anos')) p.anos = q.get('anos').split(',').filter(Boolean);
  for (const k of ['partido', 'uf', 'deputado']) if (q.get(k)) p[k] = q.get(k);
  if (q.has('minimo') && Number.isFinite(+q.get('minimo'))) p.minimo = +q.get('minimo');
  return p;
}

function escreverUrl(p) {
  const q = new URLSearchParams();
  if (CASA !== 'camara') q.set('casa', CASA);
  if (p.anos && p.anos.length) q.set('anos', p.anos.join(','));
  for (const k of ['partido', 'uf', 'deputado']) if (p[k] != null && p[k] !== '') q.set(k, p[k]);
  if (p.minimo !== PADRAO.minimo) q.set('minimo', String(p.minimo));
  const s = q.toString();
  history.replaceState(history.state, '', location.pathname + (s ? '?' + s : '') + location.hash);
}

export function criarRuntime() {
  const estado = Object.fromEntries(Object.keys(FONTES).map((id) => [id, { status: 'loading', data: [], columns: [], message: '' }]));
  let params = lerUrl();
  const desenhos = [];
  let agendado = false;

  const redesenhar = () => {
    if (agendado) return;
    agendado = true;
    // setTimeout em vez de requestAnimationFrame: abas carregadas em segundo plano
    // podem adiar ou descartar quadros, e o painel ficava sem desenhar.
    setTimeout(() => {
      agendado = false;
      for (const fn of desenhos) {
        try { fn(); } catch (e) { console.error('[painel] erro ao desenhar', e); }
      }
    }, 0);
  };

  for (const [id, url] of Object.entries(FONTES)) {
    const pedido = url.endsWith('.json')
      ? d3.json(url, { cache: 'no-cache' })
      : d3.csv(url, { cache: 'no-cache' }, (r) => r);
    pedido.then((data) => {
      estado[id] = { status: 'ok', data, columns: data && data.columns ? data.columns : [], message: '' };
      redesenhar();
    }).catch((e) => {
      estado[id] = { status: 'error', data: [], columns: [], message: String(e && e.message || e) };
      console.error('[painel] falha ao carregar', url, e);
      redesenhar();
    });
  }

  let largura = window.innerWidth;
  window.addEventListener('resize', () => {
    if (Math.abs(window.innerWidth - largura) < 8) return;
    largura = window.innerWidth;
    redesenhar();
  });
  window.addEventListener('popstate', () => { params = lerUrl(); redesenhar(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) redesenhar(); });

  return {
    casa: CASA,
    colors: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => `var(--series-${i})`),
    data: (id) => ({ ...(estado[id] || { status: 'missing', data: [], columns: [], message: 'fonte desconhecida' }), refreshing: false, meta: [] }),
    onData: (fn) => { desenhos.push(fn); try { fn(); } catch (e) { console.error(e); } },
    params: () => ({ ...params, anos: [...params.anos] }),
    setParams: (o) => { params = { ...params, ...o }; escreverUrl(params); redesenhar(); },
    resetParams: () => { params = { ...PADRAO }; escreverUrl(params); redesenhar(); },
    setLink: (nome) => { history.replaceState(history.state, '', location.pathname + location.search + '#' + nome); },
    refresh: () => {},
    calc: () => {},
    numerico: (x) => (NUMERICOS.test(x) ? +x : x),
  };
}
