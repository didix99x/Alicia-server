/* Alicia Server — controles na tela (celular e tablet) para os jogos.
   Substitui o gamepad virtual do EmulatorJS. Pensado para não errar:
   - vários dedos ao mesmo tempo; o dedo pode DESLIZAR de um botão para outro sem levantar;
   - o direcional é uma única área (8 direções, aceita o dedo "escorregar"); no Nintendo 64 vira analógico de verdade;
   - o dedo entre dois botões aperta os dois (ex.: A+B);
   - toque que cai fora dos controles passa para o jogo/menu; soltar, trocar de aba, girar a tela ou perder o foco solta tudo;
   - esconde sozinho quando um controle físico é usado; botões de ajuste: tamanho, transparência, vibração e modo canhoto.
   Uso: AliciaToque.iniciar({ console, enviar: (indice, valor) => …, menu: () => …, forcar: false }) */
(function () {
  const FAMILIA = { 'Nintendo': 'nes', 'Super Nintendo': 'snes', 'Game Boy': 'gba', 'Game Boy Advance': 'gba', 'PlayStation': 'psx', 'Nintendo 64': 'n64' };
  const PADRAO = { visivel: true, escala: 100, opac: 45, vibra: true, canhoto: false };
  const A = 0x7fff;
  const $ = (t, a, ...f) => { const e = document.createElement(t); if (a) Object.assign(e, a); f.flat().forEach(x => e.append(x)); return e; };
  let pref = { ...PADRAO }; try { Object.assign(pref, JSON.parse(localStorage.getItem('alicia.toque') || '{}')); } catch (e) {}
  const salva = () => { try { localStorage.setItem('alicia.toque', JSON.stringify(pref)); } catch (e) {} };

  let cfg = {}, raiz, barra, painel, ctrls = [], ponteiros = new Map(), ativos = {}, fam = 'snes', padFisico = 0, viu = false;

  const ehToque = () => !!cfg.forcar || (navigator.maxTouchPoints || 0) > 0 || matchMedia('(pointer: coarse)').matches;
  const visivel = () => pref.visivel && !padFisico && ehToque();

  // ---------- definição dos controles ----------
  function definir() {
    ctrls.forEach(c => c.el && c.el.remove()); ctrls = [];
    const add = c => { c.el = $('div'); c.el.className = 'tq ' + c.k; if (c.t) c.el.textContent = c.t; raiz.append(c.el); ctrls.push(c); return c; };
    if (fam === 'n64') add({ k: 'stick', idx: [16, 17, 18, 19] });   // x+, x-, y+(baixo), y-(cima)
    else add({ k: 'dpad' });
    const face = {
      nes: [['B', 0, -0.6, 0.35], ['A', 8, 0.6, -0.35]],
      gba: [['B', 0, -0.6, 0.35], ['A', 8, 0.6, -0.35]],
      snes: [['Y', 1, -1, 0], ['X', 9, 0, -1], ['B', 0, 0, 1], ['A', 8, 1, 0]],
      psx: [['□', 1, -1, 0], ['△', 9, 0, -1], ['✕', 0, 0, 1], ['○', 8, 1, 0]],
      n64: [['A', 0, -1.25, 0.35], ['B', 1, -0.3, 1.25]],
    }[fam];
    face.forEach(([t, idx, fx, fy]) => add({ k: 'btn', t, idx: [idx], fx, fy, f: 1 }));
    if (fam === 'n64') [['C▲', 23, 1.0, -0.9], ['C◀', 21, 0.45, -0.2], ['C▶', 20, 1.55, -0.2], ['C▼', 22, 1.0, 0.5]].forEach(([t, idx, fx, fy]) => add({ k: 'btn c', t, idx: [idx], fx, fy, f: 1, val: A, pequeno: true }));
    const om = { nes: [], gba: [['L', 10, 'L', 0], ['R', 11, 'R', 0]], snes: [['L', 10, 'L', 0], ['R', 11, 'R', 0]],
      psx: [['L1', 10, 'L', 0], ['R1', 11, 'R', 0], ['L2', 12, 'L', 1], ['R2', 13, 'R', 1]], n64: [['L', 10, 'L', 0], ['R', 11, 'R', 0], ['Z', 12, 'L', 1]] }[fam];
    om.forEach(([t, idx, lado, linha]) => add({ k: 'pill', t, idx: [idx], lado, linha, ombro: true }));
    if (fam !== 'n64') add({ k: 'pill', t: 'SELECT', idx: [2], mid: -1 });
    add({ k: 'pill', t: 'START', idx: [3], mid: fam === 'n64' ? 0 : 1 });
  }

  // ---------- posição (muda com o tamanho/rotação da tela) ----------
  function posiciona() {
    const W = innerWidth, H = innerHeight, retrato = H > W, e = pref.escala / 100;
    const u = (retrato ? W / 100 * 1.5 : Math.min(W / 100, H / 45)) * e;
    raiz.style.setProperty('--u', u + 'px'); raiz.style.setProperty('--op', pref.opac / 100);
    const dpC = retrato ? { x: 17 * u, y: H - 22 * u } : { x: 16 * u, y: H - 16 * u };
    let fC = retrato ? { x: W - 17 * u, y: H - 22 * u } : { x: W - (fam === 'n64' ? 19 : 16) * u, y: H - 16 * u };
    let dC = dpC;
    if (pref.canhoto) { dC = { x: W - dpC.x, y: dpC.y }; fC = { x: W - fC.x, y: fC.y }; }
    const d = (fam === 'n64' ? 8 : fam === 'nes' || fam === 'gba' ? 9 : 8.2) * u;
    for (const c of ctrls) {
      let x, y, w, h;
      if (c.k === 'dpad' || c.k === 'stick') { c.x = dC.x; c.y = dC.y; c.r = 11 * u; w = h = 22 * u; x = c.x; y = c.y; }
      else if (c.f) { c.r = (c.pequeno ? 3.4 : fam === 'n64' ? 5 : 5.4) * u; c.x = fC.x + c.fx * d; c.y = fC.y + c.fy * d; w = h = c.r * 2; x = c.x; y = c.y; }
      else {                                                    // pílulas: ombros, start, select
        w = 12 * u; h = 5.5 * u;
        if (c.ombro) { c.x = c.lado === 'L' ? 9 * u : W - 9 * u; c.y = (retrato ? H - (52 + c.linha * 9) * u : (7 + c.linha * 8.5) * u); }
        else { c.x = W / 2 + c.mid * (retrato ? 14 : 11) * u; c.y = H - (retrato ? 43 : 6) * u; w = 13 * u; h = 5 * u; }
        c.w = w; c.h = h; x = c.x; y = c.y;
      }
      Object.assign(c.el.style, { left: (x - w / 2) + 'px', top: (y - h / 2) + 'px', width: w + 'px', height: h + 'px', fontSize: (c.f ? c.r * 0.9 : h * 0.5) + 'px' });
    }
    barra.style.top = '58px';
  }

  // ---------- leitura dos dedos ----------
  function desejado() {
    const q = {};
    const poe = (i, v) => { if (Math.abs(v) > Math.abs(q[i] || 0)) q[i] = v; };
    for (const p of ponteiros.values()) {
      for (const c of ctrls) {
        const area = (c.k === 'dpad' || c.k === 'stick') ? 'd' : 'b';
        if (p.modo !== area) continue;                         // um dedo que começou no direcional só mexe no direcional; o que começou nos botões, só nos botões
        const dx = p.x - c.x, dy = p.y - c.y, dist = Math.hypot(dx, dy);
        if (c.k === 'dpad') {
          if (dist <= c.r * 2.4 && dist > c.r * 0.22) { const hx = dx / dist, hy = dy / dist; if (hy < -0.38) poe(4, 1); if (hy > 0.38) poe(5, 1); if (hx < -0.38) poe(6, 1); if (hx > 0.38) poe(7, 1); c.kx = dx; c.ky = dy; c.on = true; }
        } else if (c.k === 'stick') {
          if (dist <= c.r * 2.4) {
            const m = Math.min(1, dist / c.r), ux = dist ? dx / dist : 0, uy = dist ? dy / dist : 0, v = m < 0.12 ? 0 : Math.round(m * A);
            if (ux > 0) poe(16, Math.round(ux * v)); else poe(17, Math.round(-ux * v));
            if (uy > 0) poe(18, Math.round(uy * v)); else poe(19, Math.round(-uy * v));
            c.kx = ux * Math.min(dist, c.r); c.ky = uy * Math.min(dist, c.r); c.on = true;
          }
        } else if (c.f) {
          if (dist <= c.r * 1.22) { c.idx.forEach(i => poe(i, c.val || 1)); c.on = true; }
        } else if (Math.abs(dx) <= c.w * 0.62 && Math.abs(dy) <= c.h * 0.9) { c.idx.forEach(i => poe(i, 1)); c.on = true; }
      }
    }
    return q;
  }
  function atualiza() {
    ctrls.forEach(c => { c.on = false; });
    const q = desejado();
    const novos = [];
    for (const i of new Set([...Object.keys(ativos), ...Object.keys(q)])) {
      const antes = ativos[i] || 0, agora = q[i] || 0;
      if (antes !== agora) { cfg.enviar(+i, agora); if (agora && !antes && +i < 16) novos.push(i); }
    }
    ativos = Object.fromEntries(Object.entries(q).filter(([, v]) => v));
    if (novos.length && pref.vibra && navigator.vibrate) { try { navigator.vibrate(9); } catch (e) {} }
    for (const c of ctrls) {
      c.el.classList.toggle('on', !!c.on);
      if (c.k === 'stick') c.el.style.setProperty('--kx', (c.on ? c.kx : 0) + 'px'), c.el.style.setProperty('--ky', (c.on ? c.ky : 0) + 'px');
      if (c.k === 'dpad') ['u', 'd', 'l', 'r'].forEach(s => c.el.classList.toggle('d' + s, !!(c.on && ((s === 'u' && ativos[4]) || (s === 'd' && ativos[5]) || (s === 'l' && ativos[6]) || (s === 'r' && ativos[7])))));
    }
  }
  function soltaTudo() { ponteiros.clear(); atualiza(); }
  function modoDe(x, y) {                                   // onde o dedo caiu: botões têm prioridade; direcional aceita até 1,35 do raio
    if (ctrls.some(c => c.f ? Math.hypot(x - c.x, y - c.y) <= c.r * 1.22 : (c.k === 'pill' && Math.abs(x - c.x) <= c.w * 0.62 && Math.abs(y - c.y) <= c.h * 0.9))) return 'b';
    if (ctrls.some(c => (c.k === 'dpad' || c.k === 'stick') && Math.hypot(x - c.x, y - c.y) <= c.r * 1.35)) return 'd';
    return null;
  }
  const aceita = e => e.pointerType === 'touch' || e.pointerType === 'pen' || cfg.forcar;

  function ligaEventos() {
    const mov = e => { if (!aceita(e) || !visivel()) return; const p = ponteiros.get(e.pointerId); if (p) { p.x = e.clientX; p.y = e.clientY; atualiza(); e.preventDefault(); } };
    addEventListener('pointerdown', e => {
      if (!aceita(e) || !visivel() || (e.target.closest && e.target.closest('#tqbarra,#tqpainel'))) return;
      const modo = modoDe(e.clientX, e.clientY); if (!modo) return;     // fora dos controles: o toque é do jogo/menu
      ponteiros.set(e.pointerId, { x: e.clientX, y: e.clientY, modo }); atualiza(); e.preventDefault();
    }, { passive: false, capture: true });
    addEventListener('pointermove', mov, { passive: false, capture: true });
    const fim = e => { if (ponteiros.delete(e.pointerId)) atualiza(); };
    addEventListener('pointerup', fim, true); addEventListener('pointercancel', fim, true);
    addEventListener('touchmove', e => { if (ponteiros.size) e.preventDefault(); }, { passive: false });
    addEventListener('contextmenu', e => { if ((e.target.closest && e.target.closest('.tq')) || ponteiros.size) e.preventDefault(); });
    addEventListener('blur', soltaTudo); addEventListener('pagehide', soltaTudo);
    document.addEventListener('visibilitychange', () => { if (document.hidden) soltaTudo(); });
    addEventListener('resize', () => { soltaTudo(); posiciona(); });
    addEventListener('orientationchange', () => { soltaTudo(); setTimeout(posiciona, 250); });
    addEventListener('alicia-pad', e => { padFisico = e.detail.n; mostra(); });
  }

  // ---------- barra pequena (ocultar / ajustes / menu) e painel de ajustes ----------
  function mostra() {
    const v = visivel();
    raiz.style.display = v ? '' : 'none';
    barra.style.display = ehToque() ? 'flex' : 'none';
    barra.querySelector('#tqocultar').textContent = pref.visivel ? '👁 Ocultar controles' : '👁 Mostrar controles';
    if (v) posiciona();
  }
  function montaBarra() {
    barra = $('div', { id: 'tqbarra' });
    const ocultar = $('button', { id: 'tqocultar', type: 'button' }); ocultar.onclick = () => { pref.visivel = !pref.visivel; salva(); soltaTudo(); mostra(); };
    const ajustes = $('button', { type: 'button', textContent: '⚙ Ajustes' }); ajustes.onclick = () => { painel.style.display = painel.style.display === 'none' ? 'block' : 'none'; };
    barra.append(ocultar, ajustes);
    if (cfg.menu) { const m = $('button', { type: 'button', textContent: '☰ Menu' }); m.onclick = () => { soltaTudo(); cfg.menu(); }; barra.append(m); }
    painel = $('div', { id: 'tqpainel' }); painel.style.display = 'none';
    const lin = (txt, ...els) => $('label', null, $('span', { textContent: txt }), ...els);
    const tam = $('input', { type: 'range', min: 70, max: 150, step: 5, value: pref.escala }); tam.oninput = () => { pref.escala = +tam.value; salva(); posiciona(); };
    const op = $('input', { type: 'range', min: 20, max: 90, step: 5, value: pref.opac }); op.oninput = () => { pref.opac = +op.value; salva(); posiciona(); };
    const vib = $('input', { type: 'checkbox', checked: pref.vibra }); vib.onchange = () => { pref.vibra = vib.checked; salva(); if (vib.checked && navigator.vibrate) navigator.vibrate(30); };
    const can = $('input', { type: 'checkbox', checked: pref.canhoto }); can.onchange = () => { pref.canhoto = can.checked; salva(); posiciona(); };
    const fechar = $('button', { type: 'button', textContent: 'Fechar' }); fechar.onclick = () => painel.style.display = 'none';
    painel.append($('b', { textContent: 'Controles na tela' }), lin('Tamanho', tam), lin('Transparência', op), lin('Vibração ao tocar', vib), lin('Modo canhoto (troca os lados)', can), fechar);
    document.body.append(barra, painel);
  }
  function estilos() {
    document.head.append($('style', { textContent: `
html,body{touch-action:none;overscroll-behavior:none}
#tqraiz{position:fixed;inset:0;z-index:70;pointer-events:none;--u:8px;--op:.45;-webkit-user-select:none;user-select:none;-webkit-touch-callout:none;touch-action:none}
.tq{pointer-events:auto;position:absolute;display:grid;place-items:center;color:#fff;font-weight:800;font-family:system-ui,sans-serif;box-sizing:border-box;opacity:var(--op);background:#ffffff30;border:2px solid #ffffff90;transition:background .06s,opacity .06s;touch-action:none}
.tq.on{opacity:.95;background:#a78bfaee;border-color:#fff}
.tq.btn{border-radius:50%}.tq.pill{border-radius:999px;letter-spacing:.04em}
.tq.dpad,.tq.stick{border-radius:50%;background:radial-gradient(circle,#ffffff14 0,#ffffff2a 100%)}
.tq.dpad.on,.tq.stick.on{background:radial-gradient(circle,#ffffff22 0,#a78bfa66 100%);border-color:#ffffffc0}
.tq.dpad:before,.tq.dpad:after{content:"";position:absolute;background:#ffffffb0;border-radius:4px}
.tq.dpad:before{width:26%;height:74%}.tq.dpad:after{height:26%;width:74%}
.tq.dpad.du:before{background:linear-gradient(#a78bfa 50%,#ffffffb0 50%)}.tq.dpad.dd:before{background:linear-gradient(#ffffffb0 50%,#a78bfa 50%)}
.tq.dpad.dl:after{background:linear-gradient(90deg,#a78bfa 50%,#ffffffb0 50%)}.tq.dpad.dr:after{background:linear-gradient(90deg,#ffffffb0 50%,#a78bfa 50%)}
.tq.stick:before{content:"";width:46%;height:46%;border-radius:50%;background:#ffffffc0;transform:translate(var(--kx,0px),var(--ky,0px));box-shadow:0 2px 8px #0008}
.tq.c{background:#fbbf2440;border-color:#fbbf24b0}
#tqbarra{position:fixed;top:58px;left:50%;flex-wrap:nowrap;opacity:.5;transform:translateX(-50%);z-index:80;display:flex;gap:6px}
#tqbarra button,#tqpainel button{white-space:nowrap;width:auto;height:auto;min-width:0;line-height:1.2;background:#1a1d27dd;color:#e9ecf5;border:1px solid #ffffff40;border-radius:999px;padding:6px 12px;font-size:13px;font-family:system-ui,sans-serif}
#tqpainel{position:fixed;top:44px;left:50%;transform:translateX(-50%);z-index:85;background:#1a1d27f5;color:#e9ecf5;padding:14px 16px;border-radius:14px;width:min(320px,90vw);font:14px system-ui,sans-serif;box-shadow:0 10px 30px #000a}
#tqpainel label{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:10px 0}
#tqpainel input[type=range]{flex:1;max-width:160px}
.ejs_virtualGamepad_parent{display:none!important}
` }));
  }

  window.AliciaToque = {
    iniciar(o) {
      if (viu) return; viu = true; cfg = o; fam = FAMILIA[o.console] || 'snes';
      estilos(); raiz = $('div', { id: 'tqraiz' }); document.body.append(raiz);
      definir(); montaBarra(); ligaEventos(); mostra(); posiciona();
    },
    painelControles() { return ctrls; },
  };
})();
