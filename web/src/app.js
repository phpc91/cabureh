// Lógica do painel: recebe o runtime de dados (dash) e o d3, desenha tudo dentro de .cp
export function iniciar(dash, d3) {
const root = document.querySelector('.cp');
const $ = (s) => root.querySelector(s);
const SENADO = dash.casa === 'senado';
// No Senado, os textos escritos para a Câmara são adaptados por estas trocas, em ordem.
// Trechos entre ⟦ ⟧ já estão escritos para a casa certa e não são trocados.
const TROCAS = [
  [/Dados Abertos da Câmara dos Deputados/g, 'Dados Abertos do Senado Federal'], [/Câmara dos Deputados/g, 'Senado Federal'],
  [/Câmara inteira/g, 'Senado inteiro'], [/\bda Câmara\b/g, 'do Senado'], [/\bna Câmara\b/g, 'no Senado'], [/\bà Câmara\b/g, 'ao Senado'],
  [/\bpela Câmara\b/g, 'pelo Senado'], [/\ba Câmara\b/g, 'o Senado'], [/\bA Câmara\b/g, 'O Senado'], [/Câmara/g, 'Senado'],
  [/deputados federais/g, 'senadores'], [/Deputados/g, 'Senadores'], [/Deputado/g, 'Senador'], [/deputados/g, 'senadores'],
  [/deputada/g, 'senadora'], [/deputado/g, 'senador'],
  [/sessões deliberativas/g, 'sessões com votação nominal'], [/sessão deliberativa/g, 'sessão com votação nominal'],
  [/senadores do Senado/g, 'senadores'],
];
const tx = (s) => {
  if (s == null) return s;
  s = String(s);
  if (!SENADO) return s.replace(/[⟦⟧]/g, '');
  return s.split(/(⟦[^⟧]*⟧)/).map((p) => (p.startsWith('⟦') ? p.slice(1, -1) : TROCAS.reduce((a, [re, b]) => a.replace(re, b), p))).join('');
};
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = tx(text); return e; };
const nf = new Intl.NumberFormat('pt-BR');
const num = (x) => nf.format(Math.round(x || 0));
const dec = (x, d = 1) => (x == null || !isFinite(x)) ? '—' : x.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (x, d = 1) => (x == null || !isFinite(x)) ? '—' : dec(x * 100, d) + '%';
const fmtPctl = (x) => (x == null ? '—' : String(Math.max(1, Math.round(x * 100))));
const qtd = (n, um, varios) => num(n) + ' ' + (Math.round(n) === 1 ? um : varios);
const MES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const mesNome = (m) => MES[+m.slice(5, 7) - 1] + '/' + m.slice(0, 4);
const semAcento = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const C = dash.colors;
const MUTED = 'var(--ds-chart-muted)';
const F = ['sE', 'sP', 'vE', 'vS', 'vN', 'vA', 'vO', 'vX', 'cV', 'oE', 'pA', 'pC'];
const SEM = 'Sem partido';
const TABS = ['presenca', 'votacoes', 'pauta', 'projetos', 'gastos', 'emendas', 'trabalho', 'deputados', 'partidos', 'metodo'];
const ui = { tab: 'presenca', modo: 'taxa', q: '', sortDep: { k: 'aus', dir: -1 }, sortPart: { k: 'taus', dir: -1 }, pesos: { pres: 2, com: 2, proj: 1, coaut: 1, abs: 1 }, sortObs: { k: 'obs', dir: -1 }, sortPauta: { k: 'n', dir: -1 }, sortDet: { k: 'data', dir: 1 }, tema: null, prop: null, qPauta: '', sortForn: { k: 'v', dir: -1 }, sortDest: { k: 'e', dir: -1 }, sortFav: { k: 'v', dir: -1 }, modoEm: 'valor' };
let cache3 = { key: '', G: null };
let cache2 = { key: '', V: null };
const FATORES = [
  { k: 'pres', nome: 'Presença em plenário', desc: 'Presenças sobre sessões em exercício', v: (d) => d.pres, bom: 1, mostra: (d) => pct(d.pres) + ' de presença' },
  SENADO
    ? { k: 'com', nome: 'Votos em comissões', desc: 'Votos registrados em votações de comissões, por sessão em exercício', v: (d) => d.cV / d.sE, bom: 1, mostra: (d) => qtd(d.cV, 'voto em comissão', 'votos em comissões') }
    : { k: 'com', nome: 'Reuniões de comissão', desc: 'Comissões, audiências e outros eventos, por sessão em exercício', v: (d) => d.oE / d.sE, bom: 1, mostra: (d) => qtd(d.oE, 'reunião de comissão', 'reuniões de comissão') },
  { k: 'proj', nome: 'Projetos', desc: 'Como primeiro autor, por sessão em exercício', v: (d) => d.pA / d.sE, bom: 1, mostra: (d) => qtd(d.pA, 'projeto', 'projetos') },
  { k: 'coaut', nome: 'Coautorias', desc: 'Projetos assinados como coautor, por sessão em exercício', v: (d) => d.pC / d.sE, bom: 1, mostra: (d) => qtd(d.pC, 'coautoria', 'coautorias') },
  { k: 'abs', nome: 'Abstenções', desc: 'Parcela dos votos dados; menos é melhor', v: (d) => (d.vot ? d.vA / d.vot : 0), bom: -1, mostra: (d) => qtd(d.vA, 'abstenção', 'abstenções') },
];
let cache = { key: '', D: null };
let ctx = null;

/* ---------- dados ---------- */
function prep(data) {
  const rows = data.map((r) => {
    const m = String(r.mes);
    return { id: String(r.id_deputado), nome: String(r.deputado), uf: String(r.uf), p: String(r.partido), m, y: m.slice(0, 4),
      sE: +r.sessoes || 0, sP: +r.presencas || 0, vE: +r.votacoes || 0, vS: +r.votou_sim || 0, vN: +r.votou_nao || 0, vA: +r.abstencao || 0,
      vO: +r.obstrucao || 0, vX: +r.outros_votos || 0, cV: +r.votos_comissoes || 0, oE: +r.eventos_comissoes || 0, pA: +r.projetos_autor || 0, pC: +r.projetos_coautor || 0 };
  });
  const comDado = [...new Set(rows.map((r) => r.m))].sort();
  const meses = [];
  if (comDado.length) {
    let y = +comDado[0].slice(0, 4), mo = +comDado[0].slice(5, 7); const fim = comDado[comDado.length - 1];
    for (let n = 0; n < 600; n++) { const k = y + '-' + String(mo).padStart(2, '0'); meses.push(k); if (k >= fim) break; mo++; if (mo > 12) { mo = 1; y++; } }
  }
  const anos = [...new Set(rows.map((r) => r.y))].sort();
  const ufs = [...new Set(rows.map((r) => r.uf))].filter(Boolean).sort();
  const peso = new Map();
  for (const r of rows) peso.set(r.p, (peso.get(r.p) || 0) + r.sE);
  const partidos = [...peso.keys()].sort((a, b) => peso.get(b) - peso.get(a));
  // nº de sessões e de votações em cada mês = o máximo esperado de um mesmo deputado
  const porDepMes = new Map();
  for (const r of rows) { const k = r.id + '|' + r.m; let a = porDepMes.get(k); if (!a) { a = [r.m, 0, 0]; porDepMes.set(k, a); } a[1] += r.sE; a[2] += r.vE; }
  const sessMes = new Map(meses.map((m) => [m, 0])), votMes = new Map(meses.map((m) => [m, 0]));
  for (const a of porDepMes.values()) { if (a[1] > sessMes.get(a[0])) sessMes.set(a[0], a[1]); if (a[2] > votMes.get(a[0])) votMes.set(a[0], a[2]); }
  const nomes = new Map(); for (const r of rows) nomes.set(r.id, r.nome);
  const info = new Map(); for (const r of rows) { const a = info.get(r.id); if (!a || r.m >= a.m) info.set(r.id, { id: r.id, nome: r.nome, uf: r.uf, p: r.p, m: r.m }); }
  return { rows, meses, anos, ufs, partidos, sessMes, votMes, nomes, info };
}
const zero = () => ({ sE: 0, sP: 0, vE: 0, vS: 0, vN: 0, vA: 0, vO: 0, vX: 0, cV: 0, oE: 0, pA: 0, pC: 0 });
const add = (a, r) => { for (const k of F) a[k] += r[k]; return a; };
const fin = (a) => {
  a.aus = a.sE - a.sP; a.pres = a.sE ? a.sP / a.sE : null; a.taus = a.sE ? a.aus / a.sE : null;
  a.vot = a.vS + a.vN + a.vA + a.vO + a.vX; a.nvot = Math.max(0, a.vE - a.vot); a.pvot = a.vE ? a.vot / a.vE : null;
  a.pabs = a.vot ? a.vA / a.vot : null; a.pobs = a.vot ? a.vO / a.vot : null;
  return a;
};
const total = (rows) => fin(rows.reduce(add, zero()));
function porDeputado(rows) {
  const m = new Map();
  for (const r of rows) {
    let a = m.get(r.id);
    if (!a) { a = Object.assign(zero(), { id: r.id, nome: r.nome, uf: r.uf, p: r.p, um: r.m }); m.set(r.id, a); }
    if (r.m >= a.um) { a.um = r.m; a.p = r.p; a.uf = r.uf; }
    add(a, r);
  }
  return [...m.values()].map(fin);
}
function porPartido(rows, nSess) {
  const m = new Map();
  for (const r of rows) { let a = m.get(r.p); if (!a) { a = Object.assign(zero(), { p: r.p }); m.set(r.p, a); } add(a, r); }
  return [...m.values()].map(fin).map((a) => { a.banc = nSess ? a.sE / nSess : 0; a.ppd = a.banc >= 1 ? a.pA / a.banc : null; return a; });
}
function porMes(rows, meses) {
  const m = new Map(meses.map((k) => [k, zero()]));
  for (const r of rows) { const a = m.get(r.m); if (a) add(a, r); }
  return meses.map((k) => Object.assign(fin(m.get(k)), { m: k }));
}
function lerFiltros() {
  const p = dash.params() || {};
  const minimo = Number(p.minimo);
  return {
    anos: Array.isArray(p.anos) ? p.anos.map(String) : [],
    partido: p.partido ? String(p.partido) : null,
    uf: p.uf ? String(p.uf) : null,
    deputado: p.deputado != null && p.deputado !== '' ? String(p.deputado) : null,
    minimo: Number.isFinite(minimo) && p.minimo != null ? minimo : 25,
  };
}
function contexto(D) {
  const P = lerFiltros();
  const anos = P.anos.filter((a) => D.anos.includes(a));
  const meses = D.meses.filter((m) => !anos.length || anos.includes(m.slice(0, 4)));
  const mset = new Set(meses);
  const base = D.rows.filter((r) => mset.has(r.m));
  const geo = P.uf ? base.filter((r) => r.uf === P.uf) : base;
  const scope = P.partido ? geo.filter((r) => r.p === P.partido) : geo;
  const depRows = P.deputado ? base.filter((r) => r.id === P.deputado) : null;
  const slice = depRows || scope;
  const nSess = d3.sum(meses, (m) => D.sessMes.get(m));
  const nVot = d3.sum(meses, (m) => D.votMes.get(m));
  const comSessao = meses.filter((m) => D.sessMes.get(m) > 0);
  const minSess = Math.max(1, Math.ceil(nSess * P.minimo / 100));
  const baseDeps = porDeputado(base);
  const taxas = baseDeps.filter((d) => d.sE >= minSess).map((d) => d.pres).sort(d3.ascending);
  const pctl = new Map();
  for (const d of baseDeps) pctl.set(d.id, d.sE >= minSess && taxas.length ? d3.bisectRight(taxas, d.pres) / taxas.length : null);
  const comPctl = (lista) => lista.map((d) => Object.assign(d, { pctl: pctl.has(d.id) ? pctl.get(d.id) : null }));
  return {
    D, P, anos, meses, base, geo, scope, slice, nSess, nVot,
    minSess, minVot: Math.max(1, Math.ceil(nVot * P.minimo / 100)),
    de: comSessao[0] || meses[0], ate: comSessao[comSessao.length - 1] || meses[meses.length - 1],
    tot: total(slice), deps: comPctl(porDeputado(scope)), parts: porPartido(geo, nSess), nPctl: taxas.length, baseDeps,
    dep: depRows ? (comPctl(porDeputado(depRows))[0] || null) : null,
    filtrado: !!(P.partido || P.uf || P.deputado),
  };
}
const partidosComBancada = (c) => c.parts.filter((a) => a.p !== SEM && a.banc >= 1);
const rotuloRecorte = (c) => {
  if (c.P.deputado) return c.dep ? c.dep.nome : (c.D.nomes.get(c.P.deputado) || 'Deputado');
  if (c.P.partido && c.P.uf) return c.P.partido + ' em ' + c.P.uf;
  return c.P.partido || c.P.uf || 'Câmara';
};

/* ---------- motivos das ausências (Senado) ---------- */
const NCOM = 'Não compareceu';
let cache5 = { key: '', A: null };
function prepAusencias(rows) { return rows.map((r) => ({ id: String(r.id_deputado), m: String(r.mes), p: String(r.partido), mot: String(r.motivo), n: +r.sessoes || 0 })); }
function contextoAusencias(c, A) {
  const mset = new Set(c.meses);
  const info = (id) => c.D.info.get(id) || {};
  const doPeriodo = A.filter((r) => mset.has(r.m) && (!c.P.uf || info(r.id).uf === c.P.uf));
  const rec = doPeriodo.filter((r) => (!c.P.partido || r.p === c.P.partido) && (!c.P.deputado || r.id === c.P.deputado));
  const porDep = new Map();
  for (const r of doPeriodo) { let a = porDep.get(r.id); if (!a) { a = { ncom: 0, just: 0 }; porDep.set(r.id, a); } if (r.mot === NCOM) a.ncom += r.n; else a.just += r.n; }
  const ncom = d3.sum(rec, (r) => (r.mot === NCOM ? r.n : 0)), aus = d3.sum(rec, (r) => r.n);
  return { rec, porDep, total: { aus, ncom, just: aus - ncom } };
}
function secaoAusencias(c) {
  if (!SENADO) return;
  if (!c.ca) { for (const k of ['motivos', 'ncom']) { const b = caixa(k); b.classList.remove('dash-skeleton'); b.replaceChildren(el('p', 'cp-card-n', dash.data('ausencias').status === 'error' ? 'Não foi possível carregar os motivos.' : 'Carregando motivos…')); } return; }
  for (const k of ['motivos', 'ncom']) caixa(k).classList.remove('dash-skeleton');
  const por = d3.rollups(c.ca.rec, (rs) => d3.sum(rs, (r) => r.n), (r) => r.mot).sort((a, b) => (a[0] === NCOM) - (b[0] === NCOM) || b[1] - a[1]);
  const tot = d3.sum(por, (x) => x[1]) || 1;
  nota('motivos', 'Sessões com votação nominal em que ' + (c.P.deputado ? 'o senador' : 'senadores do recorte') + ' não votaram nem registraram presença, pelo motivo informado. Atividade parlamentar é declarada pelo próprio senador; “não compareceu” é a falta sem justificativa.');
  barras(caixa('motivos'), por.map(([k, v]) => ({ chave: k, rotulo: k, valor: v, texto: num(v) + ' · ' + pct(v / tot, 0), tip: () => [{ h: k }, { k: 'Sessões', v: num(v) }, { k: 'Das ausências', v: pct(v / tot) }] })),
    { cor: C[0], vazio: 'Nenhuma ausência com os filtros escolhidos.' });
  for (const b of caixa('motivos').querySelectorAll('.cp-hb')) if (b.querySelector('.cp-hb-l').textContent === NCOM) b.querySelector('.cp-hb-f').style.background = 'var(--color-bad)';
  const lista = c.deps.filter((d) => d.sE >= c.minSess).map((d) => Object.assign(d, { ncom: (c.ca.porDep.get(d.id) || {}).ncom || 0, just: (c.ca.porDep.get(d.id) || {}).just || 0 }))
    .filter((d) => d.ncom > 0).sort((a, b) => b.ncom - a.ncom || b.ncom / b.sE - a.ncom / a.sE).slice(0, 15);
  nota('ncom', criterio(c) + ' Sessões em que o senador estava em exercício e foi registrado como “não compareceu”.');
  const max = lista.length ? lista[0].ncom : 1;
  ranking(caixa('ncom'), lista, { rotulo: 'Faltas', valor: (d) => num(d.ncom), sub: (d) => pct(d.ncom / d.sE) + ' das ' + num(d.sE) + ' sessões · ' + qtd(d.just, 'ausência justificada', 'ausências justificadas'), bar: (d) => d.ncom / max, vazio: 'Nenhuma falta sem justificativa com os filtros escolhidos.' }, c);
}

