'use strict';
/* Parte 2: Alicia, Arquivos, Servidor, Registros, Configurações */

/* ===================== ALICIA ===================== */
const AL = { pers: 'normal', sem: false, voz: (() => { try { return localStorage.getItem('ali_voz') !== '0'; } catch (e) { return true; } })(), opcoes: null, msgs: [] };
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
function aliChave() { return `ali_${EU ? EU.usuario : ''}`; }
function aliAddMsg(quem, txt, dig) {
  const m = h('div', { class: 'msg ' + (quem === 'eu' ? 'eu' : 'al') + (dig ? ' dig' : '') }, txt, quem !== 'eu' && !dig && txt.length > 3 && h('button', { class: 'ouvir', title: 'Ouvir de novo', onclick: () => falar(txt, 'feliz') }, '🔊'));
  const L = $('#aliMsgs'); L.append(m); L.scrollTop = L.scrollHeight; return m;
}
/* Voz da Alicia: a voz neural feminina original (Francisca), gerada pelo servidor. Se não houver internet,
   usa a voz do navegador, sempre escolhendo uma voz FEMININA em português. */
let vozAtual = null;
function vozFeminina() {
  const vs = speechSynthesis.getVoices().filter(v => /pt[-_]BR/i.test(v.lang) || /portugu/i.test(v.name));
  return vs.find(v => /francisca|thalita|maria|helo[ií]sa|luciana|fernanda|vit[oó]ria|raquel|feminin|female|zira/i.test(v.name)) || vs.find(v => !/daniel|antonio|ant[oô]nio|felipe|male|masculin|ricardo|jorge/i.test(v.name)) || null;
}
let _vol0 = null;   // a música abaixa enquanto a Alicia fala e volta ao normal depois
function baixaMusica() { if (typeof aud !== 'undefined' && !aud.paused && _vol0 === null) { _vol0 = aud.volume; aud.volume = _vol0 * .3; } }
function voltaMusica() { if (_vol0 !== null) { aud.volume = _vol0; _vol0 = null; } }
function pararVoz() { if (vozAtual) { vozAtual.onended = vozAtual.onerror = null; vozAtual.pause(); vozAtual = null; } if ('speechSynthesis' in window) speechSynthesis.cancel(); voltaMusica(); }
async function falar(t, expr) {
  pararVoz();
  try {
    const r = await fetch('/api/alicia/voz', { method: 'POST', headers: J, body: JSON.stringify({ texto: t, expressao: expr || 'feliz' }) });
    if (!r.ok) throw new Error('voz');
    const a = new Audio(URL.createObjectURL(await r.blob())); vozAtual = a; a.onended = a.onerror = voltaMusica; baixaMusica(); await a.play(); return;
  } catch (e) {}
  if (!('speechSynthesis' in window)) return;
  const u = new SpeechSynthesisUtterance(t.replace(/\[[^\]]*\]/g, '')); u.lang = 'pt-BR'; const v = vozFeminina(); if (v) u.voice = v; u.pitch = 1.1; u.onend = u.onerror = voltaMusica; baixaMusica(); speechSynthesis.speak(u);
}
if ('speechSynthesis' in window) speechSynthesis.onvoiceschanged = () => {};
/* ----- Alicia e a música: ela entende pedidos como "toca Linkin Park", "pausa", "próxima", "aumenta o volume" ----- */
const semAcento = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
const PEDE_MUSICA = /^(oi |ei |ola )?(alicia[, ]*)?(por favor[, ]*|pode |poderia |voce pode |me )*(toca|toque|tocar|coloca|coloque|colocar|poe|bota|bote|quero ouvir|quero escutar|vou querer ouvir|ouvir|escutar|reproduz|reproduza|manda|mande)\b/;
const FALAS = {
  pausar: ['Pausado.', 'Prontinho, silêncio.', 'Parei a música.'], continuar: ['Voltando a tocar.', 'Pronto, continua de onde parou.', 'Play!'],
  proxima: ['Pulando para a próxima.', 'Outra, então.', 'Próxima!'], anterior: ['Voltando para a anterior.', 'Voltei uma música.'],
  mais: ['Aumentei o volume.', 'Mais alto, então.'], menos: ['Abaixei o volume.', 'Mais baixinho.']
};
const sorteia = l => l[Math.floor(Math.random() * l.length)];
function comandoMusica(t) {
  const n = semAcento(t).replace(/[!?.,]/g, ' ').replace(/\s+/g, ' ').trim(), a = n.replace(/^(oi |ei |ola )?alicia /, '');
  if (/\b(que musica e essa|o que esta tocando|qual musica esta tocando|que som e esse|qual e essa musica)\b/.test(a)) return 'info';
  if (/\b(aumenta|aumentar|sobe|subir)\b.*\b(volume|som)\b|\bmais alto\b|\bmusica mais alta\b/.test(a)) return 'mais';
  if (/\b(abaixa|abaixar|diminui|diminuir|baixa|baixar)\b.*\b(volume|som)\b|\bmais baixo\b|\bmais baixinho\b/.test(a)) return 'menos';
  if (/\b(musica anterior|volta a musica|voltar a musica|volta para a anterior|faixa anterior)\b/.test(a)) return 'anterior';
  if (/\b(proxima|pula|pular|passa a musica|passar a musica|troca a musica|trocar a musica|outra musica)\b/.test(a) && !PEDE_MUSICA.test(a)) return 'proxima';
  if (/^(pausa|pause|pausar|para|parar|pare|silencio|cala)( a| o)?( musica| som)?$|\b(pausa|pausar|pause) (a )?(musica|som)\b|\b(para|parar|pare) (a )?(musica|som)\b/.test(a)) return 'pausar';
  if (/^(continua|continuar|retoma|retomar|play|despausa)( a| o)?( musica| som)?$|\b(volta a tocar|continua a musica|retoma a musica)\b/.test(a)) return 'continuar';
  return null;
}
function executaComando(c) {
  if (c === 'info') { const t = fila[idx]; return t ? `Está tocando "${t.titulo}", de ${t.canal}.` : 'Não tem nada tocando agora. É só pedir: "toca Linkin Park".'; }
  if (!fila.length) return 'Não tem nada tocando agora. É só pedir: "toca Linkin Park".';
  if (c === 'pausar') aud.pause(); else if (c === 'continuar') aud.play().catch(() => {}); else if (c === 'proxima') proxima(); else if (c === 'anterior') anterior();
  else if (c === 'mais') { aud.volume = Math.min(1, aud.volume + .2); $('#bVolR').value = Math.round(aud.volume * 100); }
  else if (c === 'menos') { aud.volume = Math.max(0, aud.volume - .2); $('#bVolR').value = Math.round(aud.volume * 100); }
  return sorteia(FALAS[c]);
}
function aliCartaoMusica(t, faixas) {
  const L = $('#aliMsgs'); L.append(h('div', { class: 'msgMus', tabindex: 0, onclick: () => tocarLista(faixas, 0), title: 'Tocar de novo' },
    h('img', { src: t.capa, alt: '' }), h('div', null, h('b', null, t.titulo), h('span', null, t.canal + (faixas.length > 1 ? ' · e mais ' + (faixas.length - 1) + ' na fila' : ''))), h('span', { class: 'pl' }, '▶'))); L.scrollTop = L.scrollHeight;
}
async function aliEnviar(txt) {
  txt = (txt || '').trim(); if (!txt) return; $('#aliIn').value = '';
  aliAddMsg('eu', txt);
  const cmd = comandoMusica(txt);                               // pausa, próxima, volume...: resolve na hora, sem gastar a IA
  if (cmd) { const fala = executaComando(cmd); aliAddMsg('al', fala); if (AL.voz) falar(fala, 'feliz'); return; }
  const dig = aliAddMsg('al', '', true); $('#aliImg').src = '/api/alicia/imagem/pensando';
  if (/\b(toca|toque|tocar|ponha|coloca|coloque|colocar|poe|bota|bote|botar|ouvir|escutar|reproduz\w*|manda|mande)\b/.test(semAcento(txt))) {                       // "toca X": a Alicia acha a música, coloca para tocar e responde no jeito dela
    try {
      const r = await post('/api/alicia/musica', { texto: txt, so_achar: true });          // 1ª etapa: acha e já começa a tocar
      if (!r.nao_e_musica) {
        dig.remove(); const bolha = aliAddMsg('al', r.texto); $('#aliImg').src = '/api/alicia/imagem/' + (r.expressao || 'feliz');
        if (r.faixas && r.faixas.length) { aliCartaoMusica(r.faixas[0], r.faixas); tocarLista(r.faixas, 0); }
        AL.msgs.push(['eu', txt], ['al', r.texto]); try { localStorage.setItem(aliChave(), JSON.stringify(AL.msgs.slice(-40))); } catch (e) {}
        if (r.faixas && r.faixas.length) {                                                // 2ª etapa: a Alicia comenta no jeito dela (demora um pouco)
          post('/api/alicia/musica', { texto: txt, so_resposta: true, faixa: r.faixas[0], personalidade: AL.pers, sem_filtro: AL.sem }).then(c => {
            bolha.firstChild.textContent = c.texto; $('#aliImg').src = '/api/alicia/imagem/' + (c.expressao || 'feliz'); AL.msgs[AL.msgs.length - 1][1] = c.texto;
            if (AL.voz) falar(c.texto, c.expressao);
          }).catch(() => { if (AL.voz) falar(r.texto, r.expressao); });
        } else if (AL.voz) falar(r.texto, r.expressao);
        return;
      }
    } catch (e) { dig.remove(); aliAddMsg('al', 'Não consegui colocar a música agora. Tente de novo.'); $('#aliImg').src = '/api/alicia/imagem/serio'; return; }
  }
  try {
    const r = await post('/api/alicia/conversar', { texto: txt, personalidade: AL.pers, sem_filtro: AL.sem });
    dig.remove(); aliAddMsg('al', r.texto); $('#aliImg').src = '/api/alicia/imagem/' + (r.expressao || 'feliz');
    AL.msgs.push(['eu', txt], ['al', r.texto]); try { localStorage.setItem(aliChave(), JSON.stringify(AL.msgs.slice(-40))); } catch (e) {}
    if (AL.voz && !r.erro && !r.sem_chave) falar(r.texto, r.expressao);
  } catch (e) { dig.remove(); aliAddMsg('al', 'Não consegui falar agora. Tente de novo em instantes.'); $('#aliImg').src = '/api/alicia/imagem/serio'; }
}
ENTRAR._aliEstado = () => {
  const e = $('#aliEst'); if (!e || !S) return; const ok = ligado('Alicia') && S.chave_nvidia;
  e.className = 'pill ' + (ok ? 'ok' : 'av'); e.textContent = ok ? 'Pronta para conversar' : !S.chave_nvidia ? 'Sem cérebro (falta a chave)' : 'Iniciando…';
  const av = $('#aliAviso'); if (av) av.style.display = S.chave_nvidia ? 'none' : 'block';
};
ENTRAR.alicia = async () => {
  const P = $('#p-alicia'); P.textContent = '';
  if (!AL.opcoes) { try { AL.opcoes = (await api('/api/alicia/opcoes')).personalidades; } catch (e) { AL.opcoes = []; } }
  try { AL.msgs = JSON.parse(localStorage.getItem(aliChave()) || '[]'); } catch (e) { AL.msgs = []; }
  P.append(cabecalho('Alicia', 'Converse por texto ou voz. Ela lembra das conversas.'));
  P.append(h('div', { class: 'box', id: 'aliAviso', style: 'display:none;border-left:5px solid var(--warn)' }, h('b', null, 'A Alicia ainda não tem cérebro. '), 'Coloque a chave da NVIDIA em Configurações.', h('div', null, h('button', { class: 'btn', onclick: () => ir('config') }, 'Ir para Configurações'))));
  const chips = h('div', { class: 'chips' }); const pintaChips = () => { chips.textContent = ''; AL.opcoes.forEach(o => chips.append(h('span', { class: 'chip' + (AL.pers === o.id ? ' on' : ''), tabindex: 0, title: o.desc, onclick: () => { AL.pers = o.id; pintaChips(); toast('Jeito da Alicia: ' + o.nome); } }, o.nome))); }; pintaChips();
  const mic = h('button', { class: 'btn-ic', title: SR ? 'Falar com a Alicia' : 'Seu navegador não tem reconhecimento de voz', disabled: !SR, onclick: () => {
    const r = new SR(); r.lang = 'pt-BR'; r.interimResults = false; mic.textContent = '🔴';
    r.onresult = ev => aliEnviar(ev.results[0][0].transcript); r.onend = () => mic.textContent = '🎤'; r.onerror = () => { mic.textContent = '🎤'; toast('Não consegui ouvir. Veja a permissão do microfone.', 'erro'); }; r.start(); } }, '🎤');
  const rapidas = ['O que você sabe fazer?', 'Analise o servidor', 'Toca uma música pra mim', 'Me conte uma curiosidade'];
  P.append(h('div', { class: 'alic' },
    h('div', { class: 'box perfil' }, h('img', { class: 'av', id: 'aliImg', src: '/api/alicia/imagem/feliz', alt: 'Alicia' }), h('h3', null, 'Alicia'), h('span', { class: 'pill', id: 'aliEst' }),
      h('p', { class: 'mut peq' }, 'Jeito dela:'), chips,
      h('label', { class: 'rad', style: 'justify-content:center' }, h('input', { type: 'checkbox', checked: AL.sem, onchange: e => { AL.sem = e.target.checked; toast(AL.sem ? 'Modo sem filtro ligado' : 'Modo sem filtro desligado'); } }), '🔥 Modo sem filtro'),
      h('label', { class: 'rad', style: 'justify-content:center;margin-top:6px' }, h('input', { type: 'checkbox', checked: AL.voz, onchange: e => { AL.voz = e.target.checked; try { localStorage.setItem('ali_voz', AL.voz ? '1' : '0'); } catch (x) {} if (!AL.voz) pararVoz(); else falar('Pronto, agora eu falo com você.', 'feliz'); } }), '🔊 Falar as respostas em voz alta')),
    h('div', { class: 'box chat' }, h('div', { class: 'msgs', id: 'aliMsgs' }),
      h('div', { class: 'chips', style: 'justify-content:flex-start' }, rapidas.map(t => h('span', { class: 'chip', tabindex: 0, onclick: () => aliEnviar(t) }, t))),
      h('div', { class: 'envio' }, h('input', { type: 'text', id: 'aliIn', placeholder: 'Escreva para a Alicia e tecle Enter', onkeydown: e => { if (e.key === 'Enter') aliEnviar(e.target.value); } }), mic, h('button', { class: 'btn', onclick: () => aliEnviar($('#aliIn').value) }, 'Enviar')))));
  if (AL.msgs.length) AL.msgs.forEach(([q, t]) => aliAddMsg(q, t)); else aliAddMsg('al', 'Oi! Eu sou a Alicia. Pode falar comigo, pedir ajuda com o servidor ou só bater papo.');
  ENTRAR._aliEstado();
};

