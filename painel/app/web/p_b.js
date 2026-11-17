'use strict';
/* Parte 3: Filmes, Jogos, Música (com o player que fica por cima de tudo) e RPG */

/* ===================== FILMES E SÉRIES ===================== */
const jfUrl = () => location.protocol + '//' + location.hostname + ':8096/';
ENTRAR.filmes = () => {
  const P = $('#p-filmes'); if (P.dataset.ok) return; P.dataset.ok = '1'; P.textContent = '';
  const fr = h('iframe', { allow: 'autoplay; fullscreen', allowfullscreen: true, src: jfUrl() });
  const caixa = h('div', { class: 'jf' }, fr);
  // Janela para adicionar filmes e séries (o Jellyfin continua ocupando a tela inteira por baixo)
  const abrirEnvio = () => {
    const tipo = h('select', { onchange: () => { const s = tipo.value === 'serie'; nome.style.display = s ? '' : 'none'; temp.style.display = s ? '' : 'none'; } }, h('option', { value: 'filme' }, 'Filme'), h('option', { value: 'serie' }, 'Série'));
    const nome = h('input', { type: 'text', placeholder: 'Nome da série', style: 'display:none;max-width:260px' }), temp = h('input', { type: 'number', value: 1, min: 1, max: 99, title: 'Temporada', style: 'display:none;max-width:90px' });
    const st = h('p', { class: 'mut peq' }), arq = h('input', { type: 'file', multiple: true, style: 'display:none', onchange: e => { enviar([...e.target.files]); e.target.value = ''; } });
    const drop = h('div', { class: 'drop', style: 'margin-top:10px' }, 'ou arraste os arquivos aqui');
    async function enviar(arqs) {
      const serie = tipo.value === 'serie'; if (serie && !nome.value.trim()) { toast('Escreva o nome da série primeiro.', 'erro'); return; } let ok = 0;
      for (let n = 0; n < arqs.length; n++) {
        const f = arqs[n];
        try { await enviarArquivo('/api/filmes/enviar?tipo=' + tipo.value + '&nome=' + encodeURIComponent(nome.value) + '&temporada=' + (+temp.value || 1), f, p => st.textContent = `Enviando ${f.name} (${n + 1} de ${arqs.length})… ${Math.round(p * 100)}%`); ok++; } catch (e) {}
      }
      st.textContent = ok ? ok + ' arquivo(s) enviado(s) ✓ O Jellyfin está atualizando a biblioteca.' : ''; if (ok) { toast('Enviado!', 'ok'); setTimeout(() => { fr.src = jfUrl(); }, 5000); }
    }
    zonaEnvio(drop, enviar);
    modal(h('div', { style: 'max-width:560px' }, h('h3', null, '➕ Adicionar filmes ou séries'),
      h('p', { class: 'mut peq' }, 'Escolha o tipo, selecione os arquivos (.mkv, .mp4, .avi…) e envie. O painel organiza as pastas no padrão do Jellyfin. Filmes: "Nome do Filme (2010).mkv". Episódios: "Nome S01E01.mkv".'),
      h('div', { class: 'lin' }, tipo, nome, temp, h('button', { class: 'btn', onclick: () => arq.click() }, 'Escolher arquivos'), arq), drop, st,
      h('div', { class: 'lin', style: 'justify-content:flex-end;margin-top:10px' }, h('button', { class: 'btn sec', onclick: fechaModal }, 'Fechar'))));
  };
  P.append(h('div', { class: 'fbarra' }, h('b', null, '🎬 Filmes e Séries'), h('span', { class: 'mut peq' }, 'Você entra como "casa", sem senha.'), h('span', { class: 'sp' }),
    !EU.convidado && h('button', { class: 'btn sec peq', onclick: abrirEnvio }, '➕ Adicionar'),
    h('button', { class: 'btn sec peq', onclick: () => { const c = caixa; (c.requestFullscreen || c.webkitRequestFullscreen).call(c); } }, '⛶ Tela cheia total'),
    h('a', { class: 'btn sec peq', href: jfUrl(), target: '_blank' }, '↗ Outra aba')), caixa);
};
/* ===================== JOGOS ===================== */
const JG = { dados: [], q: '', tudo: {}, filtro: 'todos' };
function ajustaJogo() {
  const o = $('#jogoOverlay'); if (o.style.display !== 'block') return;
  let topo = innerHeight;
  [$('#barra'), $('#nav')].forEach(e => { if (e && getComputedStyle(e).display !== 'none' && getComputedStyle(e).position === 'fixed') { const r = e.getBoundingClientRect(); if (r.top > innerHeight / 2) topo = Math.min(topo, r.top); } });
  o.style.bottom = (innerHeight - topo) + 'px'; o.style.left = '0';
}
let JOGO_ATUAL = null;
function abrirJogo(pasta, arquivo) {
  JOGO_ATUAL = { pasta, arquivo, t0: Date.now() };
  $('#jogoFrame').src = '/jogar?c=' + encodeURIComponent(pasta) + '&a=' + encodeURIComponent(arquivo) + '&embed=1';
  $('#jogoOverlay').style.display = 'block'; ajustaJogo(); setTimeout(() => { try { $('#jogoFrame').contentWindow.focus(); } catch (e) {} }, 600);
}
function fecharJogo() { if (JOGO_ATUAL) { const j = JOGO_ATUAL; JOGO_ATUAL = null; try { fetch('/api/jogos/fim', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pasta: j.pasta, arquivo: j.arquivo, segundos: Math.round((Date.now() - j.t0) / 1000) }), keepalive: true }); } catch (e) {} } $('#jogoOverlay').style.display = 'none'; $('#jogoFrame').src = 'about:blank'; }
addEventListener('message', e => { if (e.origin === location.origin && e.data === 'fechar-jogo') fecharJogo(); });
addEventListener('resize', ajustaJogo);
const alturaBarra = () => document.documentElement.style.setProperty('--barraH', getComputedStyle($('#barra')).display === 'none' ? '0px' : $('#barra').offsetHeight + 'px');
new MutationObserver(() => { ajustaJogo(); alturaBarra(); }).observe($('#barra'), { attributes: true, attributeFilter: ['style'] });
$('#barra').addEventListener('click', () => setTimeout(() => { if ($('#jogoOverlay').style.display === 'block') { try { $('#jogoFrame').contentWindow.focus(); } catch (e) {} } }, 50));