/* ---------- votações, pauta e alinhamento ---------- */
const FONTES_VOT = ['pauta', 'partidos_votacao', 'alinhamento'];
const n0 = (x) => +x || 0;
function prepVot(pauta, pv, al) {
  const vot = pauta.map((r) => { const data = String(r.data).slice(0, 10); return {
    id: String(r.id_votacao), data, m: data.slice(0, 7), prop: String(r.proposicao || ''), pid: String(r.id_proposicao || ''), tipo: String(r.tipo || ''),
    ementa: String(r.ementa || ''), tema: String(r.tema || 'Sem tema'), etapa: String(r.etapa || ''), desc: String(r.votacao || ''), aprov: n0(r.aprovada),
    sim: n0(r.sim), nao: n0(r.nao), abs: n0(r.abstencoes), obs: n0(r.obstrucoes), votos: n0(r.votos), gov: String(r.orient_governo || ''), opo: String(r.orient_oposicao || '') }; });
  const byId = new Map(vot.map((v) => [v.id, v]));
  const pvr = pv.map((r) => ({ id: String(r.id_votacao), p: String(r.partido), sim: n0(r.sim), nao: n0(r.nao), abs: n0(r.abstencoes), obs: n0(r.obstrucoes), out: n0(r.outros), ori: String(r.orientacao || '') }));
  const alr = al.map((r) => ({ id: String(r.id_deputado), m: String(r.mes), p: String(r.partido), votos: n0(r.votos), bb: n0(r.base_bancada), cb: n0(r.com_bancada),
    bg: n0(r.base_governo), cg: n0(r.com_governo), obs: n0(r.obstrucoes), oo: n0(r.obst_orientadas), ob: n0(r.obst_bancada), oi: n0(r.obst_isoladas) }));
  return { vot, byId, pvr, alr };
}
const GOV_INI = '2023-01';
function somaAl(rows, chave) {
  const m = new Map();
  for (const r of rows) {
    const k = chave(r); let a = m.get(k);
    if (!a) { a = { k, votos: 0, bb: 0, cb: 0, bg: 0, cg: 0, obs: 0, oo: 0, ob: 0, oi: 0 }; m.set(k, a); }
    a.votos += r.votos; a.bb += r.bb; a.cb += r.cb; a.obs += r.obs; a.oo += r.oo; a.ob += r.ob; a.oi += r.oi;
    if (r.m >= GOV_INI) { a.bg += r.bg; a.cg += r.cg; }
  }
  for (const a of m.values()) { a.fid = a.bb ? a.cb / a.bb : null; a.gov = a.bg ? a.cg / a.bg : null; }
  return m;
}
function contextoVot(c, V) {
  const mset = new Set(c.meses);
  const vots = V.vot.filter((v) => mset.has(v.m));
  const vids = new Set(vots.map((v) => v.id));
  const pvAll = V.pvr.filter((r) => vids.has(r.id));
  const pv = c.P.partido ? pvAll.filter((r) => r.p === c.P.partido) : pvAll;
  const alAll = V.alr.filter((r) => mset.has(r.m));
  const ufDe = (id) => (c.D.info.get(id) || {}).uf;
  const alGeo = c.P.uf ? alAll.filter((r) => ufDe(r.id) === c.P.uf) : alAll;
  return { V, vots, vids, pvAll, pv, alAll, alGeo, porDep: somaAl(alAll, (r) => r.id), porPart: somaAl(alGeo, (r) => r.p) };
}
function aguardandoVot(keys) {
  const st = FONTES_VOT.map((id) => dash.data(id).status);
  const erro = st.some((x) => x === 'error' || x === 'declined');
  for (const k of keys) { const b = caixa(k); if (!b) continue; b.classList.remove('dash-skeleton'); b.replaceChildren(erro ? el('div', 'cp-err', 'Não foi possível carregar') : el('p', 'cp-card-n', 'Carregando votações…')); }
}
function colunasEmpilhadas(box, meses, series, rotulo) {
  const tot = meses.map((m, i) => d3.sum(series, (s) => s.valores[i]));
  const max = d3.max(tot) || 0;
  if (!max) return vazio(box, 'Nenhuma obstrução com os filtros escolhidos.');
  const f = moldura(box, meses, [0, d3.nice(0, max, 4)[1]], (t) => num(t), true, 8);
  const larg = Math.min(24, f.x.bandwidth());
  const g = f.svg.append('g');
  meses.forEach((m, i) => {
    let base = 0;
    series.forEach((s) => {
      const v = s.valores[i]; if (!v) return;
      const y0 = f.y(base), y1 = f.y(base + v), h = Math.max(1, y0 - y1 - (base > 0 ? 2 : 0));
      g.append('rect').attr('x', f.cx(m) - larg / 2).attr('width', larg).attr('y', y0 - (base > 0 ? 2 : 0) - h).attr('height', h).attr('rx', 2).attr('fill', s.cor).attr('data-i', i);
      base += v;
    });
  });
  f.svg.append('rect').attr('x', f.ml).attr('y', 0).attr('width', Math.max(0, f.W - f.ml - f.mr)).attr('height', f.H).attr('fill', 'transparent')
    .on('pointermove', (ev) => {
      const i = mesMaisProximo(f, meses, d3.pointer(ev, f.svg.node())[0]);
      g.selectAll('rect').attr('opacity', function () { return +this.getAttribute('data-i') === i ? 1 : 0.5; });
      mostrarTip(box, ev, [{ h: mesNome(meses[i]) }, ...series.map((s) => ({ c: s.cor, k: s.nome, v: num(s.valores[i]) })), { k: rotulo, v: num(tot[i]) }]);
    })
    .on('pointerleave', () => { g.selectAll('rect').attr('opacity', 1); esconderTip(box); });
}
function secaoObstrucao(c) {
  const keys = ['obsMes', 'obsPart', 'contraBancada', 'gov'];
  if (!c.cv) return aguardandoVot(keys);
  for (const k of keys) caixa(k).classList.remove('dash-skeleton');
  const cv = c.cv, V = cv.V;
  // por mês e partido
  const porP = d3.rollup(cv.pvAll, (rs) => d3.sum(rs, (r) => r.obs), (r) => r.p);
  let principais;
  if (c.P.partido) principais = [c.P.partido];
  else principais = [...porP].filter((x) => x[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 3).map((x) => x[0]);
  const idx = new Map(c.meses.map((m, i) => [m, i]));
  const series = principais.map((p, i) => ({ nome: p, cor: C[i], valores: c.meses.map(() => 0) }));
  const demais = { nome: c.P.partido ? 'Demais partidos' : 'Demais partidos', cor: MUTED, valores: c.meses.map(() => 0) };
  for (const r of cv.pvAll) { if (!r.obs) continue; const i = idx.get(V.byId.get(r.id).m); const s = series.find((x) => x.nome === r.p) || demais; s.valores[i] += r.obs; }
  const todas = [...series, demais].filter((s) => d3.sum(s.valores) > 0);
  legenda('obsMes', todas.map((s) => ({ nome: s.nome, c: s.cor })));
  colunasEmpilhadas(caixa('obsMes'), c.meses, todas, 'Total');
  // origem da obstrução por partido
  const parts = [...cv.porPart.values()].filter((a) => a.obs > 0).map((a) => ({ p: a.k, obs: a.obs, po: a.oo / a.obs, pb: a.ob / a.obs, pi: a.oi / a.obs }));
  tabela(caixa('obsPart'), parts, [
    { k: 'p', h: 'Partido', l: 1, f: (d) => d.p },
    { k: 'obs', h: 'Obstruções', f: (d) => num(d.obs) },
    { k: 'po', h: 'Orientadas', f: (d) => pct(d.po, 0), bar: (d) => d.po },
    { k: 'pb', h: 'Com a bancada', f: (d) => pct(d.pb, 0) },
    { k: 'pi', h: 'Isoladas', f: (d) => pct(d.pi, 0) },
  ], ui.sortObs, 'partido', c.P.partido, 'obs');
  // contra a bancada
  const minV = c.minVot;
  const escopo = new Set(c.deps.map((d) => d.id));
  const lista = [...cv.porDep.values()].filter((a) => escopo.has(a.k) && a.bb >= minV && a.fid != null)
    .map((a) => Object.assign({}, c.D.info.get(a.k) || { id: a.k, nome: a.k, uf: '', p: '' }, { fid: a.fid, bb: a.bb, cb: a.cb }))
    .sort((a, b) => a.fid - b.fid || b.bb - a.bb).slice(0, 15);
  nota('contraBancada', 'Parcela dos votos dados igual ao voto da maioria do próprio partido. ' + (c.P.minimo > 0 ? 'Entre quem votou em ao menos ' + num(minV) + ' votações com bancada definida.' : ''));
  ranking(caixa('contraBancada'), lista, { rotulo: 'Com a bancada', valor: (d) => pct(d.fid), sub: (d) => num(d.bb - d.cb) + ' votos contra a maioria do partido em ' + num(d.bb), bar: (d) => d.fid, vazio: 'Ninguém atende ao mínimo de votações com os filtros escolhidos.' }, c);
  // alinhamento ao governo por partido
  const ps = partidosComBancada(c).map((a) => cv.porPart.get(a.p)).filter((a) => a && a.gov != null).sort((a, b) => b.gov - a.gov);
  legenda('gov', [{ nome: 'Com o governo', c: C[0] }, { nome: 'Contra o governo', c: C[1] }]);
  barras(caixa('gov'), ps.map((a) => ({
    chave: a.k, rotulo: a.k, valor: a.gov, texto: pct(a.gov, 0) + ' · coesão ' + pct(a.fid, 0),
    segs: [{ v: a.cg, cor: C[0], nome: 'Com o governo' }, { v: a.bg - a.cg, cor: C[1], nome: 'Contra o governo' }],
  })), { marcado: c.P.partido, aoClicar: alternarPartido, vazio: 'Nenhuma votação com orientação do governo no período escolhido. O alinhamento começa em janeiro de 2023.' });
}

function agregaProps(cv, c) {
  const m = new Map();
  const q = semAcento(ui.qPauta.trim());
  for (const v of cv.vots) {
    if (ui.tema && v.tema !== ui.tema) continue;
    const chave = v.pid || v.prop || v.id;
    let a = m.get(chave);
    if (!a) { a = { chave, pid: v.pid, prop: v.prop || 'Sem proposição', tema: v.tema, ementa: v.ementa, n: 0, obs: 0, ult: '', res: null, resData: '', ids: [] }; m.set(chave, a); }
    a.n++; a.obs += v.obs; a.ids.push(v.id); if (v.data > a.ult) a.ult = v.data;
    if (v.etapa === 'Texto principal' && v.data >= a.resData) { a.resData = v.data; a.res = v.aprov; }
  }
  let lista = [...m.values()];
  if (q) lista = lista.filter((a) => semAcento(a.prop + ' ' + a.ementa + ' ' + a.tema).includes(q));
  if (c.P.partido) {
    const porVot = new Map(cv.pv.map((r) => [r.id, r]));
    for (const a of lista) { const t = { sim: 0, nao: 0, obs: 0, n: 0 }; for (const id of a.ids) { const r = porVot.get(id); if (r) { t.sim += r.sim; t.nao += r.nao; t.obs += r.obs; t.n += r.sim + r.nao + r.abs + r.obs + r.out; } } a.ps = t.n ? t : null; a.psim = t.n ? t.sim / t.n : null; }
  }
  return lista;
}
const fmtData = (d) => d ? d.slice(8, 10) + '/' + d.slice(5, 7) + '/' + d.slice(0, 4) : '—';
const linkProp = (pid) => (!pid ? null : SENADO ? 'https://www25.senado.leg.br/web/atividade/materias/-/materia/' + encodeURIComponent(pid) : 'https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=' + encodeURIComponent(pid));
function paginaPauta(c) {
  const keys = ['temas', 'etapas', 'obstTema', 'props'];
  if (!c.cv) return aguardandoVot(keys);
  for (const k of keys) caixa(k).classList.remove('dash-skeleton');
  const cv = c.cv;
  // temas
  const porTema = d3.rollups(cv.vots, (vs) => ({ n: vs.length, props: new Set(vs.map((v) => v.pid || v.prop)).size, obs: d3.sum(vs, (v) => v.obs) }), (v) => v.tema).sort((a, b) => b[1].n - a[1].n);
  barras(caixa('temas'), porTema.map(([t, o]) => ({
    chave: t, rotulo: t, valor: o.n, texto: num(o.n),
    tip: () => [{ h: t }, { k: 'Votações nominais', v: num(o.n) }, { k: 'Proposições', v: num(o.props) }, { k: 'Obstruções registradas', v: num(o.obs) }],
  })), { cor: C[0], marcado: ui.tema, aoClicar: (t) => { ui.tema = ui.tema === t ? null : t; ui.prop = null; desenharPagina(); }, vazio: 'Nenhuma votação nominal no período escolhido.' });
  // etapas
  const ETAPAS = ['Texto principal', 'Destaque ou emenda', 'Requerimento'];
  const porEtapa = new Map(d3.rollups(cv.vots, (vs) => ({ n: vs.length, obs: d3.sum(vs, (v) => v.obs) }), (v) => v.etapa));
  const totObs = d3.sum(cv.vots, (v) => v.obs);
  barras(caixa('etapas'), ETAPAS.filter((e) => porEtapa.has(e)).map((e) => { const o = porEtapa.get(e); return {
    chave: e, rotulo: e === 'Destaque ou emenda' ? 'Destaques e emendas' : e === 'Requerimento' ? 'Requerimentos' : e, valor: o.n, texto: num(o.n),
    tip: () => [{ h: e }, { k: 'Votações', v: num(o.n) }, { k: 'Obstruções', v: num(o.obs) + (totObs ? ' (' + pct(o.obs / totObs, 0) + ' do total)' : '') }],
  }; }), { cor: C[0], vazio: 'Nenhuma votação nominal no período escolhido.' });
  // obstruções por tema (respeita o partido)
  const obsTema = d3.rollups(cv.pv.filter((r) => r.obs > 0), (rs) => d3.sum(rs, (r) => r.obs), (r) => cv.V.byId.get(r.id).tema).sort((a, b) => b[1] - a[1]).slice(0, 10);
  nota('obstTema', 'Os dez temas com mais registros de obstrução' + (c.P.partido ? ' de deputados do ' + c.P.partido : '') + ' no período.');
  barras(caixa('obstTema'), obsTema.map(([t, n]) => ({ chave: t, rotulo: t, valor: n, texto: num(n), tip: () => [{ h: t }, { k: 'Obstruções', v: num(n) }] })),
    { cor: C[1], vazio: 'Nenhuma obstrução com os filtros escolhidos.' });
  // proposições
  const lista = agregaProps(cv, c);
  const tp = root.querySelector('.cp-tema-picked'); tp.hidden = !ui.tema; tp.textContent = ui.tema ? ui.tema + ' ×' : '';
  nota('props', qtd(lista.length, 'proposição', 'proposições') + (ui.tema ? ' do tema escolhido' : '') + ' com votação nominal no Plenário no período. Clique em uma linha para ver cada votação' + (c.P.partido ? ' e como o ' + c.P.partido + ' votou.' : '.'));
  const cols = [
    { k: 'prop', h: 'Proposição', l: 1, f: (d) => d.prop, link: (d) => linkProp(d.pid) },
    { k: 'tema', h: 'Tema', l: 1, f: (d) => d.tema },
    { k: 'ementa', h: 'Assunto', l: 1, wrap: 1, f: (d) => (d.ementa.length > 170 ? d.ementa.slice(0, 170).replace(/\s+\S*$/, '') + '…' : d.ementa || '—') },
    { k: 'n', h: 'Votações', f: (d) => num(d.n) },
    { k: 'obs', h: 'Obstruções', f: (d) => num(d.obs) },
    { k: 'res', h: 'Texto principal', f: (d) => (d.res == null ? '—' : d.res ? 'Aprovado' : 'Rejeitado'), s: (d) => d.res },
    { k: 'ult', h: 'Última votação', f: (d) => fmtData(d.ult) },
  ];
  if (c.P.partido) cols.splice(5, 0, { k: 'psim', h: 'Votos do ' + c.P.partido, f: (d) => (d.ps ? 'Sim ' + pct(d.ps.sim / d.ps.n, 0) + ' · Não ' + pct(d.ps.nao / d.ps.n, 0) + (d.ps.obs ? ' · Obstr. ' + pct(d.ps.obs / d.ps.n, 0) : '') : '—') });
  tabela(caixa('props'), lista, cols, ui.sortPauta, 'prop', ui.prop, 'pauta');
  detalheProp(c);
}
function detalheProp(c) {
  const card = root.querySelector('#pauta-detalhe');
  const cv = c.cv;
  const vs = ui.prop ? cv.vots.filter((v) => (v.pid || v.prop || v.id) === ui.prop) : [];
  card.hidden = !vs.length; if (!vs.length) return;
  root.querySelector('[data-n="detT"]').textContent = 'Votações da ' + (vs[0].prop || 'proposição');
  nota('detE', vs[0].ementa);
  const porVot = c.P.partido ? new Map(cv.pv.map((r) => [r.id, r])) : null;
  const linhas = vs.map((v) => Object.assign({}, v, { pp: porVot ? porVot.get(v.id) : null }));
  const cols = [
    { k: 'data', h: 'Data', l: 1, f: (d) => fmtData(d.data) },
    { k: 'etapa', h: 'Etapa', l: 1, f: (d) => d.etapa },
    { k: 'desc', h: 'Votação', l: 1, wrap: 1, f: (d) => d.desc },
    { k: 'sim', h: 'Sim', f: (d) => num(d.sim) },
    { k: 'nao', h: 'Não', f: (d) => num(d.nao) },
    { k: 'obs', h: 'Obstr.', f: (d) => num(d.obs) },
    { k: 'gov', h: 'Governo orientou', l: 1, f: (d) => d.gov || '—' },
  ];
  if (c.P.partido) cols.push({ k: 'pp', h: c.P.partido, l: 1, f: (d) => (d.pp ? ['Sim ' + d.pp.sim, 'Não ' + d.pp.nao, d.pp.obs ? 'Obstr. ' + d.pp.obs : '', d.pp.ori ? 'orientou ' + d.pp.ori : ''].filter(Boolean).join(' · ') : '—'), s: (d) => (d.pp ? d.pp.sim : null) });
  tabela(caixa('det'), linhas, cols, ui.sortDet, 'vot', null, 'det');
}


/* ---------- cota parlamentar ---------- */
const FONTES_GASTOS = ['gastos_mes', 'gastos_categoria', 'fornecedores'];
const brl0 = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const brlC = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', notation: 'compact', maximumFractionDigits: 1 });
const reais = (x) => (x == null || !isFinite(x) ? '—' : brl0.format(x));
const reaisC = (x) => (x == null || !isFinite(x) ? '—' : Math.abs(x) < 10000 ? brl0.format(x) : brlC.format(x));
function prepGastos(gm, gc, gf) {
  return {
    mes: gm.map((r) => ({ id: String(r.id_deputado), m: String(r.mes), p: String(r.partido), v: +r.valor || 0, n: +r.documentos || 0 })),
    cat: gc.map((r) => ({ id: String(r.id_deputado), ano: String(r.ano), p: String(r.partido), cat: String(r.categoria), v: +r.valor || 0 })),
    forn: gf.map((r) => ({ id: String(r.id_deputado), ano: String(r.ano), forn: String(r.fornecedor || ''), doc: String(r.documento || ''), cat: String(r.categoria), v: +r.valor || 0, n: +r.documentos || 0 })),
  };
}
function contextoGastos(c, G) {
  const mset = new Set(c.meses), anos = new Set(c.meses.map((m) => m.slice(0, 4)));
  const info = (id) => c.D.info.get(id) || {};
  const geo = (r) => !c.P.uf || info(r.id).uf === c.P.uf;
  const recorte = (r) => geo(r) && (!c.P.partido || r.p === c.P.partido) && (!c.P.deputado || r.id === c.P.deputado);
  const mesGeo = G.mes.filter((r) => mset.has(r.m) && geo(r));
  // meses de mandato: esperado em sessão ou com despesa registrada
  const mandato = new Map();
  const marca = (id, m, p) => { const k = id + '|' + m; if (!mandato.has(k)) mandato.set(k, p); };
  for (const r of mesGeo) marca(r.id, r.m, r.p);
  for (const r of c.geo) if (r.sE > 0) marca(r.id, r.m, r.p);
  const mesesDep = new Map(), mesesPart = new Map();
  for (const [k, p] of mandato) { const id = k.split('|')[0]; mesesDep.set(id, (mesesDep.get(id) || 0) + 1); mesesPart.set(p, (mesesPart.get(p) || 0) + 1); }
  const totalDep = new Map(), totalPart = new Map();
  for (const r of mesGeo) { totalDep.set(r.id, (totalDep.get(r.id) || 0) + r.v); totalPart.set(r.p, (totalPart.get(r.p) || 0) + r.v); }
  const mensal = new Map(); for (const [id, v] of totalDep) mensal.set(id, v / (mesesDep.get(id) || 1));
  const mes = mesGeo.filter(recorte);
  const pares = [...mandato].filter(([k, p]) => { const id = k.split('|')[0]; return (!c.P.partido || p === c.P.partido) && (!c.P.deputado || id === c.P.deputado); }).length;
  return {
    G, mes, total: d3.sum(mes, (r) => r.v), pares, totalDep, mesesDep, mensal, totalPart, mesesPart,
    cat: G.cat.filter((r) => anos.has(r.ano) && recorte(r)),
    forn: G.forn.filter((r) => anos.has(r.ano) && geo(r) && (!c.P.deputado || r.id === c.P.deputado) && (!c.P.partido || info(r.id).p === c.P.partido)),
  };
}
function aguardandoGastos(keys) {
  const st = FONTES_GASTOS.map((id) => dash.data(id).status);
  const erro = st.some((x) => x === 'error');
  for (const k of keys) { const b = caixa(k); if (!b) continue; b.classList.remove('dash-skeleton'); b.replaceChildren(erro ? el('div', 'cp-err', 'Não foi possível carregar os gastos') : el('p', 'cp-card-n', 'Carregando gastos…')); }
}
function dispersao(box, pontos, c) {
  box.replaceChildren();
  if (pontos.length < 3) return vazio(box, 'Poucos deputados com nota e gasto no recorte escolhido.');
  const W = Math.max(280, Math.floor(box.clientWidth)), H = 340, mt = 14, mb = 34, mr = 14;
  const svg = d3.select(box).append('svg').attr('class', 'cp-svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', 'Gasto mensal da cota contra a nota de trabalho');
  const ymax = d3.quantile(pontos.map((p) => p.y).sort(d3.ascending), 0.995) * 1.05 || 1;
  const y = d3.scaleLinear([0, d3.nice(0, ymax, 5)[1]], [H - mb, mt]);
  const yt = y.ticks(5);
  const g = svg.append('g');
  const rot = g.selectAll('text').data(yt).join('text').attr('y', (t) => y(t)).attr('dy', '0.32em').text((t) => reaisC(t));
  let ml = 0; rot.each(function (t) { ml = Math.max(ml, this.getComputedTextLength() || reaisC(t).length * 6.5); });
  ml = Math.ceil(ml) + 10; rot.attr('x', ml - 8).attr('text-anchor', 'end');
  const x = d3.scaleLinear([0, 100], [ml, W - mr]);
  g.selectAll('line.gy').data(yt).join('line').attr('x1', ml).attr('x2', W - mr).attr('y1', (t) => y(t)).attr('y2', (t) => y(t)).attr('stroke', 'var(--ds-chart-grid)');
  svg.append('g').selectAll('text').data(x.ticks(5)).join('text').attr('x', (t) => x(t)).attr('y', H - mb + 16).attr('text-anchor', 'middle').text((t) => t);
  svg.append('text').attr('x', W - mr).attr('y', H - 4).attr('text-anchor', 'end').text('Nota de trabalho →');
  const mx = d3.median(pontos, (p) => p.x), my = d3.median(pontos, (p) => p.y);
  svg.append('line').attr('x1', x(mx)).attr('x2', x(mx)).attr('y1', mt).attr('y2', H - mb).attr('stroke', 'var(--ds-chart-reference)').attr('stroke-dasharray', '4 3');
  svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', y(Math.min(my, y.domain()[1]))).attr('y2', y(Math.min(my, y.domain()[1]))).attr('stroke', 'var(--ds-chart-reference)').attr('stroke-dasharray', '4 3');
  svg.append('text').attr('x', W - mr - 4).attr('y', y(Math.min(my, y.domain()[1])) - 6).attr('text-anchor', 'end').text('mediana ' + reaisC(my) + '/mês');
  const cy = (p) => y(Math.min(p.y, y.domain()[1]));
  const sel = c.P.deputado;
  const pts = svg.append('g');
  pts.selectAll('circle').data(pontos.filter((p) => p.id !== sel)).join('circle').attr('cx', (p) => x(p.x)).attr('cy', cy).attr('r', 4)
    .attr('fill', (p) => (p.destaque ? C[0] : MUTED)).attr('fill-opacity', (p) => (p.destaque ? 0.85 : 0.7)).attr('stroke', 'var(--color-panel)').attr('stroke-width', 1);
  const escolhido = pontos.find((p) => p.id === sel);
  if (escolhido) {
    pts.append('circle').attr('cx', x(escolhido.x)).attr('cy', cy(escolhido)).attr('r', 7).attr('fill', 'var(--color-fg)').attr('stroke', 'var(--color-panel)').attr('stroke-width', 2);
    const t = svg.append('text').attr('class', 'cp-end').attr('y', cy(escolhido) - 12).text(escolhido.nome);
    const lw = t.node().getComputedTextLength() || escolhido.nome.length * 7;
    t.attr('x', Math.min(Math.max(x(escolhido.x) - lw / 2, ml), W - mr - lw));
  }
  const anel = svg.append('circle').attr('r', 7).attr('fill', 'none').attr('stroke', 'var(--color-fg)').attr('stroke-width', 1.5).attr('display', 'none');
  const del = d3.Delaunay.from(pontos, (p) => x(p.x), (p) => cy(p));
  svg.append('rect').attr('x', ml).attr('y', mt).attr('width', W - ml - mr).attr('height', H - mt - mb).attr('fill', 'transparent').style('cursor', 'pointer')
    .on('pointermove', (ev) => {
      const [px, py] = d3.pointer(ev, svg.node()); const i = del.find(px, py); const p = pontos[i];
      if (!p || Math.hypot(x(p.x) - px, cy(p) - py) > 28) { anel.attr('display', 'none'); esconderTip(box); return; }
      anel.attr('display', null).attr('cx', x(p.x)).attr('cy', cy(p));
      mostrarTip(box, ev, [{ h: p.nome + ' · ' + p.p + '-' + p.uf }, { k: 'Gasto por mês', v: reais(p.y) }, { k: 'Nota de trabalho', v: fmtNota(p.x) }, { k: 'Total no período', v: reais(p.total) }]);
    })
    .on('pointerleave', () => { anel.attr('display', 'none'); esconderTip(box); })
    .on('click', (ev) => { const [px, py] = d3.pointer(ev, svg.node()); const p = pontos[del.find(px, py)]; if (p && Math.hypot(x(p.x) - px, cy(p) - py) <= 28) escolherDeputado(p.id); });
}
function paginaGastos(c) {
  const keys = ['gMes', 'gMais', 'gMenos', 'gScatter', 'gCat', 'gPart', 'gForn'];
  if (!c.cg) return aguardandoGastos(keys);
  for (const k of keys) caixa(k).classList.remove('dash-skeleton');
  const cg = c.cg;
  // por mês
  const porMesG = d3.rollup(cg.mes, (rs) => d3.sum(rs, (r) => r.v), (r) => r.m);
  colunasMensais(caixa('gMes'), c.meses, c.meses.map((m) => porMesG.get(m) || 0), C[0], 'Reembolsado', reais, 'Nenhum gasto registrado com os filtros escolhidos.', reaisC);
  // rankings por mês de mandato
  const escopo = new Set(c.deps.map((d) => d.id));
  const elegiveis = [...cg.mensal].filter(([id]) => escopo.has(id) && (c.deps.find((d) => d.id === id) || {}).sE >= c.minSess)
    .map(([id, v]) => Object.assign({}, c.D.info.get(id) || { id, nome: id, p: '', uf: '' }, { id, mensal: v, total: cg.totalDep.get(id), meses: cg.mesesDep.get(id) }));
  const crit = criterio(c) + ' Gasto dividido pelos meses de mandato no período.';
  nota('gMais', crit); nota('gMenos', crit);
  const maxM = d3.max(elegiveis, (d) => d.mensal) || 1;
  const opG = { rotulo: 'Por mês', valor: (d) => reaisC(d.mensal), sub: (d) => reais(d.total) + ' em ' + qtd(d.meses, 'mês', 'meses'), bar: (d) => d.mensal / maxM, vazio: 'Ninguém atende ao mínimo de sessões com os filtros escolhidos.' };
  ranking(caixa('gMais'), [...elegiveis].sort((a, b) => b.mensal - a.mensal).slice(0, 15), opG, c);
  ranking(caixa('gMenos'), [...elegiveis].sort((a, b) => a.mensal - b.mensal).slice(0, 15), opG, c);
  // dispersão gasto x nota
  const T = notasTrabalho(c);
  const recorte = !!(c.P.partido || c.P.uf);
  const pontos = [...cg.mensal].map(([id, v]) => { const o = T.notas.get(id); if (!o || o.nota == null) return null; const inf = c.D.info.get(id) || {};
    return { id, x: o.nota, y: v, total: cg.totalDep.get(id), nome: inf.nome || id, p: inf.p || '', uf: inf.uf || '', destaque: !recorte || escopo.has(id) }; }).filter(Boolean);
  nota('gScatter', 'Cada ponto é um deputado que atinge o mínimo de sessões: nota de trabalho (aba Trabalho) contra gasto da cota por mês de mandato. As linhas tracejadas marcam as medianas. Embaixo à direita ficam os que trabalham mais e gastam menos.' + (recorte ? ' Em azul, o recorte filtrado.' : '') + ' Clique em um ponto para ver o deputado.');
  legenda('gScatter', recorte ? [{ nome: c.P.partido && c.P.uf ? c.P.partido + ' em ' + c.P.uf : (c.P.partido || c.P.uf), c: C[0] }, { nome: 'Demais deputados', c: MUTED }] : []);
  dispersao(caixa('gScatter'), pontos, c);
  // categorias
  // categorias com saldo negativo (estornos, como a complementação do auxílio-moradia) ficam fora das barras
  const porCat = d3.rollups(cg.cat, (rs) => d3.sum(rs, (r) => r.v), (r) => r.cat).filter((x) => x[1] > 0).sort((a, b) => b[1] - a[1]);
  const totCat = d3.sum(porCat, (x) => x[1]) || 1;
  barras(caixa('gCat'), porCat.map(([k, v]) => ({ chave: k, rotulo: k, valor: v, texto: reaisC(v) + ' · ' + pct(v / totCat, 0), tip: () => [{ h: k }, { k: 'Valor', v: reais(v) }, { k: 'Do total', v: pct(v / totCat) }] })),
    { cor: C[0], vazio: 'Nenhum gasto registrado com os filtros escolhidos.' });
  // partidos
  const ps = partidosComBancada(c).map((a) => ({ p: a.p, v: (cg.totalPart.get(a.p) || 0) / (cg.mesesPart.get(a.p) || 1), tot: cg.totalPart.get(a.p) || 0 })).filter((a) => a.tot > 0).sort((a, b) => b.v - a.v);
  barras(caixa('gPart'), ps.map((a) => ({ chave: a.p, rotulo: a.p, valor: a.v, texto: reaisC(a.v), tip: () => [{ h: a.p }, { k: 'Por deputado por mês', v: reais(a.v) }, { k: 'Total do partido', v: reais(a.tot) }] })),
    { cor: C[0], marcado: c.P.partido, aoClicar: alternarPartido, vazio: 'Nenhum partido com bancada média de um deputado nos filtros escolhidos.' });
  // fornecedores
  const porForn = new Map();
  for (const r of cg.forn) {
    const chave = r.doc && r.doc !== 'Pessoa física' ? r.doc : 'pf:' + r.forn.toUpperCase();
    let a = porForn.get(chave);
    if (!a) { a = { chave, forn: r.forn, doc: r.doc || '—', v: 0, n: 0, deps: new Set(), cats: new Map() }; porForn.set(chave, a); }
    a.v += r.v; a.n += r.n; a.deps.add(r.id); a.cats.set(r.cat, (a.cats.get(r.cat) || 0) + r.v);
  }
  const forn = [...porForn.values()].map((a) => Object.assign(a, { nd: a.deps.size, cat: [...a.cats].sort((x, y) => y[1] - x[1])[0][0] })).sort((a, b) => b.v - a.v).slice(0, 60);
  nota('gForn', (c.P.deputado ? 'Os maiores fornecedores do deputado' : 'Os 60 maiores fornecedores do recorte') + ', somando os dez maiores de cada deputado em cada ano. Pessoas físicas aparecem sem CPF.');
  tabela(caixa('gForn'), forn, [
    { k: 'forn', h: 'Fornecedor', l: 1, wrap: 1, f: (d) => d.forn || '—' },
    { k: 'doc', h: 'CNPJ', l: 1, f: (d) => d.doc },
    { k: 'cat', h: 'Tipo de despesa', l: 1, f: (d) => d.cat },
    { k: 'v', h: 'Valor', f: (d) => reais(d.v) },
    { k: 'nd', h: 'Deputados', f: (d) => num(d.nd) },
    { k: 'n', h: 'Documentos', f: (d) => num(d.n) },
  ], ui.sortForn, 'forn', null, 'forn');
}

/* ---------- emendas parlamentares ---------- */
const FONTES_EMENDAS = ['emendas', 'emendas_destinos', 'emendas_mes', 'emendas_favorecidos', 'emendas_tipos'];
const PIX = 'Transferência especial';
const TIPOS_EMENDA = [
  { k: 'Finalidade definida', nome: 'Individual com finalidade definida', cor: C[0] },
  { k: PIX, nome: 'Individual por transferência especial', cor: C[1] },
  { k: 'Bancada', nome: 'De bancada estadual', cor: C[2] },
  { k: 'Comissão', nome: 'De comissão', cor: C[3] },
  { k: 'Relator', nome: 'De relator', cor: C[4] },
];
const MODOS_EM = {
  valor: { maior: 'Mais emendas por ano', menor: 'Menos emendas por ano', rotulo: 'Por ano', v: (a) => a.porAno, f: (a) => reaisC(a.porAno),
    sub: (a) => reais(a.e) + ' empenhados em ' + qtd(a.anos.size, 'ano', 'anos'), nota: 'Valor empenhado em emendas individuais dividido pelo número de anos do Orçamento em que o deputado tem emendas.' },
  pix: { maior: 'Mais transferência especial', menor: 'Menos transferência especial', rotulo: 'Pix', v: (a) => a.ppix, f: (a) => pct(a.ppix, 0),
    sub: (a) => reaisC(a.pix) + ' de ' + reaisC(a.e), nota: 'Parcela do valor das emendas individuais enviada por transferência especial (emenda Pix), sem destinação específica.' },
  fora: { maior: 'Mais emendas fora do estado', menor: 'Menos emendas fora do estado', rotulo: 'Fora da UF', v: (a) => a.pfora, f: (a) => pct(a.pfora, 0),
    sub: (a) => reaisC(a.fora) + ' de ' + reaisC(a.comUf) + ' com UF de destino', nota: 'Parcela do valor com UF de destino informada que foi para outro estado que não o do deputado.' },
  exec: { maior: 'Maior execução', menor: 'Menor execução', rotulo: 'Pago', v: (a) => a.exec, f: (a) => pct(a.exec, 0),
    sub: (a) => reaisC(a.pg) + ' pagos de ' + reaisC(a.e), nota: 'Valor pago dividido pelo empenhado. Emendas do ano corrente ainda estão sendo pagas, então anos recentes puxam a execução para baixo.' },
};
let cache4 = { key: '', E: null };
function prepEmendas(em, de, me, fa, ti) {
  return {
    em: em.map((r) => ({ id: String(r.id_deputado), ano: String(r.ano), p: String(r.partido), tipo: String(r.tipo), area: String(r.area), uf: String(r.uf_destino || ''), n: +r.emendas || 0, e: +r.empenhado || 0, pg: +r.pago || 0 })),
    dest: de.map((r) => ({ id: String(r.id_deputado), ano: String(r.ano), dest: String(r.destino), uf: String(r.uf || ''), e: +r.empenhado || 0, pg: +r.pago || 0 })),
    mes: me.map((r) => ({ id: String(r.id_deputado), m: String(r.mes), p: String(r.partido), tipo: String(r.tipo), v: +r.valor || 0 })),
    fav: fa.map((r) => ({ id: String(r.id_deputado), ano: String(r.ano), fav: String(r.favorecido || ''), doc: String(r.documento || ''), nat: String(r.natureza || ''), uf: String(r.uf || ''), mun: String(r.municipio || ''), v: +r.valor || 0, n: +r.pagamentos || 0 })),
    tipos: ti.map((r) => ({ ano: String(r.ano), tipo: String(r.tipo), n: +r.emendas || 0, e: +r.empenhado || 0, pg: +r.pago || 0 })),
  };
}
function contextoEmendas(c, E) {
  const mset = new Set(c.meses), anos = [...new Set(c.meses.map((m) => m.slice(0, 4)))].sort();
  const aset = new Set(anos);
  const info = (id) => c.D.info.get(id) || {};
  const geo = (r) => !c.P.uf || info(r.id).uf === c.P.uf;
  const recorte = (r) => geo(r) && (!c.P.partido || r.p === c.P.partido) && (!c.P.deputado || r.id === c.P.deputado);
  const atual = (r) => geo(r) && (!c.P.deputado || r.id === c.P.deputado) && (!c.P.partido || info(r.id).p === c.P.partido);
  const doAno = E.em.filter((r) => aset.has(r.ano));
  const porDep = new Map();
  for (const r of doAno) {
    let a = porDep.get(r.id);
    if (!a) { a = { id: r.id, e: 0, pg: 0, n: 0, pix: 0, fora: 0, comUf: 0, anos: new Set() }; porDep.set(r.id, a); }
    a.e += r.e; a.pg += r.pg; a.n += r.n; a.anos.add(r.ano);
    if (r.tipo === PIX) a.pix += r.e;
    if (r.uf) { a.comUf += r.e; if (r.uf !== info(r.id).uf) a.fora += r.e; }
  }
  for (const a of porDep.values()) { a.ppix = a.e ? a.pix / a.e : null; a.pfora = a.comUf ? a.fora / a.comUf : null; a.exec = a.e ? a.pg / a.e : null; a.porAno = a.e / (a.anos.size || 1); }
  const porPart = new Map();
  for (const r of doAno) { if (!geo(r)) continue; let a = porPart.get(r.p); if (!a) { a = { p: r.p, e: 0, pix: 0 }; porPart.set(r.p, a); } a.e += r.e; if (r.tipo === PIX) a.pix += r.e; }
  const em = doAno.filter(recorte);
  return {
    E, anos, em, porDep, porPart,
    total: d3.sum(em, (r) => r.e), pago: d3.sum(em, (r) => r.pg), pix: d3.sum(em, (r) => (r.tipo === PIX ? r.e : 0)),
    mes: E.mes.filter((r) => mset.has(r.m) && recorte(r)),
    dest: E.dest.filter((r) => aset.has(r.ano) && atual(r)),
    fav: E.fav.filter((r) => aset.has(r.ano) && atual(r)),
    tipos: E.tipos.filter((r) => aset.has(r.ano)),
  };
}
function aguardandoEmendas(keys) {
  const st = FONTES_EMENDAS.map((id) => dash.data(id).status);
  const erro = st.some((x) => x === 'error');
  for (const k of keys) { const b = caixa(k); if (!b) continue; b.classList.remove('dash-skeleton'); b.replaceChildren(erro ? el('div', 'cp-err', 'As emendas não foram carregadas nesta atualização') : el('p', 'cp-card-n', 'Carregando emendas…')); }
}
function colunasAno(box, anos, series, fmt, fmtEixo, msgVazio) {
  // series: [{nome, cor, valores: [por ano]}], empilhadas
  box.replaceChildren();
  const tot = anos.map((a, i) => d3.sum(series, (s) => s.valores[i]));
  const max = d3.max(tot) || 0;
  if (!max) return vazio(box, msgVazio);
  const W = Math.max(260, Math.floor(box.clientWidth)), H = 250, mt = 12, mb = 26, mr = 8;
  const svg = d3.select(box).append('svg').attr('class', 'cp-svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img');
  const y = d3.scaleLinear([0, d3.nice(0, max, 4)[1]], [H - mb, mt]);
  const ticks = y.ticks(4);
  const rot = svg.append('g').selectAll('text').data(ticks).join('text').attr('y', (t) => y(t)).attr('dy', '0.32em').text((t) => fmtEixo(t));
  let ml = 0; rot.each(function (t) { ml = Math.max(ml, this.getComputedTextLength() || fmtEixo(t).length * 6.5); });
  ml = Math.ceil(ml) + 10; rot.attr('x', ml - 8).attr('text-anchor', 'end');
  svg.append('g').selectAll('line').data(ticks).join('line').attr('x1', ml).attr('x2', W - mr).attr('y1', (t) => y(t)).attr('y2', (t) => y(t)).attr('stroke', 'var(--ds-chart-grid)');
  const x = d3.scaleBand(anos, [ml, W - mr]).paddingInner(0.35).paddingOuter(0.2);
  const larg = Math.min(56, x.bandwidth());
  svg.append('g').selectAll('text').data(anos).join('text').attr('x', (a) => x(a) + x.bandwidth() / 2).attr('y', H - mb + 16).attr('text-anchor', 'middle').text((a) => a);
  const g = svg.append('g');
  anos.forEach((a, i) => {
    let base = 0; const cx = x(a) + x.bandwidth() / 2;
    series.forEach((s) => {
      const v = s.valores[i]; if (!v) return;
      const y0 = y(base), y1 = y(base + v), h = Math.max(1, y0 - y1 - (base > 0 ? 2 : 0));
      g.append('rect').attr('x', cx - larg / 2).attr('width', larg).attr('y', y0 - (base > 0 ? 2 : 0) - h).attr('height', h).attr('rx', 2).attr('fill', s.cor).attr('data-i', i);
      base += v;
    });
  });
  svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', H - mb).attr('y2', H - mb).attr('stroke', 'var(--ds-chart-axis)');
  svg.append('rect').attr('x', ml).attr('y', 0).attr('width', Math.max(0, W - ml - mr)).attr('height', H).attr('fill', 'transparent')
    .on('pointermove', (ev) => {
      const px = d3.pointer(ev, svg.node())[0];
      const i = d3.leastIndex(anos, (a, b) => Math.abs(x(a) + x.bandwidth() / 2 - px) - Math.abs(x(b) + x.bandwidth() / 2 - px));
      g.selectAll('rect').attr('opacity', function () { return +this.getAttribute('data-i') === i ? 1 : 0.5; });
      mostrarTip(box, ev, [{ h: 'Orçamento de ' + anos[i] }, ...series.filter((s) => s.valores[i]).map((s) => ({ c: s.cor, k: s.nome, v: fmt(s.valores[i]) })), ...(series.length > 1 ? [{ k: 'Total', v: fmt(tot[i]) }] : [])]);
    })
    .on('pointerleave', () => { g.selectAll('rect').attr('opacity', 1); esconderTip(box); });
}
function paginaEmendas(c) {
  const keys = ['emAno', 'emMes', 'emMais', 'emMenos', 'emArea', 'emPart', 'emDest', 'emFav'];
  for (const b of root.querySelectorAll('.cp-seg-b[data-modoem]')) b.setAttribute('aria-pressed', String(b.dataset.modoem === ui.modoEm));
  if (!c.ce) return aguardandoEmendas(keys);
  for (const k of keys) caixa(k).classList.remove('dash-skeleton');
  const ce = c.ce;
  const fmtPg = (e, pg) => reais(e) + ' empenhados · ' + reais(pg) + ' pagos';
  // por ano: Câmara inteira mostra todos os tipos (inclusive de senadores e coletivas); recorte mostra as individuais dele
  if (!c.filtrado) {
    const series = TIPOS_EMENDA.map((t) => ({ nome: t.nome, cor: t.cor, valores: ce.anos.map((a) => d3.sum(ce.tipos, (r) => (r.ano === a && r.tipo === t.k ? r.e : 0))) })).filter((s) => d3.sum(s.valores) > 0);
    nota('emAno', 'Valor empenhado em todas as emendas do Orçamento, por ano, inclusive as ⟦' + (SENADO ? 'de deputados' : 'de senadores') + '⟧ e as coletivas. Só as individuais têm um deputado como autor.');
    legenda('emAno', series.map((s) => ({ nome: s.nome, c: s.cor })));
    colunasAno(caixa('emAno'), ce.anos, series, reais, reaisC, 'Nenhuma emenda nos anos escolhidos.');
  } else {
    const series = TIPOS_EMENDA.slice(0, 2).map((t) => ({ nome: t.nome, cor: t.cor, valores: ce.anos.map((a) => d3.sum(ce.em, (r) => (r.ano === a && r.tipo === t.k ? r.e : 0))) }));
    nota('emAno', 'Valor empenhado nas emendas individuais de ' + (c.P.deputado ? rotuloRecorte(c) : 'deputados do recorte') + ', por ano do Orçamento.');
    legenda('emAno', series.map((s) => ({ nome: s.nome, c: s.cor })));
    colunasAno(caixa('emAno'), ce.anos, series, reais, reaisC, 'Nenhuma emenda individual com os filtros escolhidos.');
  }
  // pagamentos por mês
  const porMesE = d3.rollup(ce.mes, (rs) => d3.sum(rs, (r) => r.v), (r) => r.m);
  nota('emMes', 'Valor pago aos favorecidos das emendas individuais' + (c.filtrado ? ' do recorte' : ' de deputados') + ' em cada mês, qualquer que seja o ano da emenda.');
  colunasMensais(caixa('emMes'), c.meses, c.meses.map((m) => porMesE.get(m) || 0), C[0], 'Pago', reais, 'Nenhum pagamento com os filtros escolhidos.', reaisC);
  // rankings
  const modo = MODOS_EM[ui.modoEm] || MODOS_EM.valor;
  root.querySelector('[data-n="emMaisT"]').textContent = modo.maior;
  root.querySelector('[data-n="emMenosT"]').textContent = modo.menor;
  const sessoes = new Map(c.deps.map((d) => [d.id, d.sE]));
  const elegiveis = [...ce.porDep.values()].filter((a) => (sessoes.get(a.id) || 0) >= c.minSess && a.e > 0 && modo.v(a) != null)
    .map((a) => Object.assign({}, c.D.info.get(a.id) || { nome: a.id, p: '', uf: '' }, a));
  const crit = modo.nota + ' ' + criterio(c);
  nota('emMais', crit); nota('emMenos', crit);
  const maxV = d3.max(elegiveis, modo.v) || 1;
  const opE = { rotulo: modo.rotulo, valor: modo.f, sub: modo.sub, bar: (a) => (ui.modoEm === 'valor' ? modo.v(a) / maxV : modo.v(a)), vazio: 'Ninguém com emendas atende ao mínimo de sessões com os filtros escolhidos.' };
  ranking(caixa('emMais'), [...elegiveis].sort((a, b) => modo.v(b) - modo.v(a) || b.e - a.e).slice(0, 15), opE, c);
  ranking(caixa('emMenos'), [...elegiveis].sort((a, b) => modo.v(a) - modo.v(b) || b.e - a.e).slice(0, 15), opE, c);
  // áreas
  const porArea = d3.rollups(ce.em, (rs) => [d3.sum(rs, (r) => r.e), d3.sum(rs, (r) => r.pg)], (r) => r.area).filter((x) => x[1][0] > 0).sort((a, b) => b[1][0] - a[1][0]);
  const totA = d3.sum(porArea, (x) => x[1][0]) || 1;
  barras(caixa('emArea'), porArea.map(([k, [e, pg]]) => ({ chave: k, rotulo: k, valor: e, texto: reaisC(e) + ' · ' + pct(e / totA, 0), tip: () => [{ h: k }, { k: 'Empenhado', v: reais(e) }, { k: 'Pago', v: reais(pg) }, { k: 'Do total', v: pct(e / totA) }] })),
    { cor: C[0], vazio: 'Nenhuma emenda individual com os filtros escolhidos.' });
  // partidos
  const bancada = new Set(partidosComBancada(c).map((a) => a.p));
  const ps = [...ce.porPart.values()].filter((a) => bancada.has(a.p) && a.e > 0).map((a) => Object.assign(a, { ppix: a.pix / a.e })).sort((a, b) => b.ppix - a.ppix);
  barras(caixa('emPart'), ps.map((a) => ({ chave: a.p, rotulo: a.p, valor: a.ppix, texto: pct(a.ppix, 0), tip: () => [{ h: a.p }, { k: 'Transferência especial', v: reais(a.pix) }, { k: 'Total individual', v: reais(a.e) }, { k: 'Parcela', v: pct(a.ppix) }] })),
    { cor: C[1], max: 1, marcado: c.P.partido, aoClicar: alternarPartido, vazio: 'Nenhuma emenda individual com os filtros escolhidos.' });
  // destinos
  const porDest = new Map();
  for (const r of ce.dest) { let a = porDest.get(r.dest); if (!a) { a = { chave: r.dest, dest: r.dest, uf: r.uf || '—', e: 0, pg: 0, deps: new Set() }; porDest.set(r.dest, a); } a.e += r.e; a.pg += r.pg; a.deps.add(r.id); }
  const dest = [...porDest.values()].map((a) => Object.assign(a, { nd: a.deps.size, exec: a.e ? a.pg / a.e : null })).sort((a, b) => b.e - a.e).slice(0, 60);
  nota('emDest', (c.P.deputado ? 'Os principais destinos das emendas do deputado' : 'Os 60 principais destinos do recorte') + ', somando os dez maiores de cada deputado em cada ano. “Vários municípios” reúne emendas distribuídas entre municípios do estado; “(estado)” indica o governo estadual. ' + fmtPg(ce.total, ce.pago) + ' no total do recorte.');
  tabela(caixa('emDest'), dest, [
    { k: 'dest', h: 'Destino', l: 1, wrap: 1, f: (d) => d.dest },
    { k: 'e', h: 'Empenhado', f: (d) => reais(d.e) },
    { k: 'pg', h: 'Pago', f: (d) => reais(d.pg) },
    { k: 'exec', h: 'Execução', f: (d) => pct(d.exec, 0) },
    { k: 'nd', h: 'Deputados', f: (d) => num(d.nd) },
  ], ui.sortDest, 'forn', null, 'dest');
  // favorecidos
  const porFav = new Map();
  for (const r of ce.fav) {
    const chave = r.doc === 'Pessoa física' ? 'pf' : (r.doc || r.fav.toUpperCase());
    let a = porFav.get(chave);
    if (!a) { a = { chave, fav: r.fav, doc: r.doc && r.doc !== 'Pessoa física' ? r.doc : '—', nat: r.nat || '—', local: r.mun ? r.mun + (r.uf ? ' - ' + r.uf : '') : (r.uf || '—'), v: 0, n: 0, deps: new Set() }; porFav.set(chave, a); }
    a.v += r.v; a.n += r.n; a.deps.add(r.id);
  }
  const fav = [...porFav.values()].map((a) => Object.assign(a, { nd: a.deps.size })).sort((a, b) => b.v - a.v).slice(0, 60);
  nota('emFav', (c.P.deputado ? 'Quem mais recebeu pelas emendas do deputado' : 'Os 60 que mais receberam no recorte') + ', em pagamentos feitos nos anos escolhidos e somando os dez maiores favorecidos de cada deputado por ano. Caixa e Banco do Brasil aparecem como intermediários de contratos de repasse. Pessoas físicas aparecem agrupadas, sem nome.');
  tabela(caixa('emFav'), fav, [
    { k: 'fav', h: 'Favorecido', l: 1, wrap: 1, f: (d) => d.fav || '—' },
    { k: 'doc', h: 'CNPJ', l: 1, f: (d) => d.doc },
    { k: 'nat', h: 'Natureza', l: 1, wrap: 1, f: (d) => d.nat },
    { k: 'local', h: 'Local', l: 1, f: (d) => d.local },
    { k: 'v', h: 'Recebido', f: (d) => reais(d.v) },
    { k: 'nd', h: 'Deputados', f: (d) => num(d.nd) },
  ], ui.sortFav, 'forn', null, 'fav');
}

/* ---------- nota de trabalho ---------- */
let cacheTrab = { c: null, pesos: '', r: null };
function notasTrabalho(c) {
  const pk = JSON.stringify(ui.pesos);
  if (cacheTrab.c === c && cacheTrab.pesos === pk) return cacheTrab.r;
  const elig = c.baseDeps.filter((d) => d.sE >= c.minSess), n = elig.length;
  const somaPesos = d3.sum(FATORES, (f) => ui.pesos[f.k] || 0);
  const notas = new Map(elig.map((d) => [d.id, { d, comp: {}, nota: null }]));
  if (n) for (const f of FATORES) {
    const vals = elig.map(f.v).sort(d3.ascending);
    for (const d of elig) {
      const x = f.v(d), lo = d3.bisectLeft(vals, x), hi = d3.bisectRight(vals, x);
      const r = n > 1 ? (lo + (hi - lo - 1) / 2) / (n - 1) : 0.5;
      notas.get(d.id).comp[f.k] = f.bom > 0 ? r : 1 - r;
    }
  }
  if (somaPesos > 0) for (const o of notas.values()) o.nota = 100 * d3.sum(FATORES, (f) => (ui.pesos[f.k] || 0) * o.comp[f.k]) / somaPesos;
  cacheTrab = { c, pesos: pk, r: { notas, n, somaPesos } };
  return cacheTrab.r;
}
const fmtNota = (x) => (x == null ? '—' : dec(x, 1));

/* ---------- tooltip ---------- */
function tipDe(box) { let t = box.querySelector(':scope > .cp-tip'); if (!t) { t = el('div', 'cp-tip'); t.hidden = true; box.append(t); } return t; }
function mostrarTip(box, ev, linhas) {
  const t = tipDe(box); t.replaceChildren();
  for (const l of linhas) {
    if (l.h != null) { t.append(el('div', 'cp-tip-h', l.h)); continue; }
    const r = el('div', 'cp-tip-r');
    if (l.c) { const k = el('span', 'cp-sw' + (l.line ? ' cp-sw-line' : '')); k.style.background = l.c; r.append(k); }
    r.append(el('span', 'cp-tip-k', l.k), el('span', 'cp-tip-v', l.v)); t.append(r);
  }
  t.hidden = false;
  const b = box.getBoundingClientRect();
  let x = ev.clientX - b.left + 14, y = ev.clientY - b.top + 14;
  if (x + t.offsetWidth > b.width - 4) x = Math.max(4, ev.clientX - b.left - t.offsetWidth - 14);
  if (y + t.offsetHeight > b.height - 4) y = Math.max(4, ev.clientY - b.top - t.offsetHeight - 14);
  t.style.left = x + 'px'; t.style.top = y + 'px';
}
function esconderTip(box) { const t = box.querySelector(':scope > .cp-tip'); if (t) t.hidden = true; }
function comTip(alvo, box, linhas) {
  alvo.addEventListener('pointermove', (ev) => mostrarTip(box, ev, linhas()));
  alvo.addEventListener('pointerleave', () => esconderTip(box));
  alvo.addEventListener('focus', () => { const r = alvo.getBoundingClientRect(); mostrarTip(box, { clientX: r.left + r.width / 2, clientY: r.bottom - 6 }, linhas()); });
  alvo.addEventListener('blur', () => esconderTip(box));
}

/* ---------- gráficos ---------- */
function vazio(box, msg) { box.replaceChildren(el('p', 'cp-card-n', msg || 'Sem dados para os filtros escolhidos.')); }
function moldura(box, meses, dominio, fmtY, emBandas, folgaDireita) {
  box.replaceChildren();
  const W = Math.max(260, Math.floor(box.clientWidth)), H = 250, mt = 12, mb = 26;
  const svg = d3.select(box).append('svg').attr('class', 'cp-svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img');
  const y = d3.scaleLinear(dominio, [H - mb, mt]);
  const ticks = y.ticks(4);
  const eixo = svg.append('g');
  const rot = eixo.selectAll('text').data(ticks).join('text').attr('y', (t) => y(t)).attr('dy', '0.32em').text((t) => fmtY(t));
  let ml = 0; rot.each(function (t) { ml = Math.max(ml, this.getComputedTextLength() || fmtY(t).length * 6.5); });
  ml = Math.ceil(ml) + 10; rot.attr('x', ml - 8).attr('text-anchor', 'end');
  const mr = folgaDireita;
  eixo.selectAll('line').data(ticks).join('line').attr('x1', ml).attr('x2', W - mr).attr('y1', (t) => y(t)).attr('y2', (t) => y(t)).attr('stroke', 'var(--ds-chart-grid)');
  svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', H - mb).attr('y2', H - mb).attr('stroke', 'var(--ds-chart-axis)');
  const x = emBandas ? d3.scaleBand(meses, [ml, W - mr]).paddingInner(0.3).paddingOuter(0.2) : d3.scalePoint(meses, [ml, W - mr]).padding(0.5);
  const cx = (m) => x(m) + (emBandas ? x.bandwidth() / 2 : 0);
  // rótulos do eixo x: meses quando o recorte é curto, anos quando é longo
  const curto = meses.length <= 14;
  const cand = meses.map((m, i) => ({ m, i, jan: m.slice(5, 7) === '01' })).filter((d) => curto || d.jan || d.i === 0)
    .map((d) => Object.assign(d, { t: curto ? (d.i === 0 || d.jan ? mesNome(d.m) : MES[+d.m.slice(5, 7) - 1]) : (d.jan ? d.m.slice(0, 4) : mesNome(d.m)) }));
  const gx = svg.append('g');
  const postos = [];
  const ordem = curto ? cand : cand.filter((d) => d.jan).concat(cand.filter((d) => !d.jan));
  for (const d of ordem) {
    const t = gx.append('text').attr('x', cx(d.m)).attr('y', H - mb + 16).attr('text-anchor', 'middle').text(d.t);
    const w = (t.node().getComputedTextLength() || d.t.length * 6.5) / 2 + 5;
    const a = cx(d.m) - w, b = cx(d.m) + w;
    if (a < 0 || b > W || postos.some((p) => a < p[1] && b > p[0])) t.remove(); else postos.push([a, b]);
  }
  return { svg, x, cx, y, W, H, ml, mr, mt, mb };
}
function mesMaisProximo(f, meses, px) { return d3.leastIndex(meses, (a, b) => Math.abs(f.cx(a) - px) - Math.abs(f.cx(b) - px)); }
function linhaMensal(box, meses, series, extra) {
  // series: [{nome, cor, valores: [fração | null]}], a primeira é a principal
  const vals = series.flatMap((s) => s.valores).filter((v) => v != null);
  if (!vals.length) return vazio(box, 'Não houve sessão deliberativa com os filtros escolhidos.');
  const piso = Math.max(0, Math.min(0.8, Math.floor((d3.min(vals) - 0.02) * 10) / 10));
  const f = moldura(box, meses, [piso, 1], (t) => pct(t, 0), false, 50);
  const linha = d3.line().defined((d) => d.v != null).x((d) => f.cx(d.m)).y((d) => f.y(d.v));
  const fins = [];
  [...series].reverse().forEach((s) => {
    const pts = meses.map((m, i) => ({ m, v: s.valores[i] }));
    f.svg.append('path').attr('d', linha(pts)).attr('fill', 'none').attr('stroke', s.cor).attr('stroke-width', 2).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round');
    const def = pts.filter((d) => d.v != null);
    if (s === series[0]) f.svg.append('g').selectAll('circle').data(def).join('circle').attr('cx', (d) => f.cx(d.m)).attr('cy', (d) => f.y(d.v)).attr('r', 2.5).attr('fill', s.cor).attr('stroke', 'var(--color-panel)').attr('stroke-width', 1);
    if (def.length) fins.push({ s, d: def[def.length - 1] });
  });
  const princ = fins.find((e) => e.s === series[0]);
  for (const e of fins) {
    if (e !== princ && princ && Math.abs(f.y(e.d.v) - f.y(princ.d.v)) < 13) continue;
    f.svg.append('text').attr('class', 'cp-end').attr('x', Math.min(f.cx(e.d.m) + 8, f.W - 40)).attr('y', f.y(e.d.v)).attr('dy', '0.32em').text(pct(e.d.v, 0));
  }
  const guia = f.svg.append('line').attr('y1', f.mt).attr('y2', f.H - f.mb).attr('stroke', 'var(--ds-chart-reference)').attr('display', 'none');
  f.svg.append('rect').attr('x', f.ml).attr('y', 0).attr('width', Math.max(0, f.W - f.ml - f.mr)).attr('height', f.H).attr('fill', 'transparent')
    .on('pointermove', (ev) => {
      const i = mesMaisProximo(f, meses, d3.pointer(ev, f.svg.node())[0]);
      guia.attr('display', null).attr('x1', f.cx(meses[i])).attr('x2', f.cx(meses[i]));
      mostrarTip(box, ev, [{ h: mesNome(meses[i]) }, ...series.map((s) => ({ c: s.cor, line: true, k: s.nome, v: pct(s.valores[i]) })), ...extra(i)]);
    })
    .on('pointerleave', () => { guia.attr('display', 'none'); esconderTip(box); });
}
function colunasMensais(box, meses, valores, cor, rotulo, fmt = num, msgVazio = 'Nenhum projeto apresentado com os filtros escolhidos.', fmtEixo = fmt) {
  const max = d3.max(valores) || 0;
  if (!max) return vazio(box, msgVazio);
  const f = moldura(box, meses, [0, d3.nice(0, max, 4)[1]], (t) => fmtEixo(t), true, 8);
  const larg = Math.min(32, f.x.bandwidth());
  const barras = f.svg.append('g').selectAll('rect').data(meses).join('rect')
    .attr('x', (m) => f.cx(m) - larg / 2).attr('width', larg).attr('y', (m, i) => f.y(valores[i])).attr('height', (m, i) => Math.max(0, f.y(0) - f.y(valores[i])))
    .attr('rx', Math.min(4, larg / 2)).attr('fill', cor);
  f.svg.append('rect').attr('x', f.ml).attr('y', 0).attr('width', Math.max(0, f.W - f.ml - f.mr)).attr('height', f.H).attr('fill', 'transparent')
    .on('pointermove', (ev) => {
      const i = mesMaisProximo(f, meses, d3.pointer(ev, f.svg.node())[0]);
      barras.attr('opacity', (m, j) => (j === i ? 1 : 0.55));
      mostrarTip(box, ev, [{ h: mesNome(meses[i]) }, { k: rotulo, v: fmt(valores[i]) }]);
    })
    .on('pointerleave', () => { barras.attr('opacity', 1); esconderTip(box); });
}
function histograma(box, c) {
  const todos = c.baseDeps.filter((d) => d.sE >= c.minSess);
  if (!todos.length) return vazio(box, 'Ninguém atende ao mínimo de sessões com os filtros escolhidos.');
  const recorte = !!(c.P.partido || c.P.uf);
  const nomeRecorte = c.P.partido && c.P.uf ? c.P.partido + ' em ' + c.P.uf : (c.P.partido || c.P.uf);
  const foco = new Set(c.deps.filter((d) => d.sE >= c.minSess).map((d) => d.id));
  const minTaxa = d3.min(todos, (d) => d.pres) * 100;
  const w = 100 - minTaxa <= 25 ? 1 : 100 - minTaxa <= 60 ? 2 : 5;
  const lo = Math.max(0, Math.floor(minTaxa / w) * w), nb = Math.max(1, Math.ceil((100 - lo) / w)), hi = lo + nb * w;
  const bins = d3.range(nb).map((i) => ({ a: lo + i * w, b: lo + (i + 1) * w, foco: 0, resto: 0, nomes: [] }));
  for (const d of todos) {
    const b = bins[Math.max(0, Math.min(nb - 1, Math.floor((d.pres * 100 + 1e-9 - lo) / w)))];
    if (foco.has(d.id)) { b.foco++; b.nomes.push(d); } else b.resto++;
  }
  const taxasFoco = todos.filter((d) => foco.has(d.id)).map((d) => d.pres);
  const nFoco = taxasFoco.length;
  box.replaceChildren();
  const W = Math.max(260, Math.floor(box.clientWidth)), H = 250, mt = 26, mb = 26, mr = 8;
  const svg = d3.select(box).append('svg').attr('class', 'cp-svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img')
    .attr('aria-label', 'Distribuição das taxas de presença de ' + todos.length + ' deputados');
  const maxN = d3.max(bins, (b) => b.foco + b.resto) || 1;
  const y = d3.scaleLinear([0, d3.nice(0, maxN, 4)[1]], [H - mb, mt]);
  const yt = y.ticks(4).filter(Number.isInteger);
  const g = svg.append('g');
  const rot = g.selectAll('text').data(yt).join('text').attr('y', (t) => y(t)).attr('dy', '0.32em').text((t) => num(t));
  let ml = 0; rot.each(function (t) { ml = Math.max(ml, this.getComputedTextLength() || String(t).length * 7); });
  ml = Math.ceil(ml) + 10; rot.attr('x', ml - 8).attr('text-anchor', 'end');
  g.selectAll('line').data(yt).join('line').attr('x1', ml).attr('x2', W - mr).attr('y1', (t) => y(t)).attr('y2', (t) => y(t)).attr('stroke', 'var(--ds-chart-grid)');
  svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', H - mb).attr('y2', H - mb).attr('stroke', 'var(--ds-chart-axis)');
  const x = d3.scaleLinear([lo, hi], [ml, W - mr]);
  const xt = d3.ticks(lo, hi, Math.max(3, Math.min(8, Math.floor((W - ml) / 70))));
  svg.append('g').selectAll('text').data(xt).join('text').attr('x', (t) => x(t)).attr('y', H - mb + 16).attr('text-anchor', 'middle').text((t) => dec(t, 0) + '%');
  const bw = (b) => Math.max(1, x(b.b) - x(b.a) - 2);
  const gb = svg.append('g');
  const grupos = gb.selectAll('g').data(bins).join('g');
  grupos.append('rect').attr('x', (b) => x(b.a) + 1).attr('width', bw).attr('y', (b) => Math.min(y(b.foco), y(0) - (b.foco ? 2 : 0))).attr('height', (b) => (b.foco ? Math.max(2, y(0) - y(b.foco)) : 0)).attr('rx', (b) => Math.min(2, bw(b) / 2)).attr('fill', C[0]);
  grupos.filter((b) => b.resto > 0).append('rect').attr('x', (b) => x(b.a) + 1).attr('width', bw)
    .attr('y', (b) => Math.min(y(b.foco + b.resto), y(b.foco) - (b.foco ? 4 : 2))).attr('height', (b) => Math.max(2, y(b.foco) - y(b.foco + b.resto) - (b.foco ? 2 : 0))).attr('rx', (b) => Math.min(2, bw(b) / 2)).attr('fill', MUTED);
  // mediana do recorte e deputado escolhido
  const marcas = [];
  if (nFoco) marcas.push({ v: d3.median(taxasFoco), t: 'mediana ' + pct(d3.median(taxasFoco)), tracejado: true });
  if (c.dep && c.dep.sE >= c.minSess) marcas.push({ v: c.dep.pres, t: c.dep.nome + ' ' + pct(c.dep.pres) });
  marcas.forEach((m, i) => {
    const px = x(Math.min(hi, Math.max(lo, m.v * 100)));
    svg.append('line').attr('x1', px).attr('x2', px).attr('y1', mt - 6).attr('y2', H - mb).attr('stroke', m.tracejado ? 'var(--ds-chart-reference)' : 'var(--color-fg)').attr('stroke-width', m.tracejado ? 1 : 1.5).attr('stroke-dasharray', m.tracejado ? '4 3' : null);
    const lab = svg.append('text').attr('class', m.tracejado ? null : 'cp-end').attr('y', mt - 10 - (i && Math.abs(px - x(Math.min(hi, Math.max(lo, marcas[0].v * 100)))) < 140 ? 0 : 0) - (i ? 0 : 0)).text(m.t);
    const lw = lab.node().getComputedTextLength() || m.t.length * 6.5;
    const esquerda = px + 6 + lw > W - mr;
    lab.attr('x', esquerda ? px - 6 : px + 6).attr('text-anchor', esquerda ? 'end' : 'start');
    m.box = [esquerda ? px - 6 - lw : px + 6, esquerda ? px - 6 : px + 6 + lw]; m.lab = lab;
  });
  if (marcas.length === 2 && marcas[0].box[0] < marcas[1].box[1] && marcas[1].box[0] < marcas[0].box[1]) marcas[0].lab.attr('y', mt + 8);
  const hit = svg.append('g').selectAll('rect').data(bins).join('rect').attr('x', (b) => x(b.a)).attr('width', (b) => x(b.b) - x(b.a)).attr('y', mt).attr('height', H - mb - mt).attr('fill', 'transparent');
  hit.on('pointermove', (ev, b) => {
    grupos.attr('opacity', (o) => (o === b ? 1 : 0.55));
    const fx = b.b >= 100 ? dec(b.a, 0) + '% a 100%' : dec(b.a, 0) + '% a ' + dec(b.b, 0) + '%';
    const linhas = [{ h: 'Presença de ' + fx }];
    if (recorte) { linhas.push({ c: C[0], k: nomeRecorte, v: qtd(b.foco, 'deputado', 'deputados') }); linhas.push({ c: MUTED, k: 'Demais deputados', v: num(b.resto) }); }
    else linhas.push({ k: 'Deputados', v: num(b.foco) + ' (' + pct(b.foco / todos.length) + ')' });
    if (b.foco > 0 && b.foco <= 4) for (const d of b.nomes) linhas.push({ k: d.nome + ' ' + d.p + '-' + d.uf, v: pct(d.pres) });
    mostrarTip(box, ev, linhas);
  }).on('pointerleave', () => { grupos.attr('opacity', 1); esconderTip(box); });
  return { todos: todos.length, nFoco, w };
}
function barras(box, itens, o) {
  // itens: [{chave, rotulo, valor, texto, tip(), segs?: [{v, cor, nome}]}]
  box.replaceChildren();
  if (!itens.length) return vazio(box, o.vazio);
  const max = o.max || d3.max(itens, (d) => d.valor) || 1;
  box.style.setProperty('--cp-lab', Math.min(13, d3.max(itens, (d) => d.rotulo.length) * 0.6 + 0.6) + 'em');
  box.style.setProperty('--cp-val', (d3.max(itens, (d) => d.texto.length) * 0.56 + 0.5) + 'em');
  for (const d of itens) {
    const b = el(o.aoClicar ? 'button' : 'div', 'cp-hb' + (o.aoClicar ? ' cp-hb-btn' : ''));
    if (o.aoClicar) { b.type = 'button'; b.setAttribute('aria-pressed', String(o.marcado === d.chave)); b.addEventListener('click', () => o.aoClicar(d.chave)); }
    const trilho = el('span', 'cp-hb-t');
    if (d.segs) {
      const soma = d3.sum(d.segs, (s) => s.v) || 1;
      for (const s of d.segs) {
        if (s.v <= 0) continue;
        const seg = el('i', 'cp-hb-s'); seg.style.flexGrow = String(s.v); seg.style.background = s.cor;
        comTip(seg, box, () => [{ h: d.rotulo }, { c: s.cor, k: s.nome, v: pct(s.v / soma) + ' · ' + num(s.v) }]);
        trilho.append(seg);
      }
    } else {
      const fill = el('i', 'cp-hb-f'); fill.style.width = Math.max(0, d.valor / max * 100) + '%';
      fill.style.background = o.marcado && o.marcado !== d.chave ? MUTED : o.cor; trilho.append(fill);
      comTip(b, box, d.tip);
    }
    b.append(el('span', 'cp-hb-l', d.rotulo), trilho, el('span', 'cp-hb-v', d.texto));
    box.append(b);
  }
}

/* ---------- tabelas ---------- */
function celulaBarra(td, fracao, cor) { const ib = el('span', 'cp-ib'), f = el('i', 'cp-ib-f'); f.style.width = Math.max(0, Math.min(1, fracao || 0)) * 100 + '%'; f.style.background = cor || C[0]; ib.append(f); td.append(ib); }
function ranking(box, lista, o, c) {
  // o: {rotulo, valor(d), sub(d), bar(d)?, vazio?}
  box.replaceChildren();
  if (!lista.length) return vazio(box, o.vazio || 'Ninguém atende ao mínimo de sessões com os filtros escolhidos.');
  const cab = el('div', 'cp-rk-h'); cab.append(el('span', null, 'Deputado'), el('span', null, o.rotulo)); box.append(cab);
  lista.forEach((d, i) => {
    const r = el('div', 'cp-rk'); r.dataset.dep = d.id; r.tabIndex = 0; r.setAttribute('role', 'button');
    r.setAttribute('aria-pressed', String(c.P.deputado === d.id));
    const meio = el('div', 'cp-rk-m'); meio.append(el('div', null, d.nome), el('div', 'cp-sub', d.p + '-' + d.uf + ' · ' + o.sub(d)));
    const dir = el('div', 'cp-rk-v'); if (o.bar) celulaBarra(dir, o.bar(d)); dir.append(el('span', 'cp-rk-x', o.valor(d)));
    r.append(el('span', 'cp-sub', String(i + 1)), meio, dir); box.append(r);
  });
}
function ordenar(lista, cols, sort) {
  const col = cols.find((x) => x.k === sort.k) || cols[0];
  const val = (d) => (col.s ? col.s(d) : d[col.k]);
  return [...lista].sort((a, b) => {
    const x = val(a), y = val(b);
    if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
    return (typeof x === 'string' ? x.localeCompare(y, 'pt') : x - y) * sort.dir;
  });
}
function tabela(box, lista, cols, sort, attr, marcado, qual) {
  const rolagem = box.querySelector('.cp-tablebox'); const topo = rolagem ? rolagem.scrollTop : 0;
  box.replaceChildren();
  if (!lista.length) return vazio(box);
  const t = el('table', 'cp-table'), th = el('tr');
  for (const col of cols) {
    const h = el('th', col.l ? 'cp-l' : null), b = el('button', 'cp-th-b', col.h);
    b.type = 'button'; b.dataset.sort = col.k; b.dataset.qual = qual;
    if (sort.k === col.k) { b.dataset.dir = String(sort.dir); h.setAttribute('aria-sort', sort.dir > 0 ? 'ascending' : 'descending'); }
    h.append(b); th.append(h);
  }
  const tb = el('tbody');
  for (const d of ordenar(lista, cols, sort)) {
    const tr = el('tr'); tr.dataset[attr] = d[attr === 'dep' ? 'id' : attr === 'prop' || attr === 'forn' ? 'chave' : attr === 'vot' ? 'id' : 'p']; tr.tabIndex = 0;
    if (marcado === tr.dataset[attr]) tr.setAttribute('aria-selected', 'true');
    for (const col of cols) {
      const td = el('td', col.l ? 'cp-l' + (col.k === 'nome' ? ' cp-name' : '') + (col.wrap ? ' cp-wrap' : '') : null);
      if (col.bar) celulaBarra(td, col.bar(d));
      const href = col.link ? col.link(d) : null;
      if (href) { const a = el('a', null, col.f(d)); a.href = href; a.target = '_blank'; a.rel = 'noopener'; td.append(a); } else td.append(document.createTextNode(col.f(d)));
      tr.append(td);
    }
    tb.append(tr);
  }
  const head = el('thead'); head.append(th); t.append(head, tb);
  const wrap = el('div', 'cp-tablebox'); wrap.append(t); box.append(wrap); wrap.scrollTop = topo;
}
const COLS_DEP = [
  { k: 'nome', h: 'Deputado', l: 1, f: (d) => d.nome },
  { k: 'p', h: 'Partido', l: 1, f: (d) => d.p },
  { k: 'uf', h: 'UF', l: 1, f: (d) => d.uf },
  { k: 'sE', h: 'Sessões', f: (d) => num(d.sE) },
  { k: 'aus', h: 'Ausências', f: (d) => num(d.aus) },
  { k: 'pres', h: 'Presença', f: (d) => pct(d.pres), bar: (d) => d.pres },
  { k: 'pctl', h: 'Percentil', f: (d) => fmtPctl(d.pctl) },
  { k: 'nota', h: 'Nota de trabalho', f: (d) => fmtNota(d.nota) },
  { k: 'fid', h: 'Com a bancada', f: (d) => pct(d.fid) },
  { k: 'gov', h: 'Com o governo', f: (d) => pct(d.gov) },
  { k: 'cota', h: 'Cota por mês', f: (d) => reais(d.cota) },
  { k: 'emen', h: 'Emendas por ano', f: (d) => reais(d.emen) },
  { k: 'pix', h: 'Emenda Pix', f: (d) => pct(d.pix, 0) },
  { k: 'vE', h: 'Votações', f: (d) => num(d.vE) },
  { k: 'pvot', h: 'Votou em', f: (d) => pct(d.pvot) },
  { k: 'vA', h: 'Abstenções', f: (d) => num(d.vA) },
  { k: 'vO', h: 'Obstruções', f: (d) => num(d.vO) },
  { k: 'pA', h: 'Projetos', f: (d) => num(d.pA) },
  { k: 'pC', h: 'Coautorias', f: (d) => num(d.pC) },
  ...(SENADO ? [{ k: 'ncom', h: 'Faltas sem justificativa', f: (d) => num(d.ncom) }, { k: 'cV', h: 'Votos em comissões', f: (d) => num(d.cV) }] : [{ k: 'oE', h: 'Reuniões de comissão', f: (d) => num(d.oE) }]),
];
const COLS_PART = [
  { k: 'p', h: 'Partido', l: 1, f: (d) => d.p },
  { k: 'banc', h: 'Bancada média', f: (d) => dec(d.banc) },
  { k: 'aus', h: 'Ausências', f: (d) => num(d.aus) },
  { k: 'taus', h: 'Taxa de ausência', f: (d) => pct(d.taus), bar: (d) => d.taus },
  { k: 'pres', h: 'Presença', f: (d) => pct(d.pres) },
  { k: 'pvot', h: 'Votou em', f: (d) => pct(d.pvot) },
  { k: 'coesao', h: 'Coesão', f: (d) => pct(d.coesao) },
  { k: 'gov', h: 'Com o governo', f: (d) => pct(d.gov) },
  { k: 'vA', h: 'Abstenções', f: (d) => num(d.vA) },
  { k: 'vO', h: 'Obstruções', f: (d) => num(d.vO) },
  { k: 'pA', h: 'Projetos', f: (d) => num(d.pA) },
  { k: 'cota', h: 'Cota por deputado/mês', f: (d) => reais(d.cota) },
  { k: 'pix', h: 'Emenda Pix', f: (d) => pct(d.pix, 0) },
  { k: 'ppd', h: 'Projetos por deputado', f: (d) => dec(d.ppd) },
];

/* ---------- cabeçalho, filtros e números ---------- */
function desenharFiltros(c) {
  const chips = $('.cp-chips');
  const quer = ['', ...c.D.anos];
  if (chips.children.length !== quer.length) chips.replaceChildren(...quer.map((a) => { const b = el('button', 'cp-chip', a || 'Tudo'); b.type = 'button'; b.dataset.ano = a; return b; }));
  for (const b of chips.children) b.setAttribute('aria-pressed', String(b.dataset.ano === '' ? c.anos.length === 0 : c.anos.includes(b.dataset.ano)));
  const sp = $('.cp-f-partido'), su = $('.cp-f-uf');
  if (sp.options.length !== c.D.partidos.length + 1) sp.replaceChildren(new Option('Todos', ''), ...c.D.partidos.map((p) => new Option(p, p)));
  if (su.options.length !== c.D.ufs.length + 1) su.replaceChildren(new Option('Todos', ''), ...c.D.ufs.map((u) => new Option(u, u)));
  sp.value = c.P.partido || ''; su.value = c.P.uf || '';
  const sm = $('.cp-f-min'); sm.value = String(c.P.minimo); if (sm.value !== String(c.P.minimo)) sm.value = '25';
  const pk = $('.cp-picked'); pk.hidden = !c.P.deputado;
  pk.textContent = c.P.deputado ? rotuloRecorte(c) + ' ×' : '';
  if (c.P.deputado) pk.setAttribute('aria-label', 'Remover seleção de ' + rotuloRecorte(c));
}
function desenharResumo(c) {
  const p = $('.cp-takeaway'); const t = c.tot;
  const periodo = c.de === c.ate ? 'Em ' + mesNome(c.de) : 'De ' + mesNome(c.de) + ' a ' + mesNome(c.ate);
  if (c.P.deputado) {
    if (!c.dep) { p.textContent = tx(rotuloRecorte(c) + ' não esteve em exercício no período escolhido.'); return; }
    const d = c.dep;
    p.textContent = tx(periodo + ', ⟦' + d.nome + '⟧ (' + d.p + '-' + d.uf + ') registrou presença em ' + num(d.sP) + ' de ' + qtd(d.sE, 'sessão deliberativa ocorrida', 'sessões deliberativas ocorridas') + ' durante o exercício do mandato (' + pct(d.pres) + (d.pctl != null ? '; percentil ' + fmtPctl(d.pctl) + ' da Câmara' : '') + '), votou em ' + pct(d.pvot) + ' das votações nominais e apresentou ' + qtd(d.pA, 'projeto', 'projetos') + ' como primeiro autor. ' + (c.cg && c.cg.totalDep.get(d.id) ? 'A cota parlamentar reembolsou ' + reais(c.cg.totalDep.get(d.id)) + ' em despesas do gabinete (' + reais(c.cg.mensal.get(d.id)) + ' por mês de mandato). ' : '') + (c.ce && c.ce.total ? 'Nas emendas individuais ao Orçamento, foram ' + reais(c.ce.total) + ' empenhados e ' + reais(c.ce.pago) + ' pagos, ' + pct(c.ce.pix / c.ce.total, 0) + ' por transferência especial. ' : ''));
    const a = el('a', 'cp-link', 'Perfil na Câmara'); a.href = SENADO ? 'https://www25.senado.leg.br/web/senadores/senador/-/perfil/' + encodeURIComponent(d.id) : 'https://www.camara.leg.br/deputados/' + encodeURIComponent(d.id); a.target = '_blank'; a.rel = 'noopener';
    p.append(a); return;
  }
  if (!t.sE) { p.textContent = tx('Não houve sessão deliberativa com os filtros escolhidos.'); return; }
  const quem = c.P.partido && c.P.uf ? 'os deputados do ' + c.P.partido + ' em ' + c.P.uf : c.P.partido ? 'os deputados do ' + c.P.partido : c.P.uf ? 'os deputados de ' + c.P.uf : 'os deputados';
  let s = periodo + ', ' + quem + ' registraram presença em ' + pct(t.pres) + ' das vezes em que eram esperados nas ' + num(c.nSess) + ' sessões deliberativas do Plenário. ';
  const ps = partidosComBancada(c).sort((a, b) => b.taus - a.taus);
  if (!c.P.partido && ps.length > 1) s += ps[0].p + ' teve a maior taxa de ausência entre os partidos (' + pct(ps[0].taus) + ') e ' + ps[ps.length - 1].p + ', a menor (' + pct(ps[ps.length - 1].taus) + ').';
  else { const top = c.deps.filter((d) => d.sE >= c.minSess).sort((a, b) => b.aus - a.aus)[0]; if (top && top.aus > 0) s += 'Quem mais se ausentou foi ' + top.nome + ', com ' + qtd(top.aus, 'ausência', 'ausências') + ' em ' + qtd(top.sE, 'sessão', 'sessões') + '.'; }
  if (SENADO && c.ca && !c.P.partido) { const a = c.ca.total; if (a.aus) s += ' ' + pct(a.just / a.aus, 0) + ' das ausências tiveram justificativa (atividade parlamentar, missão ou licença); ' + qtd(a.ncom, 'foi falta', 'foram faltas') + ' sem justificativa.'; }
  p.textContent = tx(s);
}
function desenharNumeros(c) {
  const t = c.tot, tem = t.sE > 0 || t.vE > 0 || t.pA > 0;
  const set = (k, v) => { root.querySelector('[data-k="' + k + '"]').textContent = tx(v); };
  set('pres', t.sE ? pct(t.pres) : '—');
  const subPres = t.sE ? qtd(t.sP, 'presença', 'presenças') + ' em ' + qtd(t.sE, 'esperada', 'esperadas') : '';
  set('presS', c.dep && c.dep.sE ? (c.dep.pctl != null ? 'Percentil ' + fmtPctl(c.dep.pctl) + ' da Câmara · ' + subPres : subPres + ' · sem percentil: abaixo do mínimo de sessões') : subPres);
  set('aus', t.sE ? num(t.aus) : '—'); set('ausS', 'em ' + qtd(c.nSess, 'sessão deliberativa', 'sessões deliberativas') + (SENADO && c.ca && c.ca.total.aus ? ' · ' + pct(c.ca.total.just / c.ca.total.aus, 0) + ' justificadas' : ''));
  set('vot', t.vE ? pct(t.pvot) : '—'); set('votS', qtd(c.nVot, 'votação nominal', 'votações nominais') + ' no Plenário');
  set('abs', tem ? num(t.vA) : '—'); set('absS', tem ? 'e ' + qtd(t.vO, 'obstrução', 'obstruções') : '');
  set('proj', tem ? num(t.pA) : '—'); set('projS', tem ? 'como primeiro autor, mais ' + qtd(t.pC, 'coautoria', 'coautorias') : '');
  const kc = root.querySelector('[data-k="cota"]');
  if (c.cg) { kc.classList.remove('dash-skeleton'); set('cota', reaisC(c.cg.total)); set('cotaS', c.cg.pares ? reais(c.cg.total / c.cg.pares) + ' por deputado por mês de mandato' : ''); }
  else { set('cota', '—'); set('cotaS', dash.data('gastos_mes').status === 'error' ? 'não foi possível carregar' : ''); if (dash.data('gastos_mes').status !== 'loading') kc.classList.remove('dash-skeleton'); }
  const ke = root.querySelector('[data-k="emen"]');
  if (c.ce) { ke.classList.remove('dash-skeleton'); set('emen', c.ce.total ? reaisC(c.ce.total) : '—'); set('emenS', c.ce.total ? reaisC(c.ce.pago) + ' pagos · ' + pct(c.ce.pix / c.ce.total, 0) + ' por transferência especial' : 'nenhuma emenda individual no recorte'); }
  else { set('emen', '—'); const st = dash.data('emendas').status; set('emenS', st === 'error' ? 'não foi possível carregar' : ''); if (st !== 'loading') ke.classList.remove('dash-skeleton'); }
}

/* ---------- páginas ---------- */
const caixa = (k) => root.querySelector('[data-c="' + k + '"]');
const nota = (k, s) => { root.querySelector('[data-n="' + k + '"]').textContent = tx(s); };
const alternarPartido = (p) => dash.setParams({ partido: lerFiltros().partido === p ? null : p, deputado: null });
const criterio = (c) => (c.P.minimo > 0 ? 'Entre quem esteve em exercício em ao menos ' + num(c.minSess) + ' das ' + num(c.nSess) + ' sessões do período.' : 'Entre todos os que estiveram em exercício no período.');
function legenda(k, itens) {
  const box = root.querySelector('[data-leg="' + k + '"]'); box.hidden = itens.length < 2;
  box.replaceChildren(...itens.map((it) => { const s = el('span', 'cp-legend-i'), sw = el('span', 'cp-sw' + (it.line ? ' cp-sw-line' : '')); sw.style.background = it.c; s.append(sw, document.createTextNode(tx(it.nome))); return s; }));
}
function paginaPresenca(c) {
  const mes = porMes(c.slice, c.meses), ref = c.filtrado ? porMes(c.base, c.meses) : null;
  const series = [{ nome: rotuloRecorte(c), cor: C[0], valores: mes.map((a) => a.pres) }];
  if (ref) series.push({ nome: 'Câmara', cor: 'var(--ds-chart-reference)', valores: ref.map((a) => a.pres) });
  legenda('mes', series.map((s) => ({ nome: s.nome, c: s.cor, line: true })));
  linhaMensal(caixa('mes'), c.meses, series, (i) => [{ k: 'Sessões no mês', v: num(c.D.sessMes.get(c.meses[i])) }, { k: 'Presenças', v: num(mes[i].sP) + ' de ' + num(mes[i].sE) }]);

  const h = histograma(caixa('dist'), c);
  const recorte = !!(c.P.partido || c.P.uf);
  legenda('dist', recorte ? [{ nome: c.P.partido && c.P.uf ? c.P.partido + ' em ' + c.P.uf : (c.P.partido || c.P.uf), c: C[0] }, { nome: 'Demais deputados', c: MUTED }] : []);
  nota('dist', h ? 'Quantos deputados tiveram cada taxa de presença, em faixas de ' + h.w + ' ponto' + (h.w > 1 ? 's' : '') + ' percentual' + (h.w > 1 ? 'is' : '') + '. Entram os ' + num(h.todos) + ' que estiveram em exercício em ao menos ' + qtd(c.minSess, 'sessão', 'sessões') + ' no período; cada faixa inclui o limite inferior. A linha tracejada marca a mediana' + (recorte ? ' do recorte.' : '.') : '');

  const taxa = ui.modo === 'taxa';
  const ps = partidosComBancada(c).sort((a, b) => (taxa ? b.taus - a.taus : b.aus - a.aus));
  barras(caixa('partidos'), ps.map((a) => ({
    chave: a.p, rotulo: a.p, valor: taxa ? a.taus : a.aus, texto: taxa ? pct(a.taus) : num(a.aus),
    tip: () => [{ h: a.p }, { k: 'Taxa de ausência', v: pct(a.taus) }, { k: 'Ausências', v: num(a.aus) }, { k: 'Presenças esperadas', v: num(a.sE) }, { k: 'Bancada média', v: dec(a.banc) }],
  })), { cor: C[0], marcado: c.P.partido, aoClicar: alternarPartido, vazio: 'Nenhum partido com bancada média de um deputado nos filtros escolhidos.' });

  const elegiveis = c.deps.filter((d) => d.sE >= c.minSess);
  const ausentes = [...elegiveis].sort((a, b) => (taxa ? b.taus - a.taus || b.aus - a.aus : b.aus - a.aus || b.taus - a.taus)).slice(0, 15);
  nota('ausentes', criterio(c) + (SENADO ? ' Inclui ausências justificadas; os motivos estão nos cards abaixo.' : ' A fonte não distingue faltas justificadas.'));
  const maxAus = d3.max(ausentes, (d) => d.aus) || 1;
  ranking(caixa('ausentes'), ausentes, taxa
    ? { rotulo: 'Taxa de ausência', valor: (d) => pct(d.taus), sub: (d) => qtd(d.aus, 'ausência', 'ausências') + ' em ' + qtd(d.sE, 'sessão', 'sessões'), bar: (d) => d.taus }
    : { rotulo: 'Ausências', valor: (d) => num(d.aus), sub: (d) => pct(d.taus) + ' das ' + num(d.sE) + ' sessões', bar: (d) => d.aus / maxAus }, c);
  const presentes = [...elegiveis].sort((a, b) => b.pres - a.pres || b.sE - a.sE || a.nome.localeCompare(b.nome, 'pt')).slice(0, 15);
  nota('presentes', criterio(c) + ' Em caso de empate, vem primeiro quem teve mais sessões.');
  ranking(caixa('presentes'), presentes, { rotulo: 'Presença', valor: (d) => pct(d.pres), sub: (d) => num(d.sP) + ' de ' + num(d.sE) + ' sessões · percentil ' + fmtPctl(d.pctl) }, c);
  secaoAusencias(c);
}
const TIPOS_VOTO = [
  { k: 'vS', nome: 'Sim', cor: C[0] }, { k: 'vN', nome: 'Não', cor: C[1] }, { k: 'vA', nome: 'Abstenção', cor: C[2] },
  { k: 'vO', nome: 'Obstrução', cor: C[3] }, { k: 'vX', nome: SENADO ? 'Voto secreto ou da Presidência' : 'Outros registros', cor: C[4] }, { k: 'nvot', nome: 'Não votou', cor: MUTED },
];
function paginaVotacoes(c) {
  secaoObstrucao(c);
  legenda('votos', TIPOS_VOTO.map((t) => ({ nome: t.nome, c: t.cor })));
  const ps = partidosComBancada(c).filter((a) => a.vE > 0).sort((a, b) => b.pvot - a.pvot);
  barras(caixa('votosPartido'), ps.map((a) => ({
    chave: a.p, rotulo: a.p, valor: a.pvot, texto: pct(a.pvot), segs: TIPOS_VOTO.map((t) => ({ v: a[t.k], cor: t.cor, nome: t.nome })),
  })), { marcado: c.P.partido, aoClicar: alternarPartido, vazio: 'Nenhuma votação nominal com os filtros escolhidos.' });

  const comVoto = c.deps.filter((d) => d.vE > 0);
  ranking(caixa('maisVotou'), [...comVoto].sort((a, b) => b.vot - a.vot || b.pvot - a.pvot).slice(0, 15),
    { rotulo: 'Votos', valor: (d) => num(d.vot), sub: (d) => pct(d.pvot) + ' das ' + num(d.vE) + ' votações', bar: (d) => d.pvot, vazio: 'Nenhuma votação nominal com os filtros escolhidos.' }, c);
  nota('menosVotou', c.P.minimo > 0 ? 'Entre quem esteve em exercício em ao menos ' + num(c.minVot) + ' das ' + num(c.nVot) + ' votações do período.' : 'Entre todos os que estiveram em exercício em alguma votação.');
  ranking(caixa('menosVotou'), comVoto.filter((d) => d.vE >= c.minVot).sort((a, b) => a.pvot - b.pvot || b.vE - a.vE).slice(0, 15),
    { rotulo: 'Participação', valor: (d) => pct(d.pvot), sub: (d) => num(d.vot) + ' votos em ' + num(d.vE) + ' votações', bar: (d) => d.pvot, vazio: 'Ninguém atende ao mínimo de votações com os filtros escolhidos.' }, c);
  const abst = comVoto.filter((d) => d.vA > 0).sort((a, b) => b.vA - a.vA || b.pabs - a.pabs).slice(0, 15), maxAbst = abst.length ? abst[0].vA : 1;
  ranking(caixa('abst'), abst, { rotulo: 'Abstenções', valor: (d) => num(d.vA), sub: (d) => pct(d.pabs) + ' dos ' + num(d.vot) + ' votos', bar: (d) => d.vA / maxAbst, vazio: 'Nenhuma abstenção com os filtros escolhidos.' }, c);
  const obst = comVoto.filter((d) => d.vO > 0).sort((a, b) => b.vO - a.vO || b.pobs - a.pobs).slice(0, 15), maxObst = obst.length ? obst[0].vO : 1;
  const orientadas = (d) => { const a = c.cv && c.cv.porDep.get(d.id); return a && a.obs ? ' · ' + pct(a.oo / a.obs, 0) + ' orientadas pelo partido' : ''; };
  ranking(caixa('obst'), obst, { rotulo: 'Obstruções', valor: (d) => num(d.vO), sub: (d) => pct(d.pobs) + ' dos ' + num(d.vot) + ' votos' + orientadas(d), bar: (d) => d.vO / maxObst, vazio: 'Nenhuma obstrução com os filtros escolhidos.' }, c);
}
function paginaProjetos(c) {
  const mes = porMes(c.slice, c.meses);
  colunasMensais(caixa('projMes'), c.meses, mes.map((a) => a.pA), C[0], 'Projetos apresentados');
  const autores = c.deps.filter((d) => d.pA > 0).sort((a, b) => b.pA - a.pA || b.pC - a.pC).slice(0, 20);
  const maxA = autores.length ? autores[0].pA : 1;
  ranking(caixa('maisProj'), autores, { rotulo: 'Projetos', valor: (d) => num(d.pA), sub: (d) => qtd(d.pC, 'coautoria', 'coautorias'), bar: (d) => d.pA / maxA, vazio: 'Nenhum projeto apresentado com os filtros escolhidos.' }, c);
  const ps = c.parts.filter((a) => a.pA > 0).sort((a, b) => b.pA - a.pA);
  barras(caixa('projPartido'), ps.map((a) => ({
    chave: a.p, rotulo: a.p, valor: a.pA, texto: num(a.pA),
    tip: () => [{ h: a.p }, { k: 'Projetos como primeiro autor', v: num(a.pA) }, { k: 'Coautorias', v: num(a.pC) }, { k: 'Bancada média', v: dec(a.banc) }, { k: 'Projetos por deputado', v: dec(a.ppd) }],
  })), { cor: C[0], marcado: c.P.partido, aoClicar: alternarPartido, vazio: 'Nenhum projeto apresentado com os filtros escolhidos.' });
}
function paginaDeputados(c) {
  const T = notasTrabalho(c);
  for (const d of c.deps) { const o = T.notas.get(d.id); d.nota = o ? o.nota : null; const a = c.cv && c.cv.porDep.get(d.id); d.fid = a ? a.fid : null; d.gov = a ? a.gov : null; d.cota = c.cg ? (c.cg.mensal.get(d.id) ?? null) : null; const em = c.ce && c.ce.porDep.get(d.id); d.emen = em ? em.porAno : null; d.pix = em ? em.ppix : null; if (SENADO) d.ncom = c.ca ? ((c.ca.porDep.get(d.id) || {}).ncom || 0) : null; }
  const q = semAcento(ui.q.trim());
  const lista = q ? c.deps.filter((d) => semAcento(d.nome).includes(q)) : c.deps;
  nota('tabDep', num(lista.length) + (lista.length === 1 ? ' deputado' : ' deputados') + ' com os filtros escolhidos. O percentil compara a presença de cada um com a de todos os ' + num(c.nPctl) + ' deputados da Câmara que estiveram em exercício em ao menos ' + qtd(c.minSess, 'sessão', 'sessões') + ' no período: percentil 80 quer dizer presença igual ou maior que a de 80% deles. Clique em um cabeçalho para ordenar e em uma linha para ver os números do deputado no alto da página.');
  tabela(caixa('tabDep'), lista, COLS_DEP, ui.sortDep, 'dep', c.P.deputado, 'dep');
}
function paginaPartidos(c) {
  for (const a of c.parts) { const b = c.cv && c.cv.porPart.get(a.p); a.coesao = b ? b.fid : null; a.gov = b ? b.gov : null; a.cota = c.cg && c.cg.totalPart.get(a.p) ? c.cg.totalPart.get(a.p) / (c.cg.mesesPart.get(a.p) || 1) : null; const em = c.ce && c.ce.porPart.get(a.p); a.pix = em && em.e ? em.pix / em.e : null; }
  tabela(caixa('tabPart'), c.parts.filter((a) => a.sE > 0 || a.pA > 0), COLS_PART, ui.sortPart, 'partido', c.P.partido, 'part');
}
function paginaTrabalho(c) {
  const T = notasTrabalho(c);
  const box = caixa('pesos');
  if (!box.children.length) {
    box.classList.remove('dash-skeleton');
    for (const f of FATORES) {
      const w = el('div', 'cp-peso'), cab = el('div', 'cp-peso-n');
      cab.append(el('span', null, f.nome));
      const seg = el('div', 'cp-seg'); seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Peso de ' + f.nome);
      for (const v of [0, 1, 2, 3]) { const b = el('button', 'cp-seg-b', v === 0 ? 'Fora' : '×' + v); b.type = 'button'; b.dataset.peso = f.k; b.dataset.v = String(v); seg.append(b); }
      w.append(cab, el('span', 'cp-peso-d', f.desc), seg); box.append(w);
    }
  }
  for (const b of box.querySelectorAll('[data-peso]')) b.setAttribute('aria-pressed', String((ui.pesos[b.dataset.peso] || 0) === +b.dataset.v));
  nota('trabalho', 'Uma nota de 0 a 100 que combina cinco critérios. Em cada um, o deputado recebe o percentil dele entre os ' + num(T.n) + ' deputados da Câmara que estiveram em exercício em ao menos ' + qtd(c.minSess, 'sessão', 'sessões') + ' no período; a nota é a média ponderada desses percentis. Ajuste o peso de cada critério abaixo. É um indicador de atividade registrada: cargos como Presidência da Câmara, Mesa e lideranças, relatorias e articulação política não aparecem nos dados.');

  const escopo = c.deps.filter((d) => T.notas.has(d.id) && T.notas.get(d.id).nota != null).map((d) => T.notas.get(d.id));
  const linha = (o) => Object.assign({}, o.d, { nota: o.nota, comp: o.comp });
  const sub = (d) => FATORES.filter((f) => (ui.pesos[f.k] || 0) > 0).map((f) => f.mostra(d)).join(' · ');
  const opts = (vazio) => ({ rotulo: 'Nota', valor: (d) => fmtNota(d.nota), sub, bar: (d) => d.nota / 100, vazio });
  const msgVazio = T.somaPesos ? 'Ninguém atende ao mínimo de sessões com os filtros escolhidos.' : 'Dê peso a pelo menos um critério para calcular a nota.';
  const recorte = c.P.partido || c.P.uf ? ' Entre os deputados ' + (c.P.partido && c.P.uf ? 'do ' + c.P.partido + ' em ' + c.P.uf : c.P.partido ? 'do ' + c.P.partido : 'de ' + c.P.uf) + ', com a nota calculada contra a Câmara inteira.' : '';
  nota('trabMais', '15 maiores notas.' + recorte);
  nota('trabMenos', '15 menores notas, da menor para a maior.' + recorte);
  ranking(caixa('trabMais'), [...escopo].sort((a, b) => b.nota - a.nota).slice(0, 15).map(linha), opts(msgVazio), c);
  ranking(caixa('trabMenos'), [...escopo].sort((a, b) => a.nota - b.nota).slice(0, 15).map(linha), opts(msgVazio), c);

  const cardDep = root.querySelector('#trabalho-deputado');
  const od = c.P.deputado ? T.notas.get(c.P.deputado) : null;
  cardDep.hidden = !c.P.deputado;
  if (c.P.deputado) {
    const nome = rotuloRecorte(c);
    root.querySelector('[data-n="trabCompT"]').textContent = od && od.nota != null ? 'Nota de ' + nome + ': ' + fmtNota(od.nota) : 'Nota de ' + nome;
    if (!od) vazio(caixa('trabComp'), nome + ' não atinge o mínimo de sessões para receber nota no período.');
    else barras(caixa('trabComp'), FATORES.map((f) => ({
      chave: f.k, rotulo: f.nome, valor: od.comp[f.k], texto: 'percentil ' + fmtPctl(od.comp[f.k]),
      tip: () => [{ h: f.nome }, { k: 'Percentil', v: fmtPctl(od.comp[f.k]) }, { k: 'Peso', v: ui.pesos[f.k] ? '×' + ui.pesos[f.k] : 'fora da nota' }, { k: 'Valor', v: f.mostra(od.d) }],
    })), { cor: C[0], max: 1 });
  }
}
const PAGINAS = { presenca: paginaPresenca, votacoes: paginaVotacoes, pauta: paginaPauta, projetos: paginaProjetos, gastos: paginaGastos, emendas: paginaEmendas, trabalho: paginaTrabalho, deputados: paginaDeputados, partidos: paginaPartidos, metodo: () => {} };

function desenharPagina() {
  for (const b of root.querySelectorAll('.cp-tab')) { const on = b.dataset.tab === ui.tab; b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1; }
  for (const t of TABS) root.querySelector('#' + t).hidden = t !== ui.tab;
  for (const b of root.querySelectorAll('.cp-seg-b[data-modo]')) b.setAttribute('aria-pressed', String(b.dataset.modo === ui.modo));
  if (ctx) PAGINAS[ui.tab](ctx);
}
function semDados(status) {
  ctx = null;
  const carregando = status === 'loading';
  for (const e of root.querySelectorAll('[data-k]')) e.textContent = e.classList.contains('cp-kpi-v') ? '—' : '';
  $('.cp-takeaway').textContent = '—';
  for (const b of root.querySelectorAll('[data-c]')) {
    if (carregando) { if (!b.classList.contains('dash-skeleton')) b.replaceChildren(); continue; }
    b.replaceChildren(status === 'error' ? el('div', 'cp-err', 'Não foi possível carregar') : el('p', 'cp-card-n', 'Os dados ainda não estão disponíveis.'));
  }
}

/* ---------- eventos ---------- */
function abrirAba(t, marcarLink) { if (!PAGINAS[t]) return; ui.tab = t; desenharPagina(); if (marcarLink) { dash.setLink(t); linksCasa(); } }
function escolherDeputado(id) { dash.setParams({ deputado: lerFiltros().deputado === id ? null : id }); root.scrollIntoView({ block: 'start', behavior: 'smooth' }); }
root.addEventListener('click', (ev) => {
  const t = ev.target;
  const aba = t.closest('.cp-tab'); if (aba) return abrirAba(aba.dataset.tab, true);
  const chip = t.closest('.cp-chip');
  if (chip) {
    const a = chip.dataset.ano, atual = lerFiltros().anos;
    return dash.setParams({ anos: a === '' ? [] : (atual.includes(a) ? atual.filter((x) => x !== a) : [...atual, a].sort()) });
  }
  const peso = t.closest('[data-peso]'); if (peso) { ui.pesos[peso.dataset.peso] = +peso.dataset.v; return desenharPagina(); }
  const modo = t.closest('.cp-seg-b[data-modo]'); if (modo) { ui.modo = modo.dataset.modo; return desenharPagina(); }
  const modoEm = t.closest('.cp-seg-b[data-modoem]'); if (modoEm) { ui.modoEm = modoEm.dataset.modoem; return desenharPagina(); }
  const ord = t.closest('.cp-th-b');
  if (ord) { const s = { dep: ui.sortDep, part: ui.sortPart, obs: ui.sortObs, pauta: ui.sortPauta, det: ui.sortDet, forn: ui.sortForn, dest: ui.sortDest, fav: ui.sortFav }[ord.dataset.qual] || ui.sortPart; const k = ord.dataset.sort; if (s.k === k) s.dir = -s.dir; else { s.k = k; s.dir = (k === 'nome' || k === 'p' || k === 'uf') ? 1 : -1; } return desenharPagina(); }
  if (t.closest('.cp-picked')) return dash.setParams({ deputado: null });
  if (t.closest('.cp-reset')) { ui.q = ''; $('.cp-busca').value = ''; return dash.resetParams(); }
  if (t.closest('a')) return;
  if (t.closest('.cp-tema-picked')) { ui.tema = null; return desenharPagina(); }
  if (t.closest('.cp-fechar-prop')) { ui.prop = null; return desenharPagina(); }
  const lprop = t.closest('tr[data-prop]'); if (lprop) { ui.prop = ui.prop === lprop.dataset.prop ? null : lprop.dataset.prop; desenharPagina(); if (ui.prop) root.querySelector('#pauta-detalhe').scrollIntoView({ block: 'nearest', behavior: 'smooth' }); return; }
  if (t.closest('tr[data-vot]') || t.closest('tr[data-forn]')) return;
  const lp = t.closest('tr[data-partido]'); if (lp) return alternarPartido(lp.dataset.partido);
  const ld = t.closest('[data-dep]'); if (ld) return escolherDeputado(ld.dataset.dep);
});
root.addEventListener('keydown', (ev) => {
  if (ev.key !== 'Enter' && ev.key !== ' ') return;
  const tr = ev.target.matches && ev.target.matches('[data-dep], tr[data-partido]') ? ev.target : null; if (!tr) return;
  ev.preventDefault(); if (tr.dataset.partido) alternarPartido(tr.dataset.partido); else escolherDeputado(tr.dataset.dep);
});
$('.cp-f-partido').addEventListener('change', (ev) => dash.setParams({ partido: ev.target.value || null, deputado: null }));
$('.cp-f-uf').addEventListener('change', (ev) => dash.setParams({ uf: ev.target.value || null, deputado: null }));
$('.cp-f-min').addEventListener('change', (ev) => dash.setParams({ minimo: Number(ev.target.value) }));
$('.cp-busca-pauta').addEventListener('input', (ev) => { ui.qPauta = ev.target.value; if (ctx && ui.tab === 'pauta') paginaPauta(ctx); });
$('.cp-busca').addEventListener('input', (ev) => { ui.q = ev.target.value; if (ctx && ui.tab === 'deputados') paginaDeputados(ctx); });

/* ---------- casa legislativa ---------- */
for (const e of root.querySelectorAll('[data-casa]')) e.hidden = e.dataset.casa !== dash.casa;
if (SENADO) {
  document.title = 'Presença no Senado';
  const andar = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: (n) => (n.parentElement.closest('[data-casa], [data-notx]') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT) });
  const nos = []; while (andar.nextNode()) nos.push(andar.currentNode);
  for (const n of nos) { const t = tx(n.nodeValue); if (t !== n.nodeValue) n.nodeValue = t; }
  for (const e of root.querySelectorAll('[placeholder], [aria-label]')) for (const a of ['placeholder', 'aria-label']) if (e.hasAttribute(a)) e.setAttribute(a, tx(e.getAttribute(a)));
} else document.title = 'Presença na Câmara';
function linksCasa() {
  const q = new URLSearchParams(location.search); q.delete('deputado'); q.delete('casa');
  for (const a of root.querySelectorAll('[data-casa-link]')) {
    const qq = new URLSearchParams(q); if (a.dataset.casaLink === 'senado') qq.set('casa', 'senado');
    const s = qq.toString(); a.href = './' + (s ? '?' + s : '') + location.hash;
    if (a.dataset.casaLink === dash.casa) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  }
}
linksCasa();
window.addEventListener('hashchange', linksCasa);