/* ===================== ARQUIVOS ===================== */
let ARQ = { caminho: '' };
const iconeArq = (n, pasta) => pasta ? '📁' : /\.(png|jpe?g|gif|webp|bmp)$/i.test(n) ? '🖼️' : /\.(mp4|mkv|avi|mov|webm|m4v)$/i.test(n) ? '🎞️' : /\.(mp3|m4a|flac|wav|ogg|opus)$/i.test(n) ? '🎵' : /\.pdf$/i.test(n) ? '📕' : /\.(zip|rar|7z)$/i.test(n) ? '🗜️' : /\.(docx?|odt|txt|md)$/i.test(n) ? '📄' : /\.(xlsx?|csv)$/i.test(n) ? '📊' : '📄';
const urlArq = (c, extra) => '/api/arquivos/baixar?caminho=' + encodeURIComponent(c) + (extra || '');
function previa(c, nome) {
  let el;
  if (/\.(png|jpe?g|gif|webp|bmp)$/i.test(nome)) el = h('img', { class: 'pv', src: urlArq(c) });
  else if (/\.(mp4|webm|m4v|mov)$/i.test(nome)) el = h('video', { class: 'pv', src: urlArq(c), controls: true, autoplay: true });
  else if (/\.(mp3|m4a|flac|wav|ogg|opus)$/i.test(nome)) el = h('audio', { src: urlArq(c), controls: true, autoplay: true, style: 'width:100%' });
  else if (/\.pdf$/i.test(nome)) el = h('iframe', { class: 'pv', src: urlArq(c) });
  else if (/\.(txt|md|json|log|csv|ini|py|js|html|css)$/i.test(nome)) { el = h('pre', { style: 'white-space:pre-wrap;max-height:70vh;overflow:auto;margin:0' }, 'Carregando…'); fetch(urlArq(c, '&silencio=1')).then(r => r.text()).then(t => el.textContent = t.slice(0, 200000)); }
  else { window.open(urlArq(c, '&baixar=1')); return; }
  modal(h('div', null, h('div', { class: 'lin', style: 'justify-content:space-between;margin-bottom:12px' }, h('h3', null, nome), h('div', null, h('a', { class: 'btn sec peq', href: urlArq(c, '&baixar=1') }, '⬇ Baixar'), ' ', h('button', { class: 'btn sec peq', onclick: fechaModal }, 'Fechar'))), el), true);
}
async function arqListar(c) {
  ARQ.caminho = c; const P = $('#arqLista'); P.textContent = '';
  const partes = c ? c.split('/') : []; const mig = h('div', { class: 'mig' }, h('a', { onclick: () => arqListar('') }, '🏠 Início'));
  partes.forEach((p, i) => { mig.append(' › ', i === partes.length - 1 ? h('b', null, p) : h('a', { onclick: () => arqListar(partes.slice(0, i + 1).join('/')) }, p)); });
  $('#arqMig').textContent = ''; $('#arqMig').append(mig);
  let d; try { d = await api('/api/arquivos?caminho=' + encodeURIComponent(c)); } catch (e) { return; }
  const itens = d.itens.filter(i => !i.nome.startsWith('.'));
  if (!itens.length) { P.append(vazio('Pasta vazia', 'Arraste arquivos para cá ou use o botão Enviar.')); return; }
  const G = h('div', { class: 'arqs' });
  itens.forEach(i => {
    const p = (c ? c + '/' : '') + i.nome; const img = !i.pasta && /\.(png|jpe?g|gif|webp)$/i.test(i.nome);
    const th = h('div', { class: 'th' }, img ? h('img', { src: urlArq(p, '&silencio=1'), loading: 'lazy', alt: '' }) : iconeArq(i.nome, i.pasta));
    const ac = h('div', { class: 'ac' },
      !i.pasta && h('button', { title: 'Baixar', onclick: e => { e.stopPropagation(); location.href = urlArq(p, '&baixar=1'); } }, '⬇'),
      h('button', { title: 'Apagar', onclick: e => { e.stopPropagation(); confirma('Apagar "' + i.nome + '"?', 'Ele vai para a lixeira do servidor (não some de vez).', 'Apagar', async () => { await api('/api/arquivos?caminho=' + encodeURIComponent(p), { method: 'DELETE' }); toast('Apagado.', 'ok'); arqListar(c); }, true); } }, '🗑'));
    G.append(h('div', { class: 'arq', tabindex: 0, onclick: () => i.pasta ? arqListar(p) : previa(p, i.nome), onkeydown: e => { if (e.key === 'Enter') e.target.click(); } }, th, h('b', null, i.nome), h('span', null, i.pasta ? 'Pasta' : fmtB(i.tamanho)), ac));
  });
  P.append(G);
}
async function arqEnviar(arqs) {
  if (!arqs.length) return; const st = $('#arqSt'); let ok = 0;
  for (let n = 0; n < arqs.length; n++) {
    const f = arqs[n];
    try { await enviarArquivo('/api/arquivos/enviar?caminho=' + encodeURIComponent(ARQ.caminho), f, p => st.textContent = `Enviando ${f.name} (${n + 1} de ${arqs.length})… ${Math.round(p * 100)}%`); ok++; } catch (e) {}
  }
  st.textContent = ok ? ok + ' arquivo(s) enviado(s) ✓' : ''; if (ok) { toast('Arquivos enviados!', 'ok'); arqListar(ARQ.caminho); }
}
ENTRAR.arquivos = () => {
  const P = $('#p-arquivos'); P.textContent = '';
  const inp = h('input', { type: 'file', multiple: true, style: 'display:none', onchange: e => { arqEnviar([...e.target.files]); e.target.value = ''; } });
  P.append(cabecalho('Arquivos', 'Tudo que está guardado no servidor. Arraste arquivos para qualquer lugar da página para enviar.',
    h('button', { class: 'btn sec', onclick: () => { const n = prompt('Nome da nova pasta:'); if (n) post('/api/arquivos/pasta', { caminho: ARQ.caminho, nome: n }).then(() => arqListar(ARQ.caminho)); } }, '📁 Nova pasta'),
    h('button', { class: 'btn', onclick: () => inp.click() }, '⬆ Enviar'), inp));
  P.append(h('div', { id: 'arqMig' }), h('p', { class: 'mut peq', id: 'arqSt' }), h('div', { id: 'arqLista' }));
  zonaEnvio(P, arqEnviar); arqListar(ARQ.caminho);
};

