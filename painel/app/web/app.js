'use strict';
/* Alicia Server — painel. Parte 1: base, login, navegação, início, busca, tour, modo TV.
   (p_a.js: Alicia, Arquivos, Servidor, Registros, Configurações · p_b.js: Filmes, Jogos, Música, RPG) */

const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e[k] = v;
    else if (k === 'style') e.style.cssText = v;
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const c of kids.flat(2)) { if (c == null || c === false) continue; e.append(c.nodeType ? c : document.createTextNode(String(c))); }
  return e;
}
const J = { 'Content-Type': 'application/json' };
async function api(u, o = {}) {
  const r = await fetch(u, o);
  if (r.status === 401 && u !== '/api/login') { mostrarLogin(); throw new Error('login'); }
  if (!r.ok) {
    let m = 'Algo deu errado. Tente de novo.';
    try { m = (await r.json()).detail || m; } catch (e) {}
    toast(m, 'erro'); throw new Error(m);
  }
  return (r.headers.get('content-type') || '').includes('json') ? r.json() : r;
}
const post = (u, b) => api(u, { method: 'POST', headers: J, body: JSON.stringify(b || {}) });
function toast(t, tipo) {
  const e = $('#toast'); e.textContent = t; e.className = 'show ' + (tipo || '');
  clearTimeout(toast.t); toast.t = setTimeout(() => e.className = '', 3800);
}
const mm = s => { s = Math.max(0, Math.floor(s || 0)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
const fmtB = b => b > 1e9 ? (b / 1e9).toFixed(1) + ' GB' : b > 1e6 ? (b / 1e6).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1e3)) + ' KB';
const debounce = (f, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => f(...a), ms); }; };
const cap = s => s ? s[0].toUpperCase() + s.slice(1) : s;
function vazio(titulo, texto) { return h('div', { class: 'vazio' }, h('b', null, titulo), texto || ''); }
function cabecalho(titulo, sub, ...extra) { return h('div', { class: 'pgh' }, h('div', null, h('h2', null, titulo), sub && h('p', null, sub)), h('div', { class: 'lin' }, extra)); }