const inicial = (location.hash || '').slice(1);
if (PAGINAS[inicial]) ui.tab = inicial;

dash.onData(() => {
  const fv = FONTES_VOT.map((id) => dash.data(id));
  const src = dash.data('presenca');
  const linhas = src.status === 'ok' && Array.isArray(src.data) ? src.data : [];
  if (src.status !== 'loading') for (const e of root.querySelectorAll('.dash-skeleton')) e.classList.remove('dash-skeleton');
  if (!linhas.length) { semDados(src.status); desenharPagina(); return; }
  const chave = linhas.length + '|' + JSON.stringify(linhas[0]) + JSON.stringify(linhas[linhas.length - 1]);
  if (cache.key !== chave) cache = { key: chave, D: prep(linhas) };
  ctx = contexto(cache.D);
  if (fv.every((x) => x.status === 'ok' && Array.isArray(x.data) && x.data.length)) {
    const k2 = fv.map((x) => x.data.length + JSON.stringify(x.data[0])).join('|');
    if (cache2.key !== k2) cache2 = { key: k2, V: prepVot(fv[0].data, fv[1].data, fv[2].data) };
    ctx.cv = contextoVot(ctx, cache2.V);
  } else ctx.cv = null;
  const fg = FONTES_GASTOS.map((id) => dash.data(id));
  if (fg.every((x) => x.status === 'ok' && Array.isArray(x.data))) {
    const k3 = fg.map((x) => x.data.length + JSON.stringify(x.data[0] || {})).join('|');
    if (cache3.key !== k3) cache3 = { key: k3, G: prepGastos(fg[0].data, fg[1].data, fg[2].data) };
    ctx.cg = contextoGastos(ctx, cache3.G);
  } else ctx.cg = null;
  if (SENADO) {
    const fa = dash.data('ausencias');
    if (fa.status === 'ok' && Array.isArray(fa.data)) {
      const k5 = fa.data.length + JSON.stringify(fa.data[0] || {});
      if (cache5.key !== k5) cache5 = { key: k5, A: prepAusencias(fa.data) };
      ctx.ca = contextoAusencias(ctx, cache5.A);
    } else ctx.ca = null;
  }
  const fe = FONTES_EMENDAS.map((id) => dash.data(id));
  if (fe.every((x) => x.status === 'ok' && Array.isArray(x.data))) {
    const k4 = fe.map((x) => x.data.length + JSON.stringify(x.data[0] || {})).join('|');
    if (cache4.key !== k4) cache4 = { key: k4, E: prepEmendas(fe[0].data, fe[1].data, fe[2].data, fe[3].data, fe[4].data) };
    ctx.ce = contextoEmendas(ctx, cache4.E);
  } else ctx.ce = null;
  const meta = dash.data('meta');
  const fd = root.querySelector('.cp-fonte-data');
  if (meta.status === 'ok' && meta.data) {
    const m = meta.data, quando = new Date(m.gerado_em);
    const hora = isNaN(quando) ? '' : quando.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo' });
    fd.textContent = 'Cobre de ' + fmtData(m.periodo.inicio) + ' a ' + fmtData(m.periodo.fim) + '; última votação registrada em ' + fmtData(m.ultima_votacao) + '. Atualizado em ' + hora + '.';
  } else fd.textContent = '';
  desenharFiltros(ctx); desenharResumo(ctx); desenharNumeros(ctx); desenharPagina(); linksCasa();
});
}