/* ===================== SERVIDOR ===================== */
function pintaServidor() {
  if (!S || !$('#svCpu')) return;
  spark($('#svCpu'), hist.cpu, 100); spark($('#svRam'), hist.ram, 100);
  spark($('#svRx'), hist.rx, Math.max(50000, ...hist.rx, ...hist.tx), '#4ade80'); spark($('#svTx'), hist.tx, Math.max(50000, ...hist.rx, ...hist.tx), '#fbbf24');
  $('#svCpuV').textContent = S.cpu + '%'; $('#svRamV').textContent = S.ram + '%'; $('#svDisV').textContent = S.disco + '%'; $('#svDisB').style.width = S.disco + '%';
  $('#svDisT').textContent = S.disco_livre_gb + ' GB livres';
  $('#svRxV').textContent = fmtB(hist.rx[hist.rx.length - 1] || 0) + '/s ↓'; $('#svTxV').textContent = fmtB(hist.tx[hist.tx.length - 1] || 0) + '/s ↑';
  $('#svTemp').textContent = S.temperatura == null ? 'indisponível neste Windows' : S.temperatura + ' °C'; $('#svUp').textContent = S.ligado_ha_h >= 48 ? Math.round(S.ligado_ha_h / 24) + ' dias' : S.ligado_ha_h + ' horas';
  const T = $('#svServ'); T.textContent = '';
  S.servicos.forEach(s => T.append(h('tr', null, h('td', null, s.nome), h('td', null, h('span', { class: 'pill ' + (s.estado === 'ligado' ? 'ok' : s.estado === 'parado' ? 'er' : 'av') }, s.estado === 'ligado' ? 'Ligado' : s.estado === 'parado' ? 'Parado' : 'Em breve')),
    h('td', { style: 'text-align:right' }, EU.admin && s.nome.startsWith('Alicia') ? h('button', { class: 'btn sec peq', onclick: () => confirma('Reiniciar a Alicia/Hermes?', 'A conversa fica indisponível por cerca de 1 minuto.', 'Reiniciar', async () => { await post('/api/hermes/reiniciar'); toast('Reiniciando… volta em cerca de 1 minuto.', 'ok'); }) }, '↻ Reiniciar') : ''))));
}
ENTRAR._pintaServidor = pintaServidor;
ENTRAR.servidor = async () => {
  const P = $('#p-servidor'); P.textContent = '';
  const tile = (nome, idv, idc) => h('div', { class: 'est' }, h('div', { class: 'n' }, nome), h('div', { class: 'v', id: idv }, '…'), h('canvas', { class: 'spark', id: idc }));
  P.append(cabecalho('Servidor', 'Saúde do notebook em tempo real.', h('button', { class: 'btn sec', onclick: () => ir('registros') }, '📜 Ver registros')));
  P.append(h('div', { class: 'resumo', style: 'margin-bottom:18px' }, tile('Processador', 'svCpuV', 'svCpu'), tile('Memória', 'svRamV', 'svRam'), tile('Rede: recebendo', 'svRxV', 'svRx'), tile('Rede: enviando', 'svTxV', 'svTx'),
    h('div', { class: 'est' }, h('div', { class: 'n' }, 'Disco', h('span', { id: 'svDisT' })), h('div', { class: 'v', id: 'svDisV' }), h('div', { class: 'bar' }, h('b', { id: 'svDisB' }))),
    h('div', { class: 'est' }, h('div', { class: 'n' }, 'Temperatura'), h('div', { class: 'v', id: 'svTemp', style: 'font-size:17px' }), h('div', { class: 'n' }, 'Ligado há ', h('span', { id: 'svUp' })))));
  P.append(h('div', { class: 'box' }, h('h3', { style: 'margin-bottom:10px' }, 'Serviços'), h('table', { class: 'tbl' }, h('thead', null, h('tr', null, h('th', null, 'Serviço'), h('th', null, 'Estado'), h('th'))), h('tbody', { id: 'svServ' }))));
  const hm = h('div', { class: 'box' }, h('h3', null, 'Hermes (o cérebro da Alicia)'), h('p', { class: 'mut peq' }, 'Skills que ele aprendeu e tarefas agendadas.'), h('div', { id: 'hmInfo' }, 'Carregando…'));
  P.append(hm); pintaServidor();
  try {
    const d = await api('/api/hermes/info'); const box = $('#hmInfo'); if (!box) return; box.textContent = '';
    const lista = (t, l, vz) => h('div', { style: 'margin-bottom:10px' }, h('b', null, t), h('div', null, l.length ? l.map(x => h('span', { class: 'tag' }, x)) : h('span', { class: 'mut peq' }, vz)));
    box.append(lista('Skills (' + d.skills.length + ')', d.skills, 'Nenhuma ainda: ele cria skills conforme você usa.'), lista('Tarefas agendadas (' + d.tarefas.length + ')', d.tarefas, 'Nenhuma. Peça à Alicia: "me lembre todo dia às 9h de…".'));
  } catch (e) { const b = $('#hmInfo'); if (b) b.textContent = 'O Hermes não respondeu agora.'; }
};