/* ---------- janelas (modal) ---------- */
function modal(conteudo, larga) {
  const m = $('#modal'); m.textContent = '';
  m.append(h('div', { class: 'cx' + (larga ? ' larga' : '') }, conteudo)); m.classList.add('show');
  m.onclick = e => { if (e.target === m) fechaModal(); };
}
function fechaModal() { const m = $('#modal'); m.classList.remove('show'); m.textContent = ''; }
function confirma(titulo, texto, btn, fn, perigo) {
  modal(h('div', { style: 'max-width:420px' }, h('h3', null, titulo), h('p', { class: 'mut' }, texto),
    h('div', { class: 'lin', style: 'justify-content:flex-end;margin-top:14px' },
      h('button', { class: 'btn sec', onclick: fechaModal }, 'Cancelar'),
      h('button', { class: 'btn' + (perigo ? ' perigo' : ''), onclick: () => { fechaModal(); fn(); } }, btn))));
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') { fechaModal(); $('#resBusca').style.display = 'none'; } });

/* ---------- envio com barra de progresso (arquivos grandes) ---------- */
function enviarArquivo(url, file, aoProgresso) {
  return new Promise((ok, erro) => {
    const x = new XMLHttpRequest(); x.open('POST', url);
    x.upload.onprogress = e => { if (e.lengthComputable && aoProgresso) aoProgresso(e.loaded / e.total); };
    x.onload = () => {
      if (x.status >= 200 && x.status < 300) return ok();
      let m = 'Não consegui enviar ' + file.name + '.'; try { m = JSON.parse(x.responseText).detail || m; } catch (e) {}
      toast(m, 'erro'); erro(new Error(m));
    };
    x.onerror = () => { toast('A conexão caiu durante o envio de ' + file.name + '.', 'erro'); erro(new Error('rede')); };
    const fd = new FormData(); fd.append('arquivo', file); x.send(fd);
  });
}
function zonaEnvio(el, aoSoltar) {
  el.ondragover = e => { e.preventDefault(); el.classList.add('over'); };
  el.ondragleave = () => el.classList.remove('over');
  el.ondrop = e => { e.preventDefault(); el.classList.remove('over'); aoSoltar([...e.dataTransfer.files]); };
}

/* ---------- gráfico pequeno ---------- */
function spark(cv, dados, max, cor) {
  const dpr = devicePixelRatio || 1, w = cv.clientWidth, hh = cv.clientHeight; if (!w) return;
  cv.width = w * dpr; cv.height = hh * dpr; const c = cv.getContext('2d'); c.scale(dpr, dpr); c.clearRect(0, 0, w, hh);
  if (dados.length < 2) return;
  const m = max || Math.max(1, ...dados), pts = dados.map((v, i) => [i / (dados.length - 1) * w, hh - 3 - Math.min(1, v / m) * (hh - 6)]);
  const cs = cor || getComputedStyle(document.documentElement).getPropertyValue('--acc').trim();
  c.beginPath(); pts.forEach(([x, y], i) => i ? c.lineTo(x, y) : c.moveTo(x, y)); c.strokeStyle = cs; c.lineWidth = 2; c.lineJoin = 'round'; c.stroke();
  c.lineTo(w, hh); c.lineTo(0, hh); c.closePath(); const g = c.createLinearGradient(0, 0, 0, hh); g.addColorStop(0, cs + '55'); g.addColorStop(1, cs + '00'); c.fillStyle = g; c.fill();
}

/* ---------- estado geral ---------- */
const PAGES = [['inicio', '🏠', 'Início'], ['alicia', '💬', 'Alicia'], ['arquivos', '📁', 'Arquivos'], ['filmes', '🎬', 'Filmes'], ['jogos', '🎮', 'Jogos'],
  ['musica', '🎵', 'Música'], ['rpg', '🎲', 'RPG'], ['servidor', '🖥️', 'Servidor'], ['registros', '📜', 'Registros'], ['config', '⚙️', 'Configurações']];
const PRINCIPAIS = ['inicio', 'alicia', 'jogos', 'musica', 'filmes'];
let S = null, EU = null, atual = '';
const hist = { cpu: [], ram: [], rx: [], tx: [] }; let ultRede = null;
const ENTRAR = {};
const svc = n => S && S.servicos.find(x => x.nome.startsWith(n));
const ligado = n => { const s = svc(n); return !!s && s.estado === 'ligado'; };

function mostrarLogin() {
  $('#app').style.display = 'none'; $('#login').style.display = 'grid';
  fetch('/api/publico').then(r => r.json()).then(d => { $('#lgVis').style.display = d.visitante ? 'block' : 'none'; }).catch(() => {});
}
$('#lgVisitante').onclick = async () => { try { await post('/api/visitante'); iniciar(); } catch (e) {} };
async function entrar() {
  try {
    await post('/api/login', { usuario: $('#lgU').value, senha: $('#lgS').value });
    $('#lgS').value = ''; iniciar();
  } catch (e) {}
}
$('#lgEntrar').onclick = entrar; $('#lgS').onkeydown = e => { if (e.key === 'Enter') entrar(); };
$('#btSair').onclick = async () => { await fetch('/api/logout', { method: 'POST' }); location.reload(); };

function aplicaPrefs() {
  try {
    const tm = localStorage.getItem('tema'); if (tm) document.documentElement.dataset.tema = tm; corMeta(); const fu = localStorage.getItem('fundo'); if (fu) document.documentElement.dataset.fundo = fu;
    document.body.classList.toggle('tv', localStorage.getItem('tv') === '1');
  } catch (e) {}
}
const TEMAS = [  // id, nome, descrição, [fundo, cartão, destaque, texto]
  ['', 'Roxo Noturno', 'O clássico da casa, com aurora', ['#0d0f15', '#1a1d27', '#a78bfa', '#eceff8'], 'escuro'],
  ['preto', 'Preto Total', 'Dark mode puro, economiza bateria em tela OLED', ['#000000', '#101014', '#a78bfa', '#eceff8'], 'escuro'],
  ['grafite', 'Grafite', 'Cinza sóbrio com azul-claro', ['#121316', '#1e2025', '#7dd3fc', '#eceff8'], 'escuro'],
  ['oceano', 'Oceano', 'Azul profundo e turquesa', ['#06111b', '#0e2335', '#38bdf8', '#eceff8'], 'escuro'],
  ['floresta', 'Floresta', 'Verdes de mata fechada', ['#08120d', '#12241a', '#4ade80', '#eceff8'], 'escuro'],
  ['sol', 'Pôr do Sol', 'Laranja e rosa de fim de tarde', ['#150b0f', '#271820', '#fb923c', '#eceff8'], 'escuro'],
  ['sakura', 'Sakura', 'Rosa de flor de cerejeira', ['#150c17', '#27182c', '#f9a8d4', '#eceff8'], 'escuro'],
  ['neon', 'Neon', 'Ciano e magenta, estilo cyberpunk', ['#07060f', '#120f26', '#22d3ee', '#eceff8'], 'escuro'],
  ['retro', 'Retrô Terminal', 'Verde fósforo e letra de computador antigo', ['#030803', '#0b160b', '#4ade80', '#d4ffd4'], 'escuro'],
  ['lavanda', 'Claro Lavanda', 'Modo claro, suave e elegante', ['#f1f0fa', '#ffffff', '#6d4ae0', '#1d1b2e'], 'claro'],
  ['ceu', 'Claro Céu', 'Modo claro azulado', ['#eaf3fb', '#ffffff', '#0369a1', '#10283c'], 'claro'],
  ['papel', 'Papel', 'Modo claro quente, cor de papel', ['#f5efe2', '#fffdf7', '#b45309', '#2b2418'], 'claro'],
  ['contraste', 'Alto Contraste', 'Preto e amarelo, para enxergar melhor', ['#000000', '#0b0b0b', '#ffd400', '#ffffff'], 'acessível'],
];
function corMeta() { const t = TEMAS.find(x => x[0] === (document.documentElement.dataset.tema || '')); const m = document.querySelector('meta[name=theme-color]'); if (m && t) m.content = t[3][0]; }
function setTema(id) { document.documentElement.dataset.tema = id; corMeta(); try { localStorage.setItem('tema', id); } catch (e) {} }
function setCor() {}
function setFundo(f) { document.documentElement.dataset.fundo = f === 'aurora' ? '' : f; try { localStorage.setItem('fundo', f === 'aurora' ? '' : f); } catch (e) {} }
function setTV(v) { document.body.classList.toggle('tv', v); try { localStorage.setItem('tv', v ? '1' : '0'); } catch (e) {} toast(v ? 'Modo TV ligado: use as setas e o OK.' : 'Modo TV desligado.'); }
$('#btTV').onclick = () => setTV(!document.body.classList.contains('tv'));
$('#btTour').onclick = () => tour(0);

function montaNav() {
  const n = $('#nav'); n.textContent = '';
  n.append(h('div', { class: 'logo' }, h('i'), 'Alicia Server'));
  PAGES.forEach(([id, ic, nome]) => n.append(h('a', { class: 'nv' + (PRINCIPAIS.includes(id) ? '' : ' extra'), 'data-p': id, tabindex: 0, onclick: () => ir(id) }, h('span', { class: 'ic' }, ic), h('span', null, nome))));
  n.append(h('a', { class: 'nv sobr', tabindex: 0, onclick: () => $('#maisMenu').classList.toggle('show') }, h('span', { class: 'ic' }, '⋯'), h('span', null, 'Mais')));
  const mm_ = $('#maisMenu'); mm_.textContent = '';
  PAGES.filter(p => !PRINCIPAIS.includes(p[0])).forEach(([id, ic, nome]) => mm_.append(h('a', { onclick: () => ir(id) }, h('span', { class: 'ic' }, ic), nome)));
}
function ir(p) {
  if (!PAGES.some(x => x[0] === p)) p = 'inicio';
  atual = p;
  $('#main').classList.toggle('imersivo', p === 'filmes');
  $$('.sec').forEach(s => s.classList.toggle('show', s.id === 'p-' + p));
  $$('#nav a.nv[data-p]').forEach(a => a.classList.toggle('on', a.dataset.p === p));
  $('#maisMenu').classList.remove('show'); $('#resBusca').style.display = 'none';
  if (location.hash !== '#' + p) history.replaceState(null, '', '#' + p);
  scrollTo(0, 0);
  if (ENTRAR[p]) ENTRAR[p]();
}
addEventListener('hashchange', () => { const p = location.hash.slice(1); if (p && p !== atual) ir(p); });

async function iniciar() {
  try { EU = await api('/api/eu'); } catch (e) { return; }
  $('#login').style.display = 'none'; $('#app').style.display = 'grid';
  $('#euN').textContent = cap(EU.usuario); $('#euI').textContent = EU.usuario[0].toUpperCase();
  if (EU.convidado) ['arquivos', 'servidor', 'registros', 'config', 'alicia'].forEach(id => { const i = PAGES.findIndex(p => p[0] === id); if (i >= 0) PAGES.splice(i, 1); });   // visitante: só jogos, música, filmes e RPG
  aplicaPrefs(); montaNav();
  ajTopo();
  await status(); setInterval(status, 5000);
  iniciaMusica();
  ir(location.hash.slice(1) || 'inicio');
  try { if (!EU.convidado && !localStorage.getItem('tour_visto')) setTimeout(() => tour(0), 600); } catch (e) {}
}

async function status() {
  try { S = await api('/api/status'); } catch (e) { return; }
  const agora = Date.now();
  if (ultRede) { const dt = (agora - ultRede.t) / 1000; hist.rx.push(Math.max(0, (S.rede_recebido - ultRede.rx) / dt)); hist.tx.push(Math.max(0, (S.rede_enviado - ultRede.tx) / dt)); }
  ultRede = { t: agora, rx: S.rede_recebido, tx: S.rede_enviado };
  hist.cpu.push(S.cpu); hist.ram.push(S.ram);
  for (const k in hist) if (hist[k].length > 60) hist[k].shift();
  if (atual === 'inicio') pintaInicio();
  if (atual === 'servidor' && ENTRAR._pintaServidor) ENTRAR._pintaServidor();
  if (atual === 'alicia' && ENTRAR._aliEstado) ENTRAR._aliEstado();
}

/* ---------- início ---------- */
const CARTOES = [
  ['alicia', '💬', 'Alicia', 'Converse, escolha o jeito dela e use a memória.', () => !ligado('Alicia') ? ['av', 'Iniciando…'] : S.chave_nvidia ? ['ok', 'Ligada'] : ['av', 'Falta a chave da NVIDIA']],
  ['arquivos', '📁', 'Arquivos', 'Seus documentos em qualquer aparelho.', () => ['ok', 'Ligado']],
  ['filmes', '🎬', 'Filmes e Séries', 'Assista no navegador ou no app.', () => ligado('Jellyfin') ? ['ok', 'Ligado'] : ['er', 'Parado']],
  ['jogos', '🎮', 'Jogos', 'Super Nintendo, Nintendo 64, PlayStation e mais, direto no navegador.', () => ['ok', 'Pronto para jogar']],
  ['musica', '🎵', 'Música', 'Sua biblioteca por artista e gênero, tocando no seu aparelho.', () => ['ok', 'Ligado']],
  ['rpg', '🎲', 'RPG', 'Aventuras com a Alicia como mestra, até 5 jogadores.', () => ['ok', 'Ligado']],
  ['servidor', '🖥️', 'Servidor', 'Saúde, serviços e tarefas do Hermes.', () => S && S.servicos.some(x => x.estado === 'parado') ? ['av', 'Atenção'] : ['ok', 'Tudo certo']],
];
ENTRAR.inicio = () => {
  const P = $('#p-inicio'); P.textContent = '';
  P.append(h('div', { class: 'anf' }, h('img', { class: 'av', id: 'inAv', src: '/api/alicia/imagem/feliz', alt: 'Alicia' }), h('div', { style: 'position:relative;z-index:1' }, h('h1', { id: 'inSaud' }), h('p', { id: 'inFrase' }))));
  P.append(h('div', { class: 'cards' }, CARTOES.filter(c => PAGES.some(p => p[0] === c[0])).map(([id, ic, nome, desc]) => h('div', { class: 'cartao', tabindex: 0, 'data-id': id, onclick: () => ir(id) }, h('div', { class: 'ic' }, ic), h('h3', null, nome), h('p', null, desc), h('span', { class: 'pill', id: 'cs-' + id })))));
  if (!EU.convidado) {
    P.append(h('div', { class: 'pgh' }, h('h3', null, 'Resumo do servidor'), h('a', { onclick: () => ir('servidor') }, 'Ver detalhes ›')));
    P.append(h('div', { class: 'resumo', id: 'inRes' }));
  }
  pintaInicio();
};
function pintaInicio() {
  if (!S || !$('#inSaud')) return;
  const hr = new Date().getHours(); $('#inSaud').textContent = (hr < 12 ? 'Bom dia' : hr < 18 ? 'Boa tarde' : 'Boa noite') + ', ' + cap(EU.usuario) + '!';
  const parados = S.servicos.filter(x => x.estado === 'parado').map(x => x.nome);
  if (EU.convidado) { $('#inFrase').textContent = 'Você entrou como visitante: pode jogar, ouvir música, assistir filmes e jogar RPG. Divirta-se!'; CARTOES.forEach(([id, , , , f]) => { const [c, t] = f(); const e = $('#cs-' + id); if (e) { e.className = 'pill ' + c; e.textContent = t; } }); return; }
  $('#inFrase').textContent = S.disco > 90 ? 'O disco está quase cheio: apague o que não usa.' : parados.length ? 'Atenção: ' + parados.join(', ') + ' parado. Veja em Servidor.'
    : !S.chave_nvidia ? 'Tudo certo por aqui. Falta só colocar a chave da NVIDIA para a Alicia pensar (Configurações).' : 'Tudo funcionando. Disco com ' + S.disco + '% de uso.';
  CARTOES.forEach(([id, , , , f]) => { const [c, t] = f(); const e = $('#cs-' + id); if (e) { e.className = 'pill ' + c; e.textContent = t; } });
  const r = $('#inRes'); if (!r) return; r.textContent = '';
  const est = (n, v, txt) => h('div', { class: 'est' }, h('div', { class: 'n' }, n, h('span', null, txt)), h('div', { class: 'bar' + (v > 90 ? ' perigo' : v > 75 ? ' aviso' : '') }, h('b', { style: 'width:' + v + '%' })));
  r.append(est('Processador', S.cpu, S.cpu + '%'), est('Memória', S.ram, S.ram + '%'), est('Disco', S.disco, S.disco_livre_gb + ' GB livres'));
}

/* ---------- busca no topo ---------- */
let CJOGOS = null, CJ_T = 0;
async function buscaGlobal() {
  const q = $('#buscaIn').value.trim().toLowerCase(), R = $('#resBusca');
  if (q.length < 2) { R.style.display = 'none'; return; }
  const sec = (t, itens) => itens.length ? [h('div', { class: 'rbt' }, t), ...itens] : [];
  const lin = (img, tit, sub, fn) => h('div', { class: 'rb', tabindex: 0, onclick: () => { R.style.display = 'none'; $('#buscaIn').value = ''; fn(); }, onkeydown: e => { if (e.key === 'Enter') e.target.click(); } },
    typeof img === 'string' && img.startsWith('/') || (typeof img === 'string' && img.startsWith('http')) ? h('img', { src: img, alt: '' }) : h('span', { style: 'width:44px;text-align:center;font-size:26px' }, img), h('div', null, tit, h('small', null, sub)));
  const paginas = PAGES.filter(p => p[2].toLowerCase().includes(q)).map(([id, ic, nome]) => lin(ic, nome, 'Página', () => ir(id)));
  if (!CJOGOS || Date.now() - CJ_T > 60000) { try { CJOGOS = await api('/api/jogos'); CJ_T = Date.now(); } catch (e) { CJOGOS = []; } }
  const jogos = []; CJOGOS.forEach(c => c.jogos.forEach(j => { if (jogos.length < 6 && j.nome.toLowerCase().includes(q)) jogos.push(lin('🎮', j.nome, c.nome, () => abrirJogo(c.pasta, j.arquivo))); }));
  const mus = (srv.musicas || []).filter(m => (m.titulo + ' ' + m.canal).toLowerCase().includes(q)).slice(0, 6).map((m, i, a) => lin(m.capa, m.titulo, m.canal, () => tocarLista([m], 0)));
  const arts = Object.keys(srv.artistas || {}).filter(a => a.toLowerCase().includes(q)).slice(0, 4).map(a => lin('👤', a, 'Artista', () => { ir('musica'); irMusica('artista', a); }));
  const tudo = [...sec('Páginas', paginas), ...sec('Jogos', jogos), ...sec('Músicas', mus), ...sec('Artistas', arts)];
  R.textContent = ''; R.style.display = 'block';
  if (!tudo.length) R.append(h('div', { class: 'vazio' }, 'Nada encontrado. Para músicas novas, use a página Música.'));
  else tudo.forEach(x => R.append(x));
}
$('#buscaIn').oninput = debounce(buscaGlobal, 200);
$('#buscaIn').onkeydown = e => { if (e.key === 'Enter') { const p = $('#resBusca .rb'); if (p) p.click(); } };
document.addEventListener('click', e => { if (!e.target.closest('#busca')) $('#resBusca').style.display = 'none'; });
document.addEventListener('keydown', e => { if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) { e.preventDefault(); $('#buscaIn').focus(); } });