const EXT_CONSOLE = { nes: 'Nintendo', sfc: 'Super Nintendo', smc: 'Super Nintendo', z64: 'Nintendo 64', n64: 'Nintendo 64', v64: 'Nintendo 64', gba: 'Game Boy Advance', gb: 'Game Boy', gbc: 'Game Boy', cue: 'PlayStation', chd: 'PlayStation', iso: 'PlayStation', pbp: 'PlayStation', bin: 'PlayStation' };
async function jogosEnviar(arqs, consoleZip, st) {
  let ok = 0;
  for (let n = 0; n < arqs.length; n++) {
    const f = arqs[n], ext = f.name.split('.').pop().toLowerCase(); let pasta = EXT_CONSOLE[ext] || consoleZip;
    if (['png', 'jpg', 'jpeg'].includes(ext)) { const nm = f.name.replace(/\.[^.]+$/, ''); const a = JG.dados.find(c => c.jogos.some(j => j.arquivo.replace(/\.[^.]+$/, '') === nm)); pasta = a ? a.pasta : consoleZip; }
    if (!pasta) { toast('Não sei o console de "' + f.name + '". Escolha o console da lista e envie de novo.', 'erro'); continue; }
    try { await enviarArquivo('/api/arquivos/enviar?caminho=' + encodeURIComponent('Jogos/' + pasta), f, p => st.textContent = `Enviando ${f.name} para ${pasta} (${n + 1} de ${arqs.length})… ${Math.round(p * 100)}%`); ok++; } catch (e) {}
  }
  st.textContent = ok ? ok + ' arquivo(s) enviado(s) ✓' : ''; if (ok) { toast('Jogos adicionados!', 'ok'); jogosPinta(true); }
}
const DESEMP = { leve: ['⚡', 'Leve', 'ok'], 'médio': ['⚖️', 'Médio', 'av'], pesado: ['🔥', 'Pesado', 'er'] };
async function jogoFav(c, j) {
  const antes = j.fav; j.fav = !antes; jogosPinta();
  try { await api('/api/jogos/favorito', { method: 'POST', body: JSON.stringify({ pasta: c.pasta, arquivo: j.arquivo, fav: j.fav }) }); toast(j.fav ? '⭐ ' + j.nome + ' nos favoritos' : 'Tirado dos favoritos', 'ok'); }
  catch (e) { j.fav = antes; jogosPinta(); }
}
function cartaoJogo(c, j) {
  const img = h('img', { class: 'capa', loading: 'lazy', alt: '', src: `/api/jogos/imagem?pasta=${encodeURIComponent(c.pasta)}&arquivo=${encodeURIComponent(j.arquivo)}` });
  img.onerror = () => img.remove();
  const ini = j.nome.replace(/^(the|a|an)\s+/i, '').split(/[\s\-:]+/).filter(Boolean).slice(0, 2).map(x => x[0]).join('').toUpperCase();
  const card = h('div', { class: 'jogo', tabindex: 0, style: `background:linear-gradient(145deg,${c.cor}dd,#1a1d27)`, onclick: () => abrirJogo(c.pasta, j.arquivo), onkeydown: e => { if (e.key === 'Enter' && e.target === card) card.click(); } },
    h('i', { class: 'inicial' }, ini), img,
    h('button', { class: 'fav' + (j.fav ? ' on' : ''), title: j.fav ? 'Tirar dos favoritos' : 'Favoritar', 'aria-label': 'Favoritar ' + j.nome, onclick: e => { e.stopPropagation(); jogoFav(c, j); } }, j.fav ? '★' : '☆'),
    h('em', { class: 'selo', style: 'background:' + c.cor }, c.pasta), h('b', null, j.nome), h('span', null, '▶ Jogar'));
  return card;
}
function painelEmuladores() {
  return h('div', { class: 'emus' }, JG.dados.map(c => {
    const e = c.emulador, d = DESEMP[e.desempenho] || DESEMP.leve, ativo = JG.filtro === c.pasta;
    return h('div', { class: 'emu' + (ativo ? ' ativo' : '') + (e.pronto ? '' : ' off'), tabindex: 0, style: 'border-top-color:' + c.cor, title: e.dica, onclick: () => { JG.filtro = ativo ? 'todos' : c.pasta; jogosPinta(); }, onkeydown: ev => { if (ev.key === 'Enter') ev.target.click(); } },
      h('b', null, c.nome), h('span', { class: 'mut peq' }, '🕹️ ' + e.nome + ' · ' + c.jogos.length + ' jogo(s)'),
      h('div', { class: 'etq' },
        h('span', { class: 'pill ' + (e.pronto ? 'ok' : 'er') }, e.pronto ? '✓ Emulador pronto' : '✗ Emulador ausente'),
        h('span', { class: 'pill ' + d[2], title: e.dica }, d[0] + ' ' + d[1]),
        e.bios !== null && h('span', { class: 'pill ' + (e.bios ? 'ok' : 'av'), title: 'Jogos/BIOS' }, e.bios ? '✓ BIOS' : 'BIOS opcional')));
  }));
}
async function jogosPinta(recarrega) {
  if (recarrega || !JG.dados.length) { try { JG.dados = await api('/api/jogos'); CJOGOS = JG.dados; CJ_T = Date.now(); } catch (e) { return; } }
  const L = $('#jgLista'); if (!L) return; L.textContent = ''; const q = JG.q.toLowerCase(); let total = 0;
  const E = $('#jgEmus'); if (E) { E.textContent = ''; E.append(painelEmuladores()); }
  const chips = $('#jgChips'); if (chips) {
    chips.textContent = ''; const nf = JG.dados.reduce((n, c) => n + c.jogos.filter(j => j.fav).length, 0);
    [['todos', 'Todos'], ['fav', '⭐ Favoritos (' + nf + ')']].concat(JG.dados.filter(c => c.jogos.length).map(c => [c.pasta, c.pasta])).forEach(([k, t]) =>
      chips.append(h('button', { class: 'chip' + (JG.filtro === k ? ' on' : ''), onclick: () => { JG.filtro = k; jogosPinta(); } }, t)));
  }
  const filtroConsole = JG.filtro !== 'todos' && JG.filtro !== 'fav' ? JG.filtro : null;
  if (JG.filtro === 'todos' && !q) {                       // faixa de favoritos no topo
    const fav = []; JG.dados.forEach(c => c.jogos.forEach(j => { if (j.fav) fav.push([c, j]); }));
    if (fav.length) { total += fav.length; L.append(h('div', { class: 'rowh' }, h('h3', null, '⭐ Favoritos', h('span', { class: 'mut peq', style: 'font-weight:400' }, '  ' + fav.length + ' jogo(s)'))), h('div', { class: 'grade' }, fav.map(([c, j]) => cartaoJogo(c, j)))); }
  }
  JG.dados.forEach(c => {
    if (filtroConsole && c.pasta !== filtroConsole) return;
    const js = c.jogos.filter(j => (!q || j.nome.toLowerCase().includes(q)) && (JG.filtro !== 'fav' || j.fav)); if (!js.length) return; total += js.length;
    const todos = JG.tudo[c.pasta] || q || JG.filtro !== 'todos', vis = todos ? js : js.slice(0, 12);
    L.append(h('div', { class: 'rowh' }, h('h3', null, c.nome, h('span', { class: 'mut peq', style: 'font-weight:400' }, '  ' + js.length + ' jogo(s)')), js.length > 12 && !q && JG.filtro === 'todos' && h('a', { onclick: () => { JG.tudo[c.pasta] = !JG.tudo[c.pasta]; jogosPinta(); } }, todos ? 'Mostrar menos' : 'Mostrar todos (' + js.length + ')')));
    L.append(h('div', { class: 'grade' }, vis.map(j => cartaoJogo(c, j))));
  });
  if (!total) L.append(JG.filtro === 'fav' && !q ? vazio('Nenhum favorito ainda', 'Toque na ☆ de um jogo para guardá-lo aqui.') : JG.dados.some(c => c.jogos.length) ? vazio('Nenhum jogo com esse nome.') : vazio('Nenhum jogo ainda', 'Abra "Adicionar jogos" acima e envie os seus jogos (Super Nintendo, Nintendo 64, PlayStation…). Eu coloco cada um na pasta certa.'));
}ENTRAR.jogos = () => {
  const P = $('#p-jogos'); P.textContent = '';
  const st = h('p', { class: 'mut peq' }), arq = h('input', { type: 'file', multiple: true, style: 'display:none' });
  const cons = h('select', null, h('option', { value: '' }, 'Console dos arquivos .zip…'), ['Nintendo', 'Super Nintendo', 'Nintendo 64', 'Game Boy Advance', 'Game Boy', 'PlayStation'].map(c => h('option', null, c)));
  arq.onchange = e => { jogosEnviar([...e.target.files], cons.value, st); e.target.value = ''; };
  const drop = h('div', { class: 'drop', style: 'margin-top:10px' }, 'Arraste os jogos aqui'); zonaEnvio(drop, a => jogosEnviar(a, cons.value, st));
  P.append(cabecalho('Jogos', 'Jogue direto no navegador, sem instalar nada. Seu progresso fica salvo no servidor.', h('input', { type: 'text', placeholder: '🔍 Buscar jogo…', style: 'min-width:220px', oninput: debounce(e => { JG.q = e.target.value; jogosPinta(); }, 200), value: JG.q })));
  if (!EU.convidado) P.append(h('details', { class: 'box' }, h('summary', { style: 'cursor:pointer;font-weight:700' }, '➕ Adicionar jogos'),
    h('p', { class: 'mut peq' }, 'Envie os arquivos dos seus jogos. O painel descobre o console pelo arquivo (inclusive dentro do .zip) e guarda na pasta certa. Para PlayStation, a BIOS vai na pasta Jogos/BIOS. As capas oficiais são buscadas sozinhas; para usar uma sua, envie uma imagem com o mesmo nome do jogo.'),
    h('div', { class: 'lin' }, h('button', { class: 'btn', onclick: () => arq.click() }, 'Escolher arquivos'), cons, arq), drop, st));
  P.append(h('div', { id: 'jgEmus' }), h('div', { id: 'jgChips', class: 'chips' }), h('div', { id: 'jgLista' }, h('div', { class: 'skel' }))); jogosPinta(true);
};