/* ===================== REGISTROS ===================== */
const LG = { linhas: [], filtro: 'todos', serv: '', texto: '', pausa: false, es: null };
function lgPassa(l) {
  if (LG.filtro === 'seguranca' && l.tipo !== 'seguranca') return false; if (LG.filtro === 'erros' && !['erro', 'seguranca'].includes(l.tipo)) return false; if (LG.filtro === 'avisos' && l.tipo !== 'aviso') return false;
  if (LG.serv && l.servico !== LG.serv) return false; if (LG.texto && !(`${l.servico} ${l.quem} ${l.ip} ${l.o_que} ${l.resultado}`).toLowerCase().includes(LG.texto)) return false; return true;
}
const lgLinha = l => h('div', { class: l.tipo }, l.t + '  ', h('span', { class: 'sv' }, l.servico), `${l.quem} (${l.ip})  ${l.o_que}  → ${l.resultado}`);
function lgPinta() {
  const C = $('#lgBox'); if (!C) return; C.textContent = ''; const v = LG.linhas.filter(lgPassa).slice(-400);
  if (!v.length) C.append(h('div', { class: 'info' }, 'Nenhum registro com esses filtros.')); else v.forEach(l => C.append(lgLinha(l))); C.scrollTop = C.scrollHeight;
}
ENTRAR.registros = async () => {
  const P = $('#p-registros'); P.textContent = '';
  const chip = (id, n) => h('span', { class: 'chip' + (LG.filtro === id ? ' on' : ''), tabindex: 0, onclick: () => { LG.filtro = id; ENTRAR.registros(); } }, n);
  const servs = ['', 'PAINEL', 'LOGIN', 'ARQUIVOS', 'ALICIA', 'NVIDIA', 'JELLYFIN', 'JOGOS', 'MÚSICA', 'RPG', 'SEGURANÇA', 'SISTEMA'];
  P.append(cabecalho('Registros', 'Quem acessou o quê, ao vivo. Fica guardado por 30 dias. Nunca aparecem senhas, chaves nem conteúdo de conversas.',
    h('button', { class: 'btn sec', id: 'lgPausa', onclick: e => { LG.pausa = !LG.pausa; e.target.textContent = LG.pausa ? '▶ Continuar' : '⏸ Pausar'; } }, LG.pausa ? '▶ Continuar' : '⏸ Pausar')));
  P.append(h('div', { class: 'lin', style: 'margin-bottom:12px' }, chip('todos', 'Tudo'), chip('seguranca', '🛡️ Segurança'), chip('erros', 'Erros'), chip('avisos', 'Avisos'),
    h('select', { onchange: e => { LG.serv = e.target.value; lgPinta(); } }, servs.map(s => h('option', { value: s, selected: s === LG.serv }, s || 'Todos os serviços'))),
    h('input', { type: 'text', placeholder: 'Filtrar por texto…', value: LG.texto, oninput: e => { LG.texto = e.target.value.toLowerCase(); lgPinta(); } })));
  P.append(h('div', { class: 'log', id: 'lgBox' }, 'Carregando…'));
  try { LG.linhas = await api('/api/logs?n=600'); } catch (e) { LG.linhas = []; } lgPinta();
  if (!LG.es) { LG.es = new EventSource('/api/logs/ao-vivo'); LG.es.onmessage = ev => { try { const l = JSON.parse(ev.data); LG.linhas.push(l); if (LG.linhas.length > 1500) LG.linhas.shift(); if (atual === 'registros' && !LG.pausa && lgPassa(l)) { const C = $('#lgBox'); if (C) { C.append(lgLinha(l)); while (C.children.length > 600) C.firstChild.remove(); C.scrollTop = C.scrollHeight; } } } catch (e) {} }; }
};