/* ---------- tour (primeiro acesso) ---------- */
const PASSOS = [
  ['👋', 'Bem-vindo ao Alicia Server', 'Este é o seu servidor da casa: a Alicia, seus arquivos, filmes, jogos, músicas e RPG, tudo num lugar só. Vou mostrar rapidinho.'],
  ['💬', 'Alicia', 'Converse por texto ou voz. Ela lembra das conversas e tem vários jeitos: normal, brincalhona, séria, malcriada, carinhosa e o modo sem filtro.'],
  ['🎮', 'Jogos e 🎬 Filmes', 'Jogue Super Nintendo, Nintendo 64, PlayStation e mais direto no navegador, sem instalar nada. Adicione filmes e séries pelo painel e assista na página Filmes.'],
  ['🎵', 'Música', 'Busque qualquer música: ela toca no seu aparelho e fica guardada no servidor, organizada por artista e gênero. A música continua mesmo quando você abre um jogo.'],
  ['🌐', 'De qualquer lugar', 'Instale o Tailscale no celular e entre na mesma conta: o painel abre pelo endereço da rede privada. Em Configurações você vê os endereços e coloca a chave da NVIDIA.'],
];
function tour(n) {
  const [ic, tit, txt] = PASSOS[n];
  modal(h('div', { style: 'max-width:480px;text-align:center' }, h('div', { style: 'font-size:54px' }, ic), h('h2', { style: 'margin:6px 0 10px' }, tit), h('p', { class: 'mut' }, txt),
    h('div', { class: 'lin', style: 'justify-content:center;margin-top:16px' },
      h('button', { class: 'btn sec', onclick: () => { try { localStorage.setItem('tour_visto', '1'); } catch (e) {} fechaModal(); } }, 'Pular'),
      h('button', { class: 'btn', onclick: () => { if (n + 1 < PASSOS.length) tour(n + 1); else { try { localStorage.setItem('tour_visto', '1'); } catch (e) {} fechaModal(); } } }, n + 1 < PASSOS.length ? 'Próximo' : 'Começar')),
    h('div', { class: 'mut peq', style: 'margin-top:10px' }, (n + 1) + ' de ' + PASSOS.length)));
}

