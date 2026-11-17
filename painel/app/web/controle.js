/* Alicia Server — controles (gamepad) para os jogos.
   Substitui a leitura de controle do EmulatorJS, que supõe um layout fixo e erra em vários controles
   (botões trocados, direcional que vira "eixo", jogador errado). Aqui:
   - controles "padrão" (Xbox, PlayStation, Switch Pro, 8BitDo…) usam o mapa POSICIONAL do RetroArch:
     botão de baixo = B, da direita = A, da esquerda = Y, de cima = X (assim "pular" fica onde se espera);
   - controles fora do padrão (genéricos de USB) pedem uma configuração rápida, guiada, e ela fica salva por modelo;
   - o direcional pode vir como botões, como eixo ou como "hat"; o analógico esquerdo também funciona como direcional;
   - cada controle ligado vira um jogador (1, 2, 3…), na ordem em que foi usado;
   - botão "🎮 Controle" mostra os controles, testa os botões ao vivo e refaz a configuração.
   Uso:  AliciaPad.iniciar({ console, enviar: (jogador, indice, valor) => …, maxJogadores, botao: elemento })  */
(function () {
  const BUT = { B: 0, Y: 1, SELECT: 2, START: 3, CIMA: 4, BAIXO: 5, ESQ: 6, DIR: 7, A: 8, X: 9, L: 10, R: 11, L2: 12, R2: 13, L3: 14, R3: 15 };
  // mapa padrão (mapping === "standard"), por posição física
  const PADRAO = { 0: { b: 0 }, 8: { b: 1 }, 1: { b: 2 }, 9: { b: 3 }, 10: { b: 4 }, 11: { b: 5 }, 12: { b: 6 }, 13: { b: 7 }, 2: { b: 8 }, 3: { b: 9 }, 14: { b: 10 }, 15: { b: 11 }, 4: { b: 12 }, 5: { b: 13 }, 6: { b: 14 }, 7: { b: 15 } };
  const EIXOS_PADRAO = { lx: 0, ly: 1, rx: 2, ry: 3 };
  const ROTULOS = {
    nes: [['Cima', 4], ['Baixo', 5], ['Esquerda', 6], ['Direita', 7], ['B', 0], ['A', 8], ['Select', 2], ['Start', 3]],
    snes: [['Cima', 4], ['Baixo', 5], ['Esquerda', 6], ['Direita', 7], ['B (baixo)', 0], ['A (direita)', 8], ['Y (esquerda)', 1], ['X (cima)', 9], ['L', 10], ['R', 11], ['Select', 2], ['Start', 3]],
    gba: [['Cima', 4], ['Baixo', 5], ['Esquerda', 6], ['Direita', 7], ['B', 0], ['A', 8], ['L', 10], ['R', 11], ['Select', 2], ['Start', 3]],
    psx: [['Cima', 4], ['Baixo', 5], ['Esquerda', 6], ['Direita', 7], ['✕ (baixo)', 0], ['○ (direita)', 8], ['□ (esquerda)', 1], ['△ (cima)', 9], ['L1', 10], ['R1', 11], ['L2', 12], ['R2', 13], ['Select', 2], ['Start', 3]],
    n64: [['Cima', 4], ['Baixo', 5], ['Esquerda', 6], ['Direita', 7], ['A', 0], ['B', 1], ['L', 10], ['R', 11], ['Z', 12], ['Start', 3]],
  };
  const FAMILIA = { 'Nintendo': 'nes', 'Super Nintendo': 'snes', 'Game Boy': 'gba', 'Game Boy Advance': 'gba', 'PlayStation': 'psx', 'Nintendo 64': 'n64' };
  const PASSO_ANALOGICO = [['Analógico esquerdo → para a DIREITA', 'lx'], ['Analógico esquerdo → para BAIXO', 'ly']];
  const $ = (t, a, ...f) => { const e = document.createElement(t); Object.assign(e, a || {}); f.flat().forEach(x => e.append(x)); return e; };

  const cfg = { console: '', enviar: () => {}, maxJogadores: 4, botao: null };
  const jogadores = [];            // índice do jogador -> índice do gamepad do navegador
  const ultimo = {};               // "jogador:indice" -> último valor enviado
  let perfis = {}, assistente = null, painel = null, avisou = {};

  const chave = g => g.index + '|' + g.id;
  const chaveId = g => 'alicia.ctl.' + g.id.replace(/\(.*?\)/g, '').replace(/\s+/g, ' ').trim().slice(0, 80);
  const nomeBonito = g => (g.id.replace(/\s*\(.*$/, '') || 'Controle').trim().slice(0, 40);
  function perfilDe(g) {
    if (perfis[chave(g)]) return perfis[chave(g)];
    let p = null;
    try { const s = localStorage.getItem(chaveId(g)); if (s) p = JSON.parse(s); } catch (e) {}
    if (!p) p = g.mapping === 'standard' ? { mapa: PADRAO, eixos: EIXOS_PADRAO, auto: true } : { mapa: {}, eixos: EIXOS_PADRAO, auto: true, precisaConfigurar: true };
    return (perfis[chave(g)] = p);
  }
  const fonteAtiva = (f, g) => {
    if (!f) return false;
    if (f.b !== undefined) { const b = g.buttons[f.b]; return !!b && (b.pressed || b.value > 0.5); }
    if (f.a !== undefined) { const v = g.axes[f.a]; if (v === undefined) return false; return f.v !== undefined ? Math.abs(v - f.v) < 0.12 : v * f.s > 0.55; }
    return false;
  };
  const manda = (j, i, v) => { const k = j + ':' + i; if (ultimo[k] === v) return; ultimo[k] = v; cfg.enviar(j, i, v); };

  function jogadorDe(g) {
    let j = jogadores.indexOf(chave(g));
    if (j >= 0) return j;
    if (jogadores.length >= cfg.maxJogadores) return -1;
    jogadores.push(chave(g));
    j = jogadores.length - 1;
    aviso(`🎮 ${nomeBonito(g)}: jogador ${j + 1}`);
    if (perfilDe(g).precisaConfigurar && !avisou[g.id]) { avisou[g.id] = 1; setTimeout(() => abrirPainel(true), 600); }
    return j;
  }

  function lerPads() {
    const pads = [...(navigator.getGamepads ? navigator.getGamepads() : [])].filter(Boolean);
    for (const g of pads) {
      if (assistente || (painel && painel.testando)) continue;
      const algo = g.buttons.some(b => b.pressed) || g.axes.some(a => Math.abs(a) > 0.5);
      if (jogadores.indexOf(chave(g)) < 0 && !algo) continue;        // só vira jogador quando alguém usa o controle
      const j = jogadorDe(g); if (j < 0) continue;
      const p = perfilDe(g), mapa = p.mapa || {}, ex = p.eixos || EIXOS_PADRAO;
      const ana = k => { const v = g.axes[ex[k]]; return v === undefined || Math.abs(v) > 1.05 ? 0 : (Math.abs(v) < 0.2 ? 0 : v); };
      const lx = ana('lx'), ly = ana('ly'), rx = ana('rx'), ry = ana('ry');
      for (const i of Object.keys(mapa).map(Number)) {
        let on = fonteAtiva(mapa[i], g);
        if (i === BUT.ESQ && lx < -0.55) on = true; if (i === BUT.DIR && lx > 0.55) on = true;       // analógico esquerdo também vale como direcional
        if (i === BUT.CIMA && ly < -0.55) on = true; if (i === BUT.BAIXO && ly > 0.55) on = true;
        manda(j, i, on ? 1 : 0);
      }
      const esc = v => Math.round(Math.min(1, (Math.abs(v) - 0.2) / 0.8) * 32767);
      manda(j, 16, lx > 0 ? esc(lx) : 0); manda(j, 17, lx < 0 ? esc(lx) : 0);          // analógico (Nintendo 64, PlayStation analógico)
      manda(j, 18, ly > 0 ? esc(ly) : 0); manda(j, 19, ly < 0 ? esc(ly) : 0);
      manda(j, 20, rx > 0 ? esc(rx) : 0); manda(j, 21, rx < 0 ? esc(rx) : 0);
      manda(j, 22, ry > 0 ? esc(ry) : 0); manda(j, 23, ry < 0 ? esc(ry) : 0);
    }
    // controle desligado: solta tudo daquele jogador
    for (let j = jogadores.length - 1; j >= 0; j--) {
      if (!pads.some(g => chave(g) === jogadores[j])) { for (let i = 0; i < 24; i++) manda(j, i, 0); jogadores.splice(j, 1); aviso('🎮 Controle desconectado'); }
    }
    requestAnimationFrame(lerPads);
  }

  function aviso(t) {
    let a = document.getElementById('padAviso');
    if (!a) { a = $('div', { id: 'padAviso' }); a.style.cssText = 'position:fixed;bottom:14px;left:50%;transform:translateX(-50%);z-index:90;background:#1a1d27ee;color:#e9ecf5;padding:10px 18px;border-radius:12px;font-size:16px;pointer-events:none;transition:opacity .3s'; document.body.append(a); }
    a.textContent = t; a.style.opacity = 1; clearTimeout(a._t); a._t = setTimeout(() => a.style.opacity = 0, 2800);
  }

  // ---------- assistente de configuração ----------
  function iniciarAssistente(g) {
    const fam = FAMILIA[cfg.console] || 'snes';
    const passos = ROTULOS[fam].concat(['psx', 'n64'].includes(fam) ? PASSO_ANALOGICO : []);
    const novo = { mapa: {}, eixos: { ...EIXOS_PADRAO }, auto: false };
    let n = 0, base = null, soltar = false;
    const caixa = $('div'); caixa.style.cssText = 'position:fixed;inset:0;z-index:120;background:#000d;display:grid;place-items:center;text-align:center;color:#fff;font-family:system-ui,sans-serif';
    const titulo = $('div'), sub = $('div'), pular = $('button', { textContent: 'Pular este botão' }), cancelar = $('button', { textContent: 'Cancelar' }), barra = $('div');
    titulo.style.cssText = 'font-size:34px;font-weight:800;margin:14px 0'; sub.style.cssText = 'font-size:18px;opacity:.85;margin-bottom:18px';
    [pular, cancelar].forEach(b => b.style.cssText = 'font-size:16px;padding:10px 18px;margin:6px;border-radius:10px;border:0;background:#2e3347;color:#fff;cursor:pointer');
    barra.style.cssText = 'font-size:15px;opacity:.7;margin-top:12px';
    caixa.append($('div', null, $('div', { textContent: '🎮 Configurar ' + nomeBonito(g) }), titulo, sub, pular, cancelar, barra)); document.body.append(caixa);
    const snap = () => { const p = [...navigator.getGamepads()].find(x => x && x.index === g.index) || g; return { b: p.buttons.map(b => b.pressed || b.value > 0.5), a: [...p.axes] }; };
    const mostra = () => {
      const nome = n < passos.length ? passos[n][0] : '';
      titulo.textContent = n < passos.length ? 'Aperte: ' + nome : 'Pronto!';
      sub.textContent = n < passos.length ? 'Segure o botão por um instante. Se o controle não tem esse botão, toque em "Pular".' : '';
      barra.textContent = n < passos.length ? `Passo ${n + 1} de ${passos.length}` : '';
    };
    const fim = salvar => {
      cancelAnimationFrame(assistente.raf); caixa.remove(); assistente = null;
      if (salvar) { try { localStorage.setItem(chaveId(g), JSON.stringify(novo)); } catch (e) {} perfis[chave(g)] = novo; aviso('✓ Controle configurado e salvo'); }
      if (painel) montarPainel();
    };
    assistente = { raf: 0 };
    cancelar.onclick = () => fim(false);
    pular.onclick = () => { n++; if (n >= passos.length) fim(true); else mostra(); };
    mostra(); base = snap(); base.b = base.b.map(() => false); soltar = true;      // repouso = nada apertado; espera soltar o que estiver segurado
    let liberado = performance.now() + 500;
    const laco = () => {
      if (!assistente) return;
      const atual = snap();
      if (performance.now() > liberado && n < passos.length) {
        let achou = null;
        atual.b.forEach((on, i) => { if (!achou && on && !base.b[i]) achou = { b: i }; });
        if (!achou) atual.a.forEach((v, i) => {
          if (achou) return;
          const rep = base.a[i] === undefined ? 0 : base.a[i];
          if (Math.abs(rep) > 1.05 && Math.abs(v - rep) > 0.1) achou = { a: i, v: +v.toFixed(3) };        // "hat": o eixo repousa fora de -1..1
          else if (Math.abs(rep) <= 1.05 && Math.abs(v - rep) > 0.7) achou = { a: i, s: v > rep ? 1 : -1 };
        });
        if (soltar) { if (!achou) soltar = false; }                 // espera soltar o botão antes de aceitar o próximo
        else if (achou) {
          const rot = passos[n];
          if (rot[1] === 'lx' || rot[1] === 'ly') { if (achou.a !== undefined) novo.eixos[rot[1]] = achou.a; }
          else novo.mapa[rot[1]] = achou;
          n++; soltar = true;
          if (n >= passos.length) { titulo.textContent = 'Pronto!'; sub.textContent = ''; barra.textContent = ''; setTimeout(() => fim(true), 700); return; }
          mostra();
        }
      }      assistente.raf = requestAnimationFrame(laco);
    };
    assistente.raf = requestAnimationFrame(laco);
  }

  // ---------- painel "🎮 Controle" ----------
  function abrirPainel(configurarAgora) {
    if (painel) { painel.el.remove(); painel = null; return; }
    painel = { el: $('div'), testando: false };
    painel.el.style.cssText = 'position:fixed;top:56px;left:8px;z-index:100;background:#1a1d27f2;color:#e9ecf5;padding:16px 18px;border-radius:14px;width:min(430px,92vw);font:15px system-ui,sans-serif;box-shadow:0 10px 30px #000a';
    document.body.append(painel.el); montarPainel();
    if (configurarAgora === true) { const g = [...navigator.getGamepads()].find(x => x); if (g) iniciarAssistente(g); }
  }
  function montarPainel() {
    if (!painel) return;
    const el = painel.el; el.textContent = '';
    el.append($('b', { textContent: '🎮 Controles' }));
    const fechar = $('button', { textContent: '✕' }); fechar.style.cssText = 'float:right;background:none;border:0;color:#fff;font-size:18px;cursor:pointer'; fechar.onclick = () => abrirPainel(); el.append(fechar);
    const pads = [...(navigator.getGamepads ? navigator.getGamepads() : [])].filter(Boolean);
    if (!pads.length) el.append($('p', { textContent: 'Nenhum controle detectado. Ligue o controle e aperte qualquer botão nele (no Bluetooth, pareie antes no aparelho).' }));
    pads.forEach(g => {
      const p = perfilDe(g), j = jogadores.indexOf(chave(g));
      const caixa = $('div'); caixa.style.cssText = 'background:#242838;border-radius:10px;padding:10px 12px;margin:10px 0';
      caixa.append($('div', { innerHTML: `<b>${nomeBonito(g)}</b> <span style="opacity:.7">· ${j >= 0 ? 'jogador ' + (j + 1) : 'aperte um botão para ativar'}</span>` }));
      caixa.append($('div', { textContent: g.mapping === 'standard' ? (p.auto ? '✓ Layout padrão (automático)' : '✓ Configuração própria salva') : (p.auto ? '⚠ Layout fora do padrão: configure abaixo' : '✓ Configuração própria salva'), style: 'opacity:.8;margin:4px 0 8px' }));
      const ao = $('div', { textContent: 'Aperte botões para testar…' }); ao.style.cssText = 'font-family:Consolas,monospace;min-height:1.4em;color:#a78bfa';
      const cfgb = $('button', { textContent: '⚙ Configurar botões' }), rest = $('button', { textContent: 'Restaurar padrão' });
      [cfgb, rest].forEach(b => b.style.cssText = 'background:#7c5cf0;color:#fff;border:0;border-radius:9px;padding:8px 12px;margin:8px 8px 0 0;cursor:pointer;font-size:14px');
      rest.style.background = '#2e3347';
      cfgb.onclick = () => iniciarAssistente(g);
      rest.onclick = () => { try { localStorage.removeItem(chaveId(g)); } catch (e) {} delete perfis[chave(g)]; aviso('Configuração apagada'); montarPainel(); };
      caixa.append(ao, cfgb, rest); el.append(caixa);
      (function viva() {
        if (!painel || !ao.isConnected) return;
        const q = [...navigator.getGamepads()].find(x => x && x.index === g.index);
        if (q) { const on = []; q.buttons.forEach((b, i) => { if (b.pressed || b.value > 0.5) on.push('B' + i); }); q.axes.forEach((v, i) => { if (Math.abs(v) > 0.5) on.push('E' + i + (v > 0 ? '+' : '-')); }); ao.textContent = on.length ? on.join('  ') : 'Aperte botões para testar…'; }
        requestAnimationFrame(viva);
      })();
    });
    el.append($('div', { textContent: 'Dica: o analógico esquerdo também funciona como direcional. Cada controle ligado vira um jogador.', style: 'opacity:.65;font-size:13px;margin-top:8px' }));
  }

  window.AliciaPad = {
    iniciar(o) {
      Object.assign(cfg, o);
      if (cfg.botao) cfg.botao.onclick = () => abrirPainel();
      addEventListener('gamepadconnected', () => { if (painel) montarPainel(); });
      addEventListener('gamepaddisconnected', () => { if (painel) montarPainel(); });
      requestAnimationFrame(lerPads);
    },
  };
})();