/* ===================== CONFIGURAÇÕES ===================== */
async function cfgNvidia(box) {
  let masc = ''; try { masc = (await api('/api/nvidia')).mascarada; } catch (e) {}
  const res = h('p'), campo = h('input', { type: 'password', placeholder: 'Cole a chave aqui (começa com nvapi-)', autocomplete: 'off' });
  box.append(h('h3', null, '🔑 Chave da NVIDIA'), h('p', { class: 'mut peq' }, 'É o “cérebro” da Alicia e do RPG. Chave atual: ', h('b', null, masc || 'nenhuma')), h('div', { class: 'lin' }, campo,
    h('button', { class: 'btn sec', onclick: async () => { res.textContent = 'Testando…'; try { const d = await post('/api/nvidia/testar', { chave: campo.value }); res.textContent = (d.estado === 'ok' ? '✓ ' : '✗ ') + d.mensagem; res.style.color = d.estado === 'ok' ? 'var(--ok)' : 'var(--err)'; } catch (e) { res.textContent = ''; } } }, 'Testar chave'),
    h('button', { class: 'btn', onclick: async () => { try { await post('/api/nvidia/salvar', { chave: campo.value }); toast('Chave salva. A Alicia reinicia em cerca de 1 minuto.', 'ok'); campo.value = ''; ENTRAR.config(); } catch (e) {} } }, 'Salvar')), res);
}
async function cfgUsuarios(box) {
  box.append(h('h3', null, '👥 Usuários e senhas'));
  const lista = h('div'), nome = h('input', { type: 'text', placeholder: 'Nome do usuário' }), sen = h('input', { type: 'password', placeholder: 'Senha (mín. 6)' }), adm = h('input', { type: 'checkbox' });
  const pinta = async () => { lista.textContent = ''; const us = await api('/api/usuarios');
    us.forEach(u => lista.append(h('div', { class: 'lin', style: 'justify-content:space-between;padding:6px 0' }, h('span', null, '👤 ' + u.usuario + (u.admin ? ' (administrador)' : '')),
      u.usuario !== EU.usuario && h('button', { class: 'btn sec peq', onclick: () => confirma('Apagar o usuário ' + u.usuario + '?', 'Ele não poderá mais entrar.', 'Apagar', async () => { await api('/api/usuarios?nome=' + encodeURIComponent(u.usuario), { method: 'DELETE' }); pinta(); }, true) }, 'Apagar')))); };
  box.append(lista, h('div', { class: 'lin', style: 'margin-top:8px' }, nome, sen, h('label', { class: 'rad' }, adm, 'Administrador'),
    h('button', { class: 'btn', onclick: async () => { try { await post('/api/usuarios', { usuario: nome.value, senha: sen.value, admin: adm.checked }); toast('Usuário salvo.', 'ok'); nome.value = sen.value = ''; pinta(); } catch (e) {} } }, 'Criar')));
  pinta();
}
ENTRAR.config = async () => {
  const P = $('#p-config'); P.textContent = '';
  P.append(cabecalho('Configurações', 'Chave, usuários, aparência e endereços do servidor.'));
  const b1 = h('div', { class: 'box' }); P.append(b1); await cfgNvidia(b1);
  const ver = h('div'); P.append(h('div', { class: 'box' }, h('h3', null, '✅ Verificar tudo'), h('p', { class: 'mut peq' }, 'Testa cada recurso de verdade e diz o que fazer se algo falhar.'),
    h('button', { class: 'btn', onclick: async e => { e.target.disabled = true; ver.textContent = 'Testando… (pode levar um minuto)'; try { const r = await post('/api/verificar'); ver.textContent = ''; r.forEach(x => ver.append(h('div', { style: 'color:' + (x.ok ? 'var(--ok)' : 'var(--err)') }, (x.ok ? '✓ ' : '✗ ') + x.nome + (x.ok ? '' : ' — ' + x.dica)))); } catch (er) { ver.textContent = 'Não consegui rodar a verificação.'; } e.target.disabled = false; } }, 'Verificar tudo'), ver));
  if (EU.admin) {
    const b = h('div', { class: 'box' }); P.append(b); cfgUsuarios(b);
    P.append(h('div', { class: 'box' }, h('h3', null, '👤 Entrada de visitante'), h('p', { class: 'mut peq' }, 'Quem clicar em "Entrar como visitante" na tela de entrada usa Jogos, Música, Filmes e RPG, sem senha. Não vê arquivos, registros, configurações nem a Alicia. Só funciona na rede de casa e na rede privada (Tailscale).'),
      h('label', { class: 'rad' }, h('input', { type: 'checkbox', checked: EU.visitante_ativo !== false, onchange: async e => { try { const d = await post('/api/visitante/config', { ativo: e.target.checked }); EU.visitante_ativo = d.visitante; toast(d.visitante ? 'Visitantes liberados.' : 'Entrada de visitante desligada.', 'ok'); } catch (x) { e.target.checked = !e.target.checked; } } }), 'Permitir entrada como visitante')));
  }
  const at = h('input', { type: 'password', placeholder: 'Senha atual' }), nv = h('input', { type: 'password', placeholder: 'Senha nova (mín. 6)' });
  P.append(h('div', { class: 'box' }, h('h3', null, '🔒 Minha senha'), h('div', { class: 'lin' }, at, nv, h('button', { class: 'btn', onclick: async () => { try { await post('/api/senha', { atual: at.value, nova: nv.value }); toast('Senha trocada.', 'ok'); at.value = nv.value = ''; } catch (e) {} } }, 'Trocar'))));
  const cor = c => h('span', { class: 'chip' + ((document.documentElement.dataset.cor || 'roxo') === c ? ' on' : ''), tabindex: 0, onclick: () => { setCor(c); ENTRAR.config(); } }, c === 'roxo' ? '🟣 Roxo' : c === 'rosa' ? '🌸 Rosa' : '🩵 Verde-água');
  P.append(h('div', { class: 'box' }, h('h3', null, '🎨 Aparência'), h('div', { class: 'chips', style: 'justify-content:flex-start' }, cor('roxo'), cor('rosa'), cor('verde')),
    h('div', { class: 'lin' }, h('label', { class: 'rad' }, h('input', { type: 'checkbox', checked: document.body.classList.contains('tv'), onchange: e => setTV(e.target.checked) }), '📺 Modo TV (letras grandes; setas e OK do controle)'), h('button', { class: 'btn sec peq', onclick: () => tour(0) }, '❓ Rever o tour'))));
  const en = (S && S.enderecos) || {}; const link = (n, u) => h('div', { class: 'lin', style: 'padding:4px 0' }, h('b', { style: 'min-width:170px' }, n), h('a', { href: u, target: '_blank' }, u), h('button', { class: 'btn sec peq', onclick: () => { navigator.clipboard && navigator.clipboard.writeText(u); toast('Endereço copiado.', 'ok'); } }, 'Copiar'));
  P.append(h('div', { class: 'box' }, h('h3', null, '🌐 Endereços do servidor'), h('p', { class: 'mut peq' }, 'Em casa use o primeiro; fora de casa, o da rede privada (precisa do app Tailscale ligado).'),
    en.casa && link('Na rede de casa', en.casa), en.tailscale ? link('De qualquer lugar (Tailscale)', en.tailscale) : h('p', { class: 'mut peq' }, 'Rede privada ainda não conectada neste servidor.'),
    h('p', { class: 'mut peq' }, 'Jellyfin (filmes): mesmo endereço, porta 8096. Pasta compartilhada: \\\\' + (en.casa ? en.casa.replace('http://', '').replace(':8080', '') : 'servidor') + '\\AliciaServer')));
};