/* ===================== MÚSICA ===================== */
let fila = [], idx = -1, lib = { curtidas: [], playlists: {} }, srv = { artistas: {}, generos: {}, musicas: [], recentes: [], total: 0 }, vista = { t: 'inicio' }, resultados = [], arrastando = false;
let RADIO = true; try { RADIO = localStorage.getItem('radio') !== '0'; } catch (e) {}
const aud = $('#aud'), CORES = ['#7c3aed', '#db2777', '#0d9488', '#2563eb', '#ca8a04', '#dc2626', '#16a34a', '#9333ea'];
const corDe = s => CORES[[...String(s)].reduce((a, c) => a + c.charCodeAt(0), 0) % CORES.length];
const tem = (l, id) => l.some(c => c.id === id), capaDe = l => (l && l[0] ? l[0].capa : ''), dur = s => s ? mm(s) : '';
const embaralha = l => { const a = l.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
async function salvaLib() { try { await post('/api/musica/biblioteca', lib); } catch (e) {} }
async function carregaSrv() { try { srv = await api('/api/musica/servidor'); } catch (e) {} }

function tocarIdx(i) {
  if (i < 0 || i >= fila.length) return; idx = i; const t = fila[i];
  $('#barra').style.display = 'grid'; $('#bTit').textContent = t.titulo; $('#bCanal').textContent = t.canal + ' · carregando…'; $('#bCapa').src = t.capa; $('#bLike').textContent = tem(lib.curtidas, t.id) ? '💚' : '🤍';
  aud.src = '/api/musica/audio/' + t.id; aud.play().catch(() => {});
  if ('mediaSession' in navigator) navigator.mediaSession.metadata = new MediaMetadata({ title: t.titulo, artist: t.canal, artwork: [{ src: t.capa, sizes: '320x180' }] });
  post('/api/musica/tocando', { titulo: t.titulo }).catch(() => {}); marcaAtual();
}
function tocarLista(l, i) { fila = l.slice(); tocarIdx(i); }
function proxima() { if (idx + 1 < fila.length) tocarIdx(idx + 1); else if (RADIO) radioProxima(); }
async function radioProxima() {
  const t = fila[idx]; if (!t) return;
  try { const n = await api('/api/musica/proxima?id=' + t.id + '&vistos=' + fila.map(x => x.id).slice(-60).join(',')); fila.push(n); toast('Tocando a seguir: ' + n.titulo); tocarIdx(fila.length - 1); } catch (e) { $('#bCanal').textContent = 'Fim da fila'; }
}
function anterior() { if (aud.currentTime > 4) aud.currentTime = 0; else if (idx > 0) tocarIdx(idx - 1); }
aud.onplaying = () => { $('#bPlay').textContent = '⏸'; const t = fila[idx]; if (t) $('#bCanal').textContent = t.canal; };
aud.onpause = () => $('#bPlay').textContent = '▶'; aud.onended = proxima;
aud.onerror = () => { if (!aud.getAttribute('src')) return; toast('Não consegui tocar essa música. Pulando…', 'erro'); proxima(); };
aud.onloadeddata = () => carregaSrv().then(() => { if (vista.t !== 'busca' && atual === 'musica') renderMusica(); });
aud.ontimeupdate = () => { const d = aud.duration || 0, c = aud.currentTime || 0; $('#bT0').textContent = mm(c); $('#bT1').textContent = mm(d); if (!arrastando && d) $('#bSeek').value = Math.round(c / d * 1000); };
if ('mediaSession' in navigator) { const m = navigator.mediaSession; m.setActionHandler('nexttrack', proxima); m.setActionHandler('previoustrack', anterior); m.setActionHandler('play', () => aud.play()); m.setActionHandler('pause', () => aud.pause()); }
$('#bPlay').onclick = () => { if (fila.length) aud.paused ? aud.play() : aud.pause(); }; $('#bNext').onclick = proxima; $('#bPrev').onclick = anterior;
aud.volume = .7; $('#bVolR').oninput = e => aud.volume = e.target.value / 100;
$('#bSeek').oninput = () => arrastando = true; $('#bSeek').onchange = e => { if (aud.duration) aud.currentTime = aud.duration * e.target.value / 1000; arrastando = false; };
$('#bLike').onclick = () => { const t = fila[idx]; if (!t) return; const i = lib.curtidas.findIndex(c => c.id === t.id); i >= 0 ? lib.curtidas.splice(i, 1) : lib.curtidas.unshift(t); $('#bLike').textContent = i >= 0 ? '🤍' : '💚'; salvaLib(); if (atual === 'musica') renderMusica(); };
function fecharPlayer() {
  aud.pause(); aud.removeAttribute('src'); aud.load(); fila = []; idx = -1; arrastando = false;
  $('#bTit').textContent = '—'; $('#bCanal').textContent = ''; $('#bSeek').value = 0; $('#bT0').textContent = '0:00'; $('#bT1').textContent = '0:00';
  $('#barra').style.display = 'none'; if ('mediaSession' in navigator) navigator.mediaSession.metadata = null;
  marcaAtual(); if (atual === 'musica') renderMusica();
}
$('#bFechar').onclick = fecharPlayer;
function marcaAtual() { const id = fila[idx] && fila[idx].id; $$('#p-musica .mFaixa').forEach(r => r.classList.toggle('atual', r.dataset.id === id)); }

const TABS = [['inicio', 'Início'], ['descobrir', 'Descobrir'], ['artistas', 'Artistas'], ['generos', 'Gêneros'], ['musicas', 'Músicas'], ['playlists', 'Playlists'], ['curtidas', 'Curtidas'], ['fila', 'Fila']];
function irMusica(t, k) { vista = { t, k }; renderMusica(); }
function cartao(tit, sub, capa, cor, redondo, aoClicar, aoTocar) {
  const im = h('div', { class: 'mCapa' + (redondo ? ' redondo' : ''), style: 'background:' + (capa ? `url("${capa}") center/cover` : `linear-gradient(135deg,${cor},#1a1d27)`) }, !capa ? tit.slice(0, 1).toUpperCase() : '');
  if (aoTocar) im.append(h('button', { class: 'mPlay', title: 'Tocar', onclick: e => { e.stopPropagation(); aoTocar(); } }, '▶'));
  return h('div', { class: 'mCard', tabindex: 0, onclick: aoClicar, onkeydown: e => { if (e.key === 'Enter') aoClicar(); } }, im, h('b', null, tit), h('span', null, sub));
}
function filaH(titulo, cards, verTudo) {
  const r = h('div', { class: 'mFila' }, cards), mover = d => r.scrollBy({ left: d * r.clientWidth * .85, behavior: 'smooth' });
  return h('div', { class: 'mSecao' }, h('div', { class: 'mSecaoH' }, h('h3', null, titulo), verTudo && h('a', { onclick: verTudo }, 'Ver tudo ›')),
    h('div', { class: 'fw' }, h('button', { class: 'seta e', onclick: () => mover(-1) }, '‹'), r, h('button', { class: 'seta d', onclick: () => mover(1) }, '›')));
}
const grade = cards => h('div', { class: 'mGrade' }, cards);
function faixas(lista, opc = {}) {
  return h('div', { class: 'mGrade' }, lista.map((t, i) => {
    const im = h('div', { class: 'mCapa', style: 'background:' + (t.capa ? `url("${t.capa}") center/cover` : `linear-gradient(135deg,${corDe(t.canal)},#1a1d27)`) }, h('button', { class: 'mPlay', title: 'Tocar' }, '▶'));
    const bt = (txt, tt, fn) => h('button', { title: tt, onclick: e => { e.stopPropagation(); fn(); } }, txt);
    const ac = h('div', { class: 'mAc' }, bt('➕', 'Adicionar à fila', () => { fila.push(t); toast('Adicionada à fila'); if (vista.t === 'fila') renderMusica(); }),
      bt(tem(lib.curtidas, t.id) ? '💚' : '🤍', 'Curtir', () => { const j = lib.curtidas.findIndex(x => x.id === t.id); j >= 0 ? lib.curtidas.splice(j, 1) : lib.curtidas.unshift(t); salvaLib(); renderMusica(); }),
      bt('📁', 'Adicionar a uma playlist', () => { const n = Object.keys(lib.playlists); if (!n.length) { toast('Crie uma playlist primeiro (aba Playlists)'); return; } const e = prompt('Em qual playlist?\n' + n.join('\n'), n[0]); if (e && lib.playlists[e]) { if (!tem(lib.playlists[e], t.id)) lib.playlists[e].push(t); salvaLib(); toast('Adicionada a ' + e, 'ok'); } }),
      opc.remover && bt('✖', 'Remover daqui', () => opc.remover(i)));
    const tocar = () => tocarLista(lista, i);
    return h('div', { class: 'mCard mFaixa' + (fila[idx] && fila[idx].id === t.id ? ' atual' : ''), 'data-id': t.id, tabindex: 0, onclick: tocar, onkeydown: e => { if (e.key === 'Enter') tocar(); } },
      im, h('b', { class: 'mTit' }, t.titulo), h('span', null, t.canal + (t.duracao ? ' · ' + dur(t.duracao) : '') + (t.genero && opc.genero !== false ? ' · ' + t.genero : '')), ac);
  }));
}
function heroi(tit, sub, capa, cor, lista, voltar, extra) {
  const im = h('div', { class: 'mCapa grande', style: 'background:' + (capa ? `url("${capa}") center/cover` : `linear-gradient(135deg,${cor},#1a1d27)`) }, !capa ? tit.slice(0, 1).toUpperCase() : '');
  return h('div', { class: 'mHero' }, im, h('div', null, h('a', { onclick: voltar }, '‹ Voltar'), h('h2', null, tit), h('p', null, sub),
    h('div', { class: 'mBot' }, h('button', { class: 'btn', onclick: () => lista.length && tocarLista(lista, 0) }, '▶ Tocar tudo'), h('button', { class: 'btn sec', onclick: () => lista.length && tocarLista(embaralha(lista), 0) }, '🔀 Aleatório'), extra)));
}
function renderMusica() {
  if (atual !== 'musica') return; const P = $('#p-musica'); const rolagem = scrollY; P.textContent = '';
  const A = srv.artistas, G = srv.generos, t = vista.t, volta = k => () => irMusica(k);
  const art = n => cartao(n, A[n].length + ' música' + (A[n].length > 1 ? 's' : ''), capaDe(A[n]), corDe(n), true, () => irMusica('artista', n), () => tocarLista(A[n], 0));
  const gen = n => cartao(n, G[n].length + ' música' + (G[n].length > 1 ? 's' : ''), '', corDe(n), false, () => irMusica('genero', n), () => tocarLista(G[n], 0));
  const busca = h('input', { type: 'text', id: 'mBusca', placeholder: '🔍 Buscar músicas e artistas (no servidor e no YouTube) ou colar um link', value: vista.t === 'busca' ? vista.k : '', onkeydown: e => { if (e.key === 'Enter') buscaMusica(); } });
  P.append(cabecalho('Música', 'Toca neste aparelho. Tudo que você ouve fica guardado no servidor, por artista e gênero.'));
  P.append(h('div', { id: 'mTopo' }, busca, h('button', { class: 'btn', onclick: buscaMusica }, 'Buscar'), fila.length > 0 && h('button', { class: 'btn sec', title: 'Para a música e fecha o player', onclick: fecharPlayer }, '✕ Fechar player'), h('label', { class: 'rad' }, h('input', { type: 'checkbox', checked: RADIO, onchange: e => { RADIO = e.target.checked; try { localStorage.setItem('radio', RADIO ? '1' : '0'); } catch (x) {} } }), '📻 Continuar do mesmo gênero')));
  P.append(h('div', { id: 'mTabs' }, TABS.map(([k, n]) => h('a', { class: 'mTab' + ((t === k || (k === 'artistas' && t === 'artista') || (k === 'generos' && t === 'genero') || (k === 'playlists' && t === 'playlist')) ? ' on' : ''), tabindex: 0, onclick: () => irMusica(k) }, n)), h('span', { id: 'mGuardando', class: 'peq', style: 'margin-left:auto;color:var(--acc);white-space:nowrap' })));
  const C = h('div'); P.append(C);
  if (t === 'inicio') {
    if (!srv.total && !Object.keys(lib.playlists).length && !lib.curtidas.length) C.append(vazio('Sua biblioteca está vazia', 'Busque uma música lá em cima e toque nela: ela fica guardada aqui no servidor, organizada por gênero e artista.'));
    if (DESC) C.append(filaH('Descubra algo novo', DESC.estilos.slice(0, 12).map(cartaoMix), () => irMusica('descobrir')));
    if (srv.recentes.length) C.append(filaH('Adicionadas recentemente', srv.recentes.map((m, i) => cartao(m.titulo, m.canal, m.capa, corDe(m.canal), false, () => tocarLista(srv.recentes, i), () => tocarLista(srv.recentes, i)))));
    if (Object.keys(A).length) C.append(filaH('Artistas', Object.keys(A).slice(0, 24).map(art), () => irMusica('artistas')));
    if (Object.keys(G).length) C.append(filaH('Gêneros', Object.keys(G).map(gen), () => irMusica('generos')));
    if (Object.keys(lib.playlists).length) C.append(filaH('Suas playlists', Object.entries(lib.playlists).map(([n, l]) => cartao(n, l.length + ' músicas', capaDe(l), corDe(n), false, () => irMusica('playlist', n), () => l.length && tocarLista(l, 0))), () => irMusica('playlists')));
    if (lib.curtidas.length) C.append(filaH('Curtidas', lib.curtidas.slice(0, 24).map((m, i) => cartao(m.titulo, m.canal, m.capa, corDe(m.canal), false, () => tocarLista(lib.curtidas, i), () => tocarLista(lib.curtidas, i))), () => irMusica('curtidas')));
  } else if (t === 'descobrir') {
    const pedido = h('input', { type: 'text', id: 'mPedido', placeholder: 'Peça à Alicia: "algo pra animar a sexta", "rock dos anos 2000", "calma depois do trabalho"…', onkeydown: e => { if (e.key === 'Enter') recomendarMusica(e.target.value); } });
    const link = h('input', { type: 'text', id: 'mLinkPl', placeholder: 'Cole o link de uma playlist do YouTube', onkeydown: e => { if (e.key === 'Enter') abrirPlaylistYT(e.target.value); } });
    C.append(h('div', { class: 'box' }, h('h3', null, '✨ A Alicia recomenda'), h('p', { class: 'mut peq' }, 'Ela monta uma seleção pelo que você já ouve e curtiu, ou surpreende você.'),
      h('div', { class: 'lin' }, pedido, h('button', { class: 'btn', onclick: () => recomendarMusica(pedido.value) }, 'Recomendar pra mim'))));
    C.append(h('div', { class: 'box' }, h('h3', null, '📥 Importar playlist do YouTube'), h('p', { class: 'mut peq' }, 'As músicas aparecem aqui; você toca, salva como playlist ou guarda tudo no servidor.'),
      h('div', { class: 'lin' }, link, h('button', { class: 'btn sec', onclick: () => abrirPlaylistYT(link.value) }, 'Importar'))));
    if (DESC) {
      C.append(h('h3', { style: 'margin:18px 0 12px' }, 'Estilos'), grade(DESC.estilos.map(cartaoMix)), h('h3', { style: 'margin:22px 0 12px' }, 'Humor e atividades'), grade(DESC.humores.map(cartaoMix)));
    } else C.append(h('div', { class: 'skel' }));
  } else if (t === 'mix') {
    if (vista.carregando) C.append(h('div', { class: 'box' }, h('h3', null, '✨ ' + vista.titulo), h('p', { class: 'mut' }, 'A Alicia está escolhendo as músicas… Na primeira vez pode levar até 30 segundos.'), h('div', { class: 'skel' })));
    else if (vista.erro) C.append(vazio('Não consegui montar agora', 'Tente de novo em instantes.'));
    else {
      const l = vista.faixas || [];
      C.append(heroi('✨ ' + vista.titulo, l.length + ' música(s)', capaDe(l), corDe(vista.titulo), l, volta('descobrir'),
        [h('button', { class: 'btn sec', onclick: () => guardarNoServidor(l) }, '💾 Guardar no servidor'), h('button', { class: 'btn sec', onclick: () => salvarComoPlaylist(vista.titulo, l) }, '📁 Salvar como playlist')]), l.length ? faixas(l) : vazio('Nada encontrado'));
    }
  } else if (t === 'artistas') C.append(Object.keys(A).length ? grade(Object.keys(A).map(art)) : vazio('Nenhum artista ainda'));
  else if (t === 'artista') { const l = A[vista.k] || []; C.append(heroi(vista.k, l.length + ' música(s) no servidor', capaDe(l), corDe(vista.k), l, volta('artistas')), faixas(l)); }
  else if (t === 'generos') C.append(Object.keys(G).length ? grade(Object.keys(G).map(gen)) : vazio('Nenhum gênero ainda'));
  else if (t === 'genero') { const l = G[vista.k] || [], ars = [...new Set(l.map(x => x.canal))]; C.append(heroi(vista.k, l.length + ' música(s) · ' + ars.length + ' artista(s)', '', corDe(vista.k), l, volta('generos'))); if (ars.length > 1) C.append(filaH('Artistas deste gênero', ars.map(art))); C.append(faixas(l, { genero: false })); }
  else if (t === 'musicas') C.append(srv.musicas.length ? faixas(srv.musicas) : vazio('Nenhuma música guardada ainda'));
  else if (t === 'playlists') {
    const nova = cartao('Nova playlist', 'criar', '', '#475569', false, () => { const n = (prompt('Nome da playlist:') || '').trim().slice(0, 40); if (n && !lib.playlists[n]) { lib.playlists[n] = []; salvaLib(); irMusica('playlist', n); } }); nova.querySelector('.mCapa').textContent = '➕';
    C.append(grade([nova, ...Object.entries(lib.playlists).map(([n, l]) => cartao(n, l.length + ' músicas', capaDe(l), corDe(n), false, () => irMusica('playlist', n), () => l.length && tocarLista(l, 0)))]));
  } else if (t === 'playlist') {
    const l = lib.playlists[vista.k] || [];
    C.append(heroi('📁 ' + vista.k, l.length + ' música(s)', capaDe(l), corDe(vista.k), l, volta('playlists'), h('button', { class: 'btn sec', onclick: () => confirma('Apagar a playlist "' + vista.k + '"?', 'As músicas continuam no servidor.', 'Apagar', () => { delete lib.playlists[vista.k]; salvaLib(); irMusica('playlists'); }, true) }, '🗑 Apagar playlist')),
      l.length ? faixas(l, { remover: i => { l.splice(i, 1); salvaLib(); renderMusica(); } }) : vazio('Playlist vazia', 'Use o botão 📁 nas músicas para adicionar.'));
  } else if (t === 'curtidas') C.append(heroi('❤ Curtidas', lib.curtidas.length + ' música(s)', capaDe(lib.curtidas), '#db2777', lib.curtidas, volta('inicio')), lib.curtidas.length ? faixas(lib.curtidas, { remover: i => { lib.curtidas.splice(i, 1); salvaLib(); renderMusica(); } }) : vazio('Nenhuma curtida', 'Toque no 🤍 de uma música para curtir.'));
  else if (t === 'fila') C.append(h('h3', { style: 'margin-bottom:12px' }, 'Fila de reprodução'), fila.length ? faixas(fila) : vazio('A fila está vazia'));
  else if (t === 'busca') {
    const q = (vista.k || '').toLowerCase(), locais = srv.musicas.filter(m => (m.titulo + ' ' + m.canal).toLowerCase().includes(q));
    C.append(h('h3', { style: 'margin:6px 0 12px' }, 'No seu servidor'), locais.length ? faixas(locais) : h('p', { class: 'mut' }, 'Nada com esse nome na sua biblioteca.'),
      h('h3', { style: 'margin:22px 0 12px' }, 'No YouTube (toque para ouvir; a música fica guardada no servidor)'),
      vista.carregando ? h('div', { class: 'skel' }) : vista.erro ? h('p', { class: 'mut' }, 'Não consegui buscar agora. Tente de novo ou cole o link do vídeo.') : resultados.length ? faixas(resultados, { genero: false }) : h('p', { class: 'mut' }, 'Nada encontrado.'));
  }
  scrollTo(0, rolagem);
}
let DESC = null, GUARD = { ativo: false, total: 0, feitos: 0, falhas: 0 }, _pg = null;
function cartaoMix(e) {
  const c = cartao(e.nome, '', '', corDe(e.nome), false, () => abrirMix(e.id, e.nome), null);
  const capa = c.querySelector('.mCapa'); capa.textContent = e.emoji; capa.style.fontSize = '3.2rem';
  c.querySelector('span').remove(); return c;
}
async function abrirMix(id, nome) {
  vista = { t: 'mix', titulo: nome, carregando: true }; renderMusica();
  try { const r = await api('/api/musica/mix?id=' + encodeURIComponent(id)); vista = { t: 'mix', titulo: r.titulo, faixas: r.faixas }; } catch (e) { vista = { t: 'mix', titulo: nome, erro: true }; } renderMusica();
}
async function recomendarMusica(pedido) {
  vista = { t: 'mix', titulo: 'Seleção da Alicia para você', carregando: true }; renderMusica();
  try { const r = await post('/api/musica/recomendar', { pedido: pedido || '' }); vista = { t: 'mix', titulo: r.titulo, faixas: r.faixas }; } catch (e) { vista = { t: 'mix', titulo: 'Seleção da Alicia para você', erro: true }; } renderMusica();
}
async function abrirPlaylistYT(url) {
  url = (url || '').trim(); if (!/list=/.test(url)) { toast('Cole o link de uma playlist do YouTube (com list=).', 'erro'); return; }
  vista = { t: 'mix', titulo: 'Playlist do YouTube', carregando: true }; renderMusica();
  try { const r = await api('/api/musica/playlist?url=' + encodeURIComponent(url)); vista = { t: 'mix', titulo: r.titulo, faixas: r.faixas }; } catch (e) { vista = { t: 'mix', titulo: 'Playlist do YouTube', erro: true }; } renderMusica();
}
function salvarComoPlaylist(nome, l) {
  const n = (prompt('Nome da playlist:', nome.replace(/^✨\s*/, '')) || '').trim().slice(0, 40); if (!n) return;
  lib.playlists[n] = lib.playlists[n] || []; l.forEach(t => { if (!tem(lib.playlists[n], t.id)) lib.playlists[n].push(t); }); salvaLib(); toast('Playlist salva: ' + n, 'ok');
}
function pintaGuardando() { const e = $('#mGuardando'); if (e) e.textContent = GUARD.ativo ? `💾 Guardando ${GUARD.feitos + GUARD.falhas}/${GUARD.total}…` : ''; }
function pollGuardando() {
  if (_pg) return;
  _pg = setInterval(async () => {
    try {
      GUARD = await api('/api/musica/guardando'); pintaGuardando();
      if (!GUARD.ativo) { clearInterval(_pg); _pg = null; toast(`Pronto! ${GUARD.feitos} música(s) guardada(s)` + (GUARD.falhas ? ` (${GUARD.falhas} não deu)` : ''), 'ok'); await carregaSrv(); if (atual === 'musica' && !['mix', 'busca'].includes(vista.t)) renderMusica(); }
    } catch (e) {}
  }, 4000);
}
async function guardarNoServidor(l) {
  try {
    const r = await post('/api/musica/guardar', { ids: l.map(x => x.id) });
    toast(r.enfileiradas ? `Guardando ${r.enfileiradas} música(s) em segundo plano. Você pode continuar usando o painel.` : 'Todas essas músicas já estão guardadas.', 'ok');
    if (r.enfileiradas) { GUARD = { ativo: true, total: r.enfileiradas, feitos: 0, falhas: 0 }; pintaGuardando(); pollGuardando(); }
  } catch (e) {}
}
async function buscaMusica() {
  const q = ($('#mBusca').value || '').trim(); if (q.length < 2) return; if (/youtu/.test(q) && /list=/.test(q)) { abrirPlaylistYT(q); return; } vista = { t: 'busca', k: q, carregando: true }; renderMusica();
  try { resultados = await api('/api/musica/buscar?q=' + encodeURIComponent(q)); } catch (e) { resultados = []; vista.erro = true; } vista.carregando = false; renderMusica();
}
async function iniciaMusica() { try { lib = await api('/api/musica/biblioteca'); } catch (e) {} try { DESC = await api('/api/musica/descobrir'); } catch (e) {} await carregaSrv(); if (atual === 'musica') renderMusica(); }
ENTRAR.musica = async () => { await carregaSrv(); renderMusica(); };

/* ===================== RPG ===================== */
const RG = { sala: null, info: null, pers: 0, timer: null, v: null };
const mod_ = v => Math.floor((v - 10) / 2), sinal = n => (n >= 0 ? '+' : '') + n;
async function rpgSala(v) { RG.sala = v.codigo; RG.v = v; rpgMesa(); }
function rpgLobby() {
  const P = $('#p-rpg'); P.textContent = ''; const camp = h('select', null, RG.info.campanhas.map(c => h('option', { value: c.id }, c.titulo))), cod = h('input', { type: 'text', placeholder: 'Código da mesa', maxlength: 4, style: 'max-width:190px;text-transform:uppercase' });
  const resumo = h('p', { class: 'mut peq' }); const mostra = () => { resumo.textContent = RG.info.campanhas.find(c => c.id === camp.value).resumo; }; camp.onchange = mostra; mostra();
  const G = h('div', { class: 'pers' });
  const pinta = () => { G.textContent = ''; RG.info.personagens.forEach(p => G.append(h('div', { class: 'cartao' + (RG.pers === p.indice ? ' on' : ''), tabindex: 0, onclick: () => { RG.pers = p.indice; pinta(); } },
    h('h3', { style: 'margin:0' }, p.nome), h('p', { style: 'margin:2px 0 6px;flex:0' }, p.classe + ' ' + p.especie), h('span', { class: 'pill' }, 'PV ' + p.pv + ' · CA ' + p.ca), h('p', { class: 'peq', style: 'margin:8px 0 0;flex:0' }, p.historia)))); }; pinta();
  P.append(cabecalho('RPG', 'A Alicia é a mestra. Até 5 jogadores, pelo celular, PC ou TV.'));
  P.append(h('div', { class: 'box' }, h('h3', null, '1. Escolha seu personagem'), G));
  P.append(h('div', { class: 'box' }, h('h3', null, '2. Crie uma mesa ou entre numa'), h('div', { class: 'lin' }, camp, h('button', { class: 'btn', onclick: async () => { try { const r = await post('/api/rpg/sala', { campanha: camp.value }); rpgSala(await post('/api/rpg/entrar', { codigo: r.codigo, personagem: RG.pers })); } catch (e) {} } }, '🎲 Criar mesa')), resumo,
    h('div', { class: 'lin', style: 'margin-top:10px' }, cod, h('button', { class: 'btn sec', onclick: async () => { try { rpgSala(await post('/api/rpg/entrar', { codigo: cod.value.toUpperCase(), personagem: RG.pers })); } catch (e) {} } }, 'Entrar na mesa'))));
}
async function rpgAcao(u, b) { try { RG.v = await post('/api/rpg/sala/' + RG.sala + u, b); rpgPinta(); } catch (e) {} }
function rpgMesa() {
  const P = $('#p-rpg'); P.textContent = '';
  P.append(h('div', { class: 'pgh' }, h('div', null, h('h2', { id: 'rgTit' }), h('p', { id: 'rgSub' })), h('div', { class: 'lin' }, h('span', { class: 'pill ok' }, 'Mesa ', h('b', { id: 'rgCod' })),
    h('button', { class: 'btn sec', onclick: () => { navigator.clipboard && navigator.clipboard.writeText(RG.sala); toast('Código copiado: ' + RG.sala, 'ok'); } }, 'Copiar código'), h('button', { class: 'btn sec', onclick: () => { RG.sala = null; ENTRAR.rpg(); } }, 'Sair da mesa'))));
  const txt = h('input', { type: 'text', placeholder: 'O que você faz? (comece com // para conversar com a mesa sem a mestra)', onkeydown: e => { if (e.key === 'Enter') falar(); } });
  const falar = () => { const t = txt.value.trim(); if (t) { txt.value = ''; rpgAcao('/falar', { texto: t }); } };
  P.append(h('div', { class: 'rpg' },
    h('div', null, h('div', { class: 'rlog', id: 'rgLog' }), h('div', { class: 'box', style: 'margin-top:14px' }, h('div', { class: 'lin' }, txt, h('button', { class: 'btn', onclick: falar }, 'Falar')),
      h('p', { class: 'mut peq', style: 'margin:10px 0 6px' }, 'Dados (rolados pelo servidor, valem para todos):'), h('div', { class: 'dados' }, ['d4', 'd6', 'd8', 'd10', 'd12', 'd20'].map(d => h('button', { class: 'dado', onclick: () => rpgAcao('/dado', { expr: d }) }, d))),
      h('div', { class: 'lin', style: 'margin-top:12px', id: 'rgAcoes' }))),
    h('div', null, h('div', { id: 'rgGrupo' }))));
  rpgPinta();
}
function rpgPinta() {
  const v = RG.v; if (!v || !$('#rgLog')) return; $('#rgTit').textContent = v.campanha; $('#rgSub').textContent = 'Capítulo ' + v.capitulo + ' de ' + v.capitulos + (v.fim ? ' · FIM' : ''); $('#rgCod').textContent = v.codigo;
  const L = $('#rgLog'), fim = L.scrollTop + L.clientHeight >= L.scrollHeight - 30; L.textContent = '';
  v.log.forEach(l => L.append(h('div', { class: l.tipo === 'narracao' ? 'narracao' : l.tipo === 'dado' ? 'dado_' : l.tipo === 'sistema' ? 'sistema' : '' }, h('b', null, l.quem + ': '), l.texto))); if (fim) L.scrollTop = L.scrollHeight;
  const A = $('#rgAcoes'); A.textContent = '';
  if (v.combate) { A.append(h('span', { class: 'pill av' }, 'Vez de: ' + (v.combate.turno_de === EU.usuario ? 'você' : cap(v.combate.turno_de)))); v.combate.inimigos.filter(e => e.pv > 0).forEach(e => A.append(h('button', { class: 'btn', onclick: () => rpgAcao('/combate', { acao: 'atacar', alvo: e.id }) }, `⚔️ Atacar ${e.nome} (${e.pv}/${e.pv_max})`))); }
  else if (!v.fim) A.append(h('button', { class: 'btn sec', onclick: () => rpgAcao('/combate', { acao: 'iniciar' }) }, '⚔️ Iniciar combate'));
  if (v.dono === EU.usuario && !v.combate && !v.fim) A.append(h('button', { class: 'btn sec', onclick: () => rpgAcao('/combate', { acao: 'capitulo' }) }, '📖 Próximo capítulo'));
  const G = $('#rgGrupo'); G.textContent = '';
  Object.entries(v.jogadores).forEach(([u, j]) => { const f = j.ficha, pct = Math.max(0, Math.round(f.pv / f.pv_max * 100)), meu = u === EU.usuario;
    G.append(h('div', { class: 'ficha', style: meu ? 'box-shadow:inset 0 0 0 2px var(--acc)' : '' }, h('b', null, f.nome + (meu ? ' (você)' : '')), h('span', { class: 'mut peq' }, `${f.classe} ${f.especie} · nível ${f.nivel} · ${u}`),
      h('div', { class: 'bar pv ' + (pct < 30 ? 'perigo' : pct < 60 ? 'aviso' : '') }, h('b', { style: 'width:' + pct + '%' })), h('span', { class: 'peq' }, `PV ${f.pv}/${f.pv_max} · CA ${f.ca} · XP ${f.xp}`),
      meu && h('div', { class: 'peq mut', style: 'margin-top:6px' }, Object.entries(f.atributos).map(([k, x]) => k + ' ' + x + ' (' + sinal(mod_(x)) + ')').join(' · '), h('br'), 'Perícias: ' + f.pericias.join(', '), h('br'), 'Equipamento: ' + f.equipamento.join(', '), f.magias.length ? h('br') : '', f.magias.length ? 'Magias: ' + f.magias.join('; ') : ''))); });
}
ENTRAR.rpg = async () => {
  try { if (!RG.info) RG.info = await api('/api/rpg/info'); } catch (e) { return; }
  if (!RG.timer) RG.timer = setInterval(async () => { if (atual === 'rpg' && RG.sala && !document.hidden) { try { RG.v = await api('/api/rpg/sala/' + RG.sala); rpgPinta(); } catch (e) {} } }, 3000);
  if (RG.sala) { try { RG.v = await api('/api/rpg/sala/' + RG.sala); rpgMesa(); return; } catch (e) { RG.sala = null; } }
  rpgLobby();
};