/* ---------- modo TV: setas + OK ---------- */
const FOCAVEIS = 'a.nv,.cartao,.mCard,.jogo,.arq,.btn,.btn-ic,.mTab,.chip,.dado,input,select,.rb,.mAc button';
document.addEventListener('keydown', e => {
  const a = document.activeElement;
  if (e.key === 'Enter' && a && a.matches && a.matches('.cartao,.mCard,.jogo,.arq,.chip,.rb,.mTab,a.nv') && !a.matches('button,input')) { a.click(); return; }
  if (!document.body.classList.contains('tv') || !['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) return;
  if (a && /INPUT|TEXTAREA/.test(a.tagName) && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) return;
  if ($('#jogoOverlay').style.display === 'block') return;
  const visivel = el => { const r = el.getBoundingClientRect(); return r.width > 4 && r.height > 4 && getComputedStyle(el).visibility !== 'hidden' && !el.closest('[hidden]') && !el.disabled; };
  const lista = $$(FOCAVEIS).filter(visivel); const ref = (a && lista.includes(a) ? a : lista[0]).getBoundingClientRect();
  const cx = ref.left + ref.width / 2, cy = ref.top + ref.height / 2; let melhor = null, md = 1e9;
  for (const el of lista) {
    if (el === a) continue; const r = el.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2, dx = x - cx, dy = y - cy;
    const ok = e.key === 'ArrowRight' ? dx > 8 && Math.abs(dy) < Math.abs(dx) * 1.5 : e.key === 'ArrowLeft' ? dx < -8 && Math.abs(dy) < Math.abs(dx) * 1.5 :
      e.key === 'ArrowDown' ? dy > 8 && Math.abs(dx) < Math.abs(dy) * 1.5 : dy < -8 && Math.abs(dx) < Math.abs(dy) * 1.5;
    if (!ok) continue; const d = Math.hypot(dx, dy); if (d < md) { md = d; melhor = el; }
  }
  if (melhor) { e.preventDefault(); melhor.focus({ preventScroll: false }); melhor.scrollIntoView({ block: 'nearest', inline: 'nearest' }); }
});

/* ---------- tamanho da interface: acompanha o monitor (tela grande = tudo maior, conteúdo centralizado) ---------- */
function ajTopo() { const t = $('header.topo'); if (t) document.documentElement.style.setProperty('--topo', t.offsetHeight + 'px'); }
function escala() {
  const w = innerWidth, a = innerHeight; let f = 16;
  if (w >= 1700) f = 16 * Math.min(w / 1700, a / 850, 1.9);     // monitor grande / ultrawide / TV 4K
  document.documentElement.style.fontSize = Math.max(16, f).toFixed(2) + 'px';
  ajTopo();
}
escala(); addEventListener('resize', debounce(escala, 150));
let _tam = ''; setInterval(() => { const t = innerWidth + 'x' + innerHeight; if (t !== _tam) { _tam = t; escala(); } }, 1200);   // garante o ajuste também quando o navegador muda de tamanho sem avisar (zoom, TV, janelas)

window.addEventListener('load', () => { aplicaPrefs(); escala(); iniciar(); });
