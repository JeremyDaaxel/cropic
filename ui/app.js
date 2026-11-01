const WEB_MODE = !window.pywebview && new URLSearchParams(location.search).has('web');
const webApi = new Proxy({}, {
  get: (_, method) => async (...args) => {
    const r = await fetch('/api/' + method, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(args),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
});
const api = () => (window.pywebview ? window.pywebview.api : webApi);
const $ = (s) => document.querySelector(s);
const el = (t, c) => { const e = document.createElement(t); if (c) e.className = c; return e; };
const editKey = (id, preset) => `${id}|${preset}`;

const SEP = String.fromCharCode(92);
const baseName = (p) => p.substring(Math.max(p.lastIndexOf('/'), p.lastIndexOf(SEP)) + 1);

const LONG_SIDE = 2000;

const state = {
  items: [],
  current: null,
  presets: [],
  preset: 'ig_portrait',
  variants: [],
  variant: 0,
  editing: false,
  tab: 'var',
  split: null,
  pieces: 2,
  cutMode: 'cara',
  zoom: null,
  vcenter: null,
  ig: false,
  igSlide: 0,
  editBox: null,
  fmt: 'jpg',
  edits: {},
  showFaces: true,
  sound: true,
  busy: false,
};

const SOUNDS = ['hover', 'click', 'select', 'open', 'close', 'done', 'error', 'ready', 'tick',
                'lightmode', 'darkmode'];
const audio = {};
const WAV_ONLY = new Set(['error']);
for (const s of SOUNDS) {
  const a = new Audio(`sounds/${s}.${WAV_ONLY.has(s) ? 'wav' : 'mp3'}`);
  a.preload = 'auto';
  a.addEventListener('error', () => { audio[s] = new Audio(`sounds/${s}.wav`); }, { once: true });
  audio[s] = a;
}
let lastPlayAt = {};
function play(name, vol = 1) {
  if (!state.sound) return null;
  const src = audio[name];
  if (!src) return null;
  const now = performance.now();
  if (now - (lastPlayAt[name] || 0) < 60) return null;
  lastPlayAt[name] = now;
  const a = src.cloneNode();
  a.volume = Math.min(1, vol * 0.7);
  a.play().catch(() => {});
  return a;
}
let lastHovered = null, lastHoverAt = 0, hoverVoice = null;
document.addEventListener('mouseover', (e) => {
  const t = e.target.closest('.btn, .seg-btn, .iconbtn');
  if (!t || t === lastHovered) return;
  lastHovered = t;
  const now = performance.now();
  if (now - lastHoverAt < 220) return;
  lastHoverAt = now;
  if (hoverVoice) { hoverVoice.pause(); hoverVoice.currentTime = 0; }
  hoverVoice = play('hover', 0.35);
});
document.addEventListener('mouseout', (e) => {
  if (e.target === lastHovered) lastHovered = null;
});
document.addEventListener('click', (e) => {
  const t = e.target.closest('.btn, .seg-btn, .iconbtn, .variant, .file, .tab');
  if (t) play(t.classList.contains('variant') || t.classList.contains('file') ? 'select' : 'click', 0.6);
});

let prefsTimer = null;
function savePrefs() {
  clearTimeout(prefsTimer);
  prefsTimer = setTimeout(() => {
    api().save_prefs({
      preset: state.preset, fmt: state.fmt, sound: state.sound,
      dark: document.body.classList.contains('dark'),
      pieces: state.pieces, cutMode: state.cutMode,
      dpi: parseInt($('#inpDpi').value, 10) || 300,
      sheet: $('#selSheet').value,
    });
  }, 400);
}

let toastTimer = null;
function toast(msg, kind = '') {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3200);
  if (kind === 'error') play('error');
  if (kind === 'done') play('done');
}

function busy(on, msg) {
  state.busy = on;
  document.body.style.cursor = on ? 'progress' : '';
  if (on && msg) toast(msg);
}

window.addEventListener('pywebviewready', init);
if (WEB_MODE) window.addEventListener('DOMContentLoaded', init);

async function init() {
  state.presets = await api().presets();
  renderPresets();
  const sheets = await api().sheets();
  $('#selSheet').innerHTML = sheets.map(s => `<option value="${s.key}">${s.label}</option>`).join('');
  const modes = await api().cut_modes();
  $('#selCut').innerHTML = modes.map(m => `<option value="${m.key}">${m.label}</option>`).join('');
  const st = await api().settings();
  applyPrefs(st.prefs || {});
  $('#info').innerHTML = 'Carga una foto para empezar.';
  bind();
  play('ready', 0.6);
}

function applyPrefs(p) {
  if (p.dark) document.body.classList.add('dark');
  if (p.sound === false) { state.sound = false; $('#btnSound').classList.add('off'); }
  if (p.preset && state.presets.some(x => x.key === p.preset)) state.preset = p.preset;
  if (p.fmt) {
    state.fmt = p.fmt;
    document.querySelectorAll('.seg-btn').forEach(b => b.classList.toggle('sel', b.dataset.fmt === p.fmt));
  }
  if (p.pieces) { state.pieces = p.pieces; $('#selPieces').value = p.pieces; }
  if (p.cutMode) { state.cutMode = p.cutMode; $('#selCut').value = p.cutMode; }
  if (p.dpi) $('#inpDpi').value = p.dpi;
  if (p.sheet) $('#selSheet').value = p.sheet;
  const pr = currentPreset();
  if (pr) {
    paintRatio();
    $('#sheetBox').style.display = pr.isDoc ? '' : 'none';
    $('#rowDpi').style.display = pr.isDoc ? '' : 'none';
  }
}

function renderPresets() {
  const menu = $('#ddMenu');
  menu.innerHTML = '';
  let i = 0;
  for (const group of ['Instagram', 'Documento', 'Otros']) {
    const g = el('div', 'dd-group');
    g.textContent = group.toLowerCase();
    menu.appendChild(g);
    for (const p of state.presets.filter(x => x.group === group)) {
      const b = el('button', 'dd-item' + (p.key === state.preset ? ' sel' : ''));
      b.style.setProperty('--i', i++);
      b.dataset.key = p.key;
      b.setAttribute('role', 'option');
      const w = p.ratio >= 1 ? 15 : Math.round(15 * p.ratio);
      const h = p.ratio >= 1 ? Math.round(15 / p.ratio) : 15;
      b.innerHTML = `<span class="ar"><i style="width:${w}px;height:${h}px"></i></span>` +
                    `<span>${p.label}</span>` +
                    (p.mm ? `<span class="mm">${p.mm[0]}x${p.mm[1]} mm</span>` : '');
      b.onclick = () => { closeDD(); selectPreset(p.key); };
      menu.appendChild(b);
    }
  }
  paintRatio();
}

let ddClosing = null;
function openDD() {
  const menu = $('#ddMenu');
  clearTimeout(ddClosing);
  menu.classList.remove('closing');
  menu.hidden = false;
  $('#ddPreset').classList.add('open');
  $('#ddBtn').setAttribute('aria-expanded', 'true');
  menu.querySelector('.dd-item.sel')?.scrollIntoView({ block: 'nearest' });
  play('open', 0.45);
}

function closeDD() {
  const menu = $('#ddMenu');
  if (menu.hidden) return;
  menu.classList.add('closing');
  $('#ddPreset').classList.remove('open');
  $('#ddBtn').setAttribute('aria-expanded', 'false');
  ddClosing = setTimeout(() => {
    menu.hidden = true;
    menu.classList.remove('closing');
    menu.querySelectorAll('.dd-item').forEach(b => b.classList.remove('marked'));
  }, 140);
}

function toggleDD() { $('#ddMenu').hidden ? openDD() : closeDD(); }

function ddKeys(e) {
  if ($('#ddMenu').hidden) return false;
  const items = [...document.querySelectorAll('.dd-item')];
  let i = items.findIndex(b => b.classList.contains('marked'));
  if (i < 0) i = items.findIndex(b => b.classList.contains('sel'));
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    i = (i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
    items.forEach(b => b.classList.remove('marked'));
    items[i].classList.add('marked');
    items[i].scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter') {
    items[Math.max(0, i)].click();
  } else if (e.key === 'Escape') {
    closeDD();
  } else {
    return false;
  }
  e.preventDefault();
  return true;
}

function paintRatio() {
  const p = currentPreset();
  if (!p) return;
  const i = $('#arPreview i');
  i.style.width = (p.ratio >= 1 ? 16 : Math.round(16 * p.ratio)) + 'px';
  i.style.height = (p.ratio >= 1 ? Math.round(16 / p.ratio) : 16) + 'px';
  $('#ddLabel').textContent = p.label;
  document.querySelectorAll('.dd-item').forEach(b =>
    b.classList.toggle('sel', b.dataset.key === state.preset));
}

function currentPreset() {
  return state.presets.find(p => p.key === state.preset);
}

async function selectPreset(key) {
  state.preset = key;
  state.vcenter = null;
  paintRatio();
  const p = currentPreset();
  $('#sheetBox').style.display = p.isDoc ? '' : 'none';
  $('#rowDpi').style.display = p.isDoc ? '' : 'none';
  play('tick', 0.7);
  savePrefs();
  await refreshVariants();
  await refreshSplit();
}

function bind() {
  $('#btnOpen').onclick = async () => {
    if (WEB_MODE) {
      const pat = prompt('Ruta de la imagen, carpeta o patron. Ejemplo: C:/fotos/*.png');
      if (pat) { const paths = await api().expand(pat); paths.length ? load(paths) : toast('Sin coincidencias', 'error'); }
      return;
    }
    const paths = await api().pick_files();
    if (paths.length) load(paths);
  };
  $('#btnFolder').onclick = async () => {
    const paths = await api().pick_folder();
    if (paths.length) load(paths); else if (paths) toast('Esa carpeta no tiene imagenes');
  };
  $('#btnClear').onclick = async () => {
    await api().clear();
    state.items = []; state.current = null; state.variants = []; state.edits = {};
    renderFiles(); renderVariants(); $('#stageimg').src = ''; $('#drop').classList.remove('hide');
    $('#winTitle').textContent = 'vista previa';
    play('close');
  };
  $('#btnAuto').onclick = async () => applyInfo(await api().reset_box(state.current.id));
  $('#btnFull').onclick = async () => applyInfo(await api().use_full(state.current.id));
  $('#btnEdit').onclick = toggleEdit;
  $('#btnFaces').onclick = () => {
    state.showFaces = !state.showFaces;
    $('#btnFaces').classList.toggle('on', state.showFaces);
    play('tick', 0.6);
    drawOverlay();
  };
  $('#segFmt').onclick = (e) => {
    const b = e.target.closest('.seg-btn');
    if (!b) return;
    state.fmt = b.dataset.fmt;
    $('#segFmt').querySelectorAll('.seg-btn').forEach(x => x.classList.toggle('sel', x === b));
    play('tick', 0.6);
    savePrefs();
  };
  $('#tabVar').onclick = () => setTab('var');
  $('#tabSplit').onclick = () => setTab('split');
  $('#selPieces').onchange = () => { state.pieces = +$('#selPieces').value; savePrefs(); refreshSplit(true); };
  $('#selCut').onchange = () => { state.cutMode = $('#selCut').value; savePrefs(); refreshSplit(true); };
  $('#selSheet').onchange = savePrefs;
  $('#inpDpi').onchange = () => { savePrefs(); updateInfo(); };
  $('#rngZoom').oninput = () => { state.zoom = +$('#rngZoom').value / 100; refreshSplit(true); };
  $('#btnZoomAuto').onclick = () => {
    state.zoom = null;
    $('#rngZoom').value = 0;
    play('tick', 0.6);
    refreshSplit(true);
  };
  $('#btnExportSplit').onclick = exportSplit;
  $('#btnExport').onclick = exportOne;
  $('#btnExportAll').onclick = exportAll;
  $('#btnSheet').onclick = makeSheet;
  $('#btnOut').onclick = async () => {
    const dir = await api().choose_out_dir();
    toast('Las fotos se guardaran en ' + dir);
  };
  $('#ddBtn').onclick = (e) => { e.stopPropagation(); toggleDD(); };
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#ddPreset')) closeDD();
  });
  $('#metaclose').onclick = closeMeta;
  dragWindow($('#metawin'), $('#metadrag'));
  $('#btnInfo').onclick = () => toggleInfo();
  $('#infoclose').onclick = () => toggleInfo(false);
  dragWindow($('#infowin'), $('#infodrag'));
  $('#btnIG').onclick = () => toggleIG();
  $('#igclose').onclick = () => toggleIG(false);
  $('#igprev').onclick = () => slideIG(-1);
  $('#ignext').onclick = () => slideIG(1);
  dragWindow($('#igwin'), $('#igdrag'));
  $('#btnSound').onclick = () => {
    state.sound = !state.sound;
    $('#btnSound').classList.toggle('off', !state.sound);
    if (state.sound) play('click');
    savePrefs();
  };
  $('#btnTheme').onclick = () => {
    const dark = document.body.classList.toggle('dark');
    play(dark ? 'darkmode' : 'lightmode', 0.8);
    savePrefs();
  };

  const stage = $('#stage');
  stage.addEventListener('dragover', e => { e.preventDefault(); stage.classList.add('dragover'); });
  stage.addEventListener('dragleave', () => stage.classList.remove('dragover'));
  stage.addEventListener('drop', e => {
    e.preventDefault();
    stage.classList.remove('dragover');
    const paths = [...(e.dataTransfer.files || [])].map(f => f.pywebviewFullPath).filter(Boolean);
    if (paths.length) load(paths);
    else toast('No pude leer la ruta; usa el boton Abrir imagenes', 'error');
  });
  enableCropDrag();
  window.addEventListener('resize', drawOverlay);
  document.addEventListener('keydown', onKey);
}

async function load(paths) {
  busy(true, `Analizando ${paths.length} imagen(es)...`);
  const res = await api().add_paths(paths);
  busy(false);
  state.items.push(...res.items);
  renderFiles();
  if (res.errors.length) toast(`${res.errors.length} archivo(s) no se pudieron leer`, 'error');
  if (res.items.length) { select(res.items[res.items.length - 1].id); play('open'); }
}

function renderFiles() {
  const list = $('#filelist');
  list.innerHTML = '';
  for (const it of state.items) {
    const row = el('div', 'file' + (state.current && it.id === state.current.id ? ' sel' : ''));
    const img = el('img'); img.src = it.thumb;
    const meta = el('div', 'meta');
    const nm = el('div', 'nm'); nm.textContent = it.name;
    const sub = el('div', 'sub');
    sub.textContent = it.isScreenshot
      ? `captura · ${it.photoSize[0]}x${it.photoSize[1]}`
      : `foto · ${it.photoSize[0]}x${it.photoSize[1]}`;
    meta.append(nm, sub);
    row.append(img, meta);
    row.onclick = () => select(it.id);
    row.ondblclick = () => showMeta(it.id);
    list.appendChild(row);
  }
}

async function select(id) {
  const it = state.items.find(i => i.id === id);
  if (!it) return;
  state.current = it;
  state.editing = false;
  state.vcenter = null;
  $('#btnEdit').textContent = 'Ajustar borde';
  renderFiles();
  $('#drop').classList.add('hide');
  $('#stageimg').src = it.preview;
  $('#winTitle').textContent = it.name;
  await refreshVariants();
  await refreshSplit();
  updateInfo();
}

function applyInfo(info) {
  if (!info) return;
  forgetEdits(info.id);
  const i = state.items.findIndex(x => x.id === info.id);
  if (i >= 0) state.items[i] = info;
  state.current = info;
  renderFiles();
  $('#stageimg').src = info.preview;
  refreshVariants();
  updateInfo();
}

async function refreshVariants() {
  if (!state.current) return;
  const guardado = savedEdits();
  if (guardado && guardado.variants) {
    state.variants = guardado.variants;
    state.variant = guardado.variant || 0;
    renderVariants();
    drawOverlay();
    renderIG();
    return;
  }
  busy(true);
  state.variants = await api().variants(state.current.id, state.preset);
  state.variant = 0;
  busy(false);
  renderVariants();
  drawOverlay();
  renderIG();
}

function renderVariants() {
  const box = $('#variants');
  box.innerHTML = '';
  state.variants.forEach((v, i) => {
    const c = el('div', 'variant' + (i === state.variant ? ' sel' : ''));
    const b = el('div', 'box');
    const img = el('img'); img.src = v.thumb; b.appendChild(img);
    const nm = el('div', 'nm'); nm.textContent = v.name;
    const sc = el('div', 'sc'); sc.innerHTML = `<b>${v.score}</b> · ${v.size[0]}x${v.size[1]}`;
    c.append(b, nm, sc);
    c.onclick = () => {
      state.variant = i;
      renderVariants(); drawOverlay(); updateInfo(); renderIG(); rememberEdits();
    };
    box.appendChild(c);
  });
}

function stageGeom() {
  const img = $('#stageimg');
  const r = img.getBoundingClientRect();
  const s = $('#stage').getBoundingClientRect();
  return { left: r.left - s.left, top: r.top - s.top, w: r.width, h: r.height };
}

function drawOverlay() {
  const cv = $('#overlay');
  const it = state.current;
  const g = stageGeom();
  if (!it || !g.w) { cv.width = cv.height = 0; return; }

  const dpr = window.devicePixelRatio || 1;
  cv.width = g.w * dpr; cv.height = g.h * dpr;
  cv.style.width = g.w + 'px'; cv.style.height = g.h + 'px';
  cv.style.left = g.left + 'px'; cv.style.top = g.top + 'px';
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, g.w, g.h);

  const src = state.editing ? it.size : it.photoSize;
  const kx = g.w / src[0], ky = g.h / src[1];

  if (state.editing) {
    const [x0, y0, x1, y1] = state.editBox;
    ctx.fillStyle = 'rgba(66,66,66,.55)';
    ctx.fillRect(0, 0, g.w, y0 * ky);
    ctx.fillRect(0, y1 * ky, g.w, g.h - y1 * ky);
    ctx.fillRect(0, y0 * ky, x0 * kx, (y1 - y0) * ky);
    ctx.fillRect(x1 * kx, y0 * ky, g.w - x1 * kx, (y1 - y0) * ky);
    ctx.strokeStyle = '#f5a623'; ctx.lineWidth = 2;
    ctx.strokeRect(x0 * kx, y0 * ky, (x1 - x0) * kx, (y1 - y0) * ky);
    for (const [hx, hy] of handles(x0 * kx, y0 * ky, x1 * kx, y1 * ky)) {
      ctx.fillStyle = '#fff'; ctx.strokeStyle = '#424242'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(hx, hy, 6, 0, 7); ctx.fill(); ctx.stroke();
    }
    return;
  }

  if (state.showFaces) {
    ctx.strokeStyle = '#4a9c5d'; ctx.lineWidth = 2;
    ctx.font = '11px "DM Mono", monospace'; ctx.fillStyle = '#4a9c5d';
    for (const f of it.faces) {
      const [x, y, w, h] = f.box;
      ctx.strokeRect(x * kx, y * ky, w * kx, h * ky);
      ctx.fillText('cara ' + f.score, x * kx, Math.max(11, y * ky - 4));
    }
  }

  if (state.tab === 'split') {
    const sp = state.split;
    if (!sp || !sp.pieces.length) return;
    const first = sp.pieces[0].box, last = sp.pieces[sp.pieces.length - 1].box;
    ctx.fillStyle = 'rgba(255,248,224,.55)';
    ctx.fillRect(0, 0, g.w, first[1] * ky);
    ctx.fillRect(0, first[3] * ky, g.w, g.h - first[3] * ky);
    ctx.fillRect(0, first[1] * ky, first[0] * kx, (first[3] - first[1]) * ky);
    ctx.fillRect(last[2] * kx, first[1] * ky, g.w - last[2] * kx, (first[3] - first[1]) * ky);
    ctx.strokeStyle = '#f5a623'; ctx.lineWidth = 3;
    ctx.strokeRect(first[0] * kx, first[1] * ky, (last[2] - first[0]) * kx,
                   (first[3] - first[1]) * ky);
    ctx.lineWidth = 2; ctx.setLineDash([7, 5]);
    for (let i = 0; i < sp.pieces.length - 1; i++) {
      const x = sp.pieces[i].box[2] * kx;
      ctx.beginPath(); ctx.moveTo(x, first[1] * ky); ctx.lineTo(x, first[3] * ky); ctx.stroke();
    }
    ctx.setLineDash([]);
    for (const [hx, hy] of handles(first[0] * kx, first[1] * ky, last[2] * kx, first[3] * ky)) {
      ctx.save();
      ctx.shadowColor = 'rgba(0,0,0,.35)'; ctx.shadowBlur = 4; ctx.shadowOffsetY = 1;
      ctx.fillStyle = '#fff';
      ctx.beginPath(); ctx.arc(hx, hy, 6.5, 0, 7); ctx.fill();
      ctx.restore();
      ctx.strokeStyle = '#f5a623'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(hx, hy, 6.5, 0, 7); ctx.stroke();
    }
    return;
  }

  const v = state.variants[state.variant];
  if (!v) return;
  const [x0, y0, x1, y1] = v.box;
  ctx.fillStyle = 'rgba(255,248,224,.55)';
  ctx.fillRect(0, 0, g.w, y0 * ky);
  ctx.fillRect(0, y1 * ky, g.w, g.h - y1 * ky);
  ctx.fillRect(0, y0 * ky, x0 * kx, (y1 - y0) * ky);
  ctx.fillRect(x1 * kx, y0 * ky, g.w - x1 * kx, (y1 - y0) * ky);
  ctx.strokeStyle = '#f5a623'; ctx.lineWidth = 3;
  ctx.strokeRect(x0 * kx, y0 * ky, (x1 - x0) * kx, (y1 - y0) * ky);

  for (const [hx, hy] of handles(x0 * kx, y0 * ky, x1 * kx, y1 * ky)) {
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,.35)';
    ctx.shadowBlur = 4;
    ctx.shadowOffsetY = 1;
    ctx.fillStyle = '#fff';
    ctx.beginPath(); ctx.arc(hx, hy, 6.5, 0, 7); ctx.fill();
    ctx.restore();
    ctx.strokeStyle = '#f5a623'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(hx, hy, 6.5, 0, 7); ctx.stroke();
  }

  {
    ctx.strokeStyle = 'rgba(245,166,35,.55)'; ctx.lineWidth = 1;
    const bw = (x1 - x0) * kx, bh = (y1 - y0) * ky, bx = x0 * kx, by = y0 * ky;
    for (let i = 1; i < 3; i++) {
      ctx.beginPath(); ctx.moveTo(bx + bw * i / 3, by); ctx.lineTo(bx + bw * i / 3, by + bh); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(bx, by + bh * i / 3); ctx.lineTo(bx + bw, by + bh * i / 3); ctx.stroke();
    }
  }
}

function handles(x0, y0, x1, y1) {
  return [[x0, y0], [x1, y0], [x0, y1], [x1, y1],
          [(x0 + x1) / 2, y0], [(x0 + x1) / 2, y1], [x0, (y0 + y1) / 2], [x1, (y0 + y1) / 2]];
}

async function toggleEdit() {
  if (!state.current) return;
  state.editing = !state.editing;
  $('#btnEdit').textContent = state.editing ? 'Aplicar borde' : 'Ajustar borde';
  if (state.editing) {
    state.editBox = [...state.current.box];
    $('#stageimg').src = await api().original_preview(state.current.id);
    $('#stageimg').onload = drawOverlay;
    enableDrag();
    play('open', .7);
    toast('Arrastra los tiradores para marcar donde empieza y acaba la foto');
  } else {
    disableDrag();
    busy(true);
    applyInfo(await api().set_box(state.current.id, state.editBox));
    busy(false);
    enableCropDrag();
    play('done', .6);
  }
}

let dragState = null;
function enableDrag() {
  const cv = $('#overlay');
  cv.style.pointerEvents = 'auto';
  cv.onmousedown = (e) => {
    const g = stageGeom();
    const it = state.current;
    const kx = g.w / it.size[0], ky = g.h / it.size[1];
    const mx = e.offsetX, my = e.offsetY;
    const [x0, y0, x1, y1] = state.editBox;
    const pts = handles(x0 * kx, y0 * ky, x1 * kx, y1 * ky);
    let idx = -1, best = 14;
    pts.forEach(([hx, hy], i) => {
      const d = Math.hypot(hx - mx, hy - my);
      if (d < best) { best = d; idx = i; }
    });
    dragState = { idx, kx, ky, startX: mx, startY: my, box: [...state.editBox] };
  };
  cv.onmousemove = (e) => {
    if (!dragState) return;
    const { idx, kx, ky, box } = dragState;
    const mx = e.offsetX / kx, my = e.offsetY / ky;
    let [x0, y0, x1, y1] = state.editBox;
    if (idx < 0) {
      const dx = (e.offsetX - dragState.startX) / kx, dy = (e.offsetY - dragState.startY) / ky;
      [x0, y0, x1, y1] = [box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy];
    } else {
      if ([0, 2, 6].includes(idx)) x0 = mx;
      if ([1, 3, 7].includes(idx)) x1 = mx;
      if ([0, 1, 4].includes(idx)) y0 = my;
      if ([2, 3, 5].includes(idx)) y1 = my;
    }
    state.editBox = [Math.round(Math.min(x0, x1)), Math.round(Math.min(y0, y1)),
                     Math.round(Math.max(x0, x1)), Math.round(Math.max(y0, y1))];
    drawOverlay();
  };
  cv.onmouseup = cv.onmouseleave = () => { dragState = null; };
}
function disableDrag() {
  const cv = $('#overlay');
  cv.style.pointerEvents = 'none';
  cv.onmousedown = cv.onmousemove = cv.onmouseup = cv.onmouseleave = null;
}

function exportOpts() {
  const p = currentPreset();
  return {
    fmt: state.fmt,
    dpi: parseInt($('#inpDpi').value, 10) || 300,
    longSide: LONG_SIDE,
    isDoc: p.isDoc,
  };
}

async function exportOne() {
  const v = state.variants[state.variant];
  if (!state.current || !v) { toast('Elige una foto y una variante', 'error'); return; }
  const o = exportOpts();
  busy(true, 'Exportando...');
  const r = await api().export(state.current.id, state.preset, v.box, o.fmt, o.dpi, o.longSide);
  busy(false);
  if (r.ok) {
    const estirado = r.stretch > 1.15
      ? ` — ojo: estirado x${r.stretch}, la foto no da mas resolucion` : '';
    toast(`Guardado: ${baseName(r.path)} (${r.size[0]}x${r.size[1]})${estirado}`, 'done');
  }
  else toast('Error: ' + r.error, 'error');
}

async function exportAll() {
  if (!state.items.length) { toast('No hay fotos cargadas', 'error'); return; }
  const o = exportOpts();
  busy(true, `Exportando ${state.items.length} fotos...`);
  const jobs = [];
  for (const it of state.items) {
    const vs = it.id === state.current?.id ? state.variants
                                           : await api().variants(it.id, state.preset);
    if (vs.length) jobs.push({ itemId: it.id, presetKey: state.preset, box: vs[0].box });
  }
  const r = await api().export_batch(jobs, o.fmt, o.dpi, o.longSide);
  busy(false);
  toast(`${r.ok} exportadas en ${r.dir}` + (r.failed.length ? ` · ${r.failed.length} fallaron` : ''),
        r.failed.length ? 'error' : 'done');
}

async function makeSheet() {
  const v = state.variants[state.variant];
  if (!state.current || !v) { toast('Elige una foto y una variante', 'error'); return; }
  const o = exportOpts();
  busy(true, 'Armando la plancha...');
  const r = await api().export_sheet(state.current.id, state.preset, v.box,
                                     $('#selSheet').value, o.dpi, null, true, o.fmt);
  busy(false);
  if (r.ok) {
    $('#stageimg').src = r.preview;
    $('#overlay').width = 0;
    toast(`Plancha de ${r.meta.count} fotos (${r.meta.cols}x${r.meta.rows}) guardada`, 'done');
  } else toast('Error: ' + r.error, 'error');
}

function setTab(tab) {
  state.tab = tab;
  $('#tabVar').classList.toggle('sel', tab === 'var');
  $('#tabSplit').classList.toggle('sel', tab === 'split');
  $('#variants').style.display = tab === 'var' ? '' : 'none';
  $('#splitRow').style.display = tab === 'split' ? '' : 'none';
  $('#splitCtl').style.display = tab === 'split' ? '' : 'none';
  play(tab === 'split' ? 'open' : 'close', 0.5);
  state.igSlide = 0;
  if (tab === 'split') refreshSplit(); else { drawOverlay(); renderIG(); }
}

async function refreshSplit(forzar = false) {
  if (!state.current || state.tab !== 'split') return;
  const guardado = savedEdits();
  if (forzar && guardado) {
    delete guardado.split;
  } else if (guardado && guardado.split && guardado.pieces === state.pieces
      && guardado.cutMode === state.cutMode) {
    state.split = guardado.split;
    renderPieces();
    drawOverlay();
    renderIG();
    return;
  }
  busy(true);
  state.split = await api().split_preview(state.current.id, state.preset, state.pieces,
                                          state.cutMode, state.zoom, state.vcenter);
  busy(false);
  renderPieces();
  drawOverlay();
  renderIG();
}

function renderPieces() {
  const box = $('#pieces');
  box.innerHTML = '';
  const sp = state.split;
  if (!sp || !sp.pieces.length) return;
  sp.pieces.forEach((p, i) => {
    const d = el('div', 'piece');
    const img = el('img'); img.src = p.thumb;
    const n = el('span', 'num'); n.textContent = `${i + 1}/${sp.pieces.length}`;
    d.append(img, n);
    box.appendChild(d);
  });
  updateInfo();
}

async function exportSplit() {
  const sp = state.split;
  if (!state.current || !sp?.pieces.length) { toast('Nada que exportar', 'error'); return; }
  const o = exportOpts();
  busy(true, 'Exportando las piezas...');
  const r = await api().export_split(state.current.id, state.preset,
                                     sp.pieces.map(p => p.box), o.fmt, o.longSide);
  busy(false);
  if (r.ok) toast(`${r.paths.length} piezas guardadas en ${r.dir}`, 'done');
  else toast('Error: ' + r.error, 'error');
}

let cropDrag = null;
const HANDLE_CURSOR = ['nwse-resize', 'nesw-resize', 'nesw-resize', 'nwse-resize',
                       'ns-resize', 'ns-resize', 'ew-resize', 'ew-resize'];

function hitHandle(e, box, kx, ky) {
  const pts = handles(box[0] * kx, box[1] * ky, box[2] * kx, box[3] * ky);
  let best = -1, bestD = 13;
  pts.forEach(([hx, hy], i) => {
    const d = Math.hypot(hx - e.offsetX, hy - e.offsetY);
    if (d < bestD) { bestD = d; best = i; }
  });
  return best;
}

function resizeBox(box, h, dx, dy, W, H, ratio) {
  const [bx0, by0, bx1, by1] = box;
  let w;
  if (h === 4 || h === 5) {
    const alto = h === 4 ? (by1 - (by0 + dy)) : ((by1 + dy) - by0);
    w = alto * ratio;
  } else {
    const derecha = (h === 1 || h === 3 || h === 7);
    w = derecha ? (bx1 + dx - bx0) : (bx1 - (bx0 + dx));
  }
  w = Math.max(60, Math.min(w, W, H * ratio));
  const alto = w / ratio;

  let x0, y0;
  if (h === 4 || h === 5) {
    x0 = (bx0 + bx1) / 2 - w / 2;
    y0 = (h === 4) ? by1 - alto : by0;
  } else if (h === 6 || h === 7) {
    x0 = (h === 7) ? bx0 : bx1 - w;
    y0 = (by0 + by1) / 2 - alto / 2;
  } else {
    x0 = (h === 1 || h === 3) ? bx0 : bx1 - w;
    y0 = (h >= 2) ? by0 : by1 - alto;
  }
  x0 = Math.max(0, Math.min(x0, W - w));
  y0 = Math.max(0, Math.min(y0, H - alto));
  return [x0, y0, x0 + w, y0 + alto];
}

function enableCropDrag() {
  const cv = $('#overlay');
  cv.style.pointerEvents = 'auto';
  cv.style.cursor = 'default';

  const cajaActiva = () => {
    if (state.editing || !state.current) return null;
    if (state.tab === 'split') {
      const ps = state.split?.pieces;
      if (!ps || !ps.length) return null;
      return [ps[0].box[0], ps[0].box[1], ps[ps.length - 1].box[2], ps[0].box[3]];
    }
    const v = state.variants[state.variant];
    return v ? v.box : null;
  };
  const ratioActivo = () => currentPreset().ratio *
    (state.tab === 'split' ? (state.split?.pieces.length || 1) : 1);

  cv.onmousedown = (e) => {
    const caja = cajaActiva();
    if (!caja) return;
    const g = stageGeom();
    const kx = g.w / state.current.photoSize[0], ky = g.h / state.current.photoSize[1];
    const h = hitHandle(e, caja, kx, ky);
    const dentro = e.offsetX > caja[0] * kx && e.offsetX < caja[2] * kx &&
                   e.offsetY > caja[1] * ky && e.offsetY < caja[3] * ky;
    if (h < 0 && !dentro) return;
    cropDrag = { h, kx, ky, sx: e.offsetX, sy: e.offsetY, box: [...caja] };
    cv.style.cursor = h < 0 ? 'grabbing' : HANDLE_CURSOR[h];
  };

  cv.onmousemove = (e) => {
    if (!cropDrag) {
      const caja = cajaActiva();
      if (!caja) { cv.style.cursor = 'default'; return; }
      const g = stageGeom();
      const kx = g.w / state.current.photoSize[0], ky = g.h / state.current.photoSize[1];
      const h = hitHandle(e, caja, kx, ky);
      const dentro = e.offsetX > caja[0] * kx && e.offsetX < caja[2] * kx &&
                     e.offsetY > caja[1] * ky && e.offsetY < caja[3] * ky;
      cv.style.cursor = h >= 0 ? HANDLE_CURSOR[h] : (dentro ? 'grab' : 'default');
      return;
    }
    const [W, H] = state.current.photoSize;
    const ratio = ratioActivo();
    const { h, kx, ky, box } = cropDrag;
    const dx = (e.offsetX - cropDrag.sx) / kx, dy = (e.offsetY - cropDrag.sy) / ky;

    let out;
    if (h < 0) {
      const w = box[2] - box[0], alto = box[3] - box[1];
      const x0 = Math.max(0, Math.min(box[0] + dx, W - w));
      const y0 = Math.max(0, Math.min(box[1] + dy, H - alto));
      out = [x0, y0, x0 + w, y0 + alto];
    } else {
      out = resizeBox(box, h, dx, dy, W, H, ratio);
    }
    const caja = out.map(Math.round);
    if (state.tab === 'split') {
      const n = state.split.pieces.length;
      const pw = (caja[2] - caja[0]) / n;
      state.split.pieces.forEach((p, i) => {
        p.box = [Math.round(caja[0] + i * pw), caja[1],
                 Math.round(caja[0] + (i + 1) * pw), caja[3]];
      });
    } else {
      state.variants[state.variant].box = caja;
    }
    drawOverlay();
  };

  cv.onmouseup = cv.onmouseleave = async () => {
    if (!cropDrag) return;
    cropDrag = null;
    cv.style.cursor = 'grab';
    if (state.tab === 'split') await commitCustomBand();
    else await commitCustomCrop();
  };
}

async function commitCustomBand() {
  const ps = state.split?.pieces;
  if (!ps || !ps.length || !state.current) return;
  const band = [ps[0].box[0], ps[0].box[1], ps[ps.length - 1].box[2], ps[0].box[3]];
  const r = await api().split_custom(state.current.id, state.preset, ps.length, band);
  if (!r || !r.pieces.length) return;
  state.split = r;
  state.zoom = null;
  const alto = state.current.photoSize[1];
  state.vcenter = ((r.pieces[0].box[1] + r.pieces[0].box[3]) / 2) / alto;
  renderPieces();
  drawOverlay();
  renderIG();
  updateInfo();
  rememberEdits();
  play('tick', 0.5);
}

async function commitCustomCrop() {
  const v = state.variants[state.variant];
  if (!v || !state.current) return;
  const r = await api().preview_box(state.current.id, v.box, state.preset);
  if (!r || !r.thumb) return;
  v.name = 'A mano';
  v.note = 'Recorte movido por ti';
  v.thumb = r.thumb;
  v.size = r.size;
  if (r.score !== undefined) v.score = r.score;
  renderVariants();
  updateInfo();
  renderIG();
  rememberEdits();
  play('tick', 0.5);
}

function rememberEdits() {
  if (!state.current) return;
  const k = editKey(state.current.id, state.preset);
  const prev = state.edits[k] || {};
  state.edits[k] = {
    variants: state.variants,
    variant: state.variant,
    split: state.split || prev.split,
    pieces: state.pieces,
    cutMode: state.cutMode,
    tab: state.tab,
  };
}

function savedEdits() {
  if (!state.current) return null;
  return state.edits[editKey(state.current.id, state.preset)] || null;
}

function forgetEdits(itemId) {
  for (const k of Object.keys(state.edits)) {
    if (k.startsWith(itemId + '|')) delete state.edits[k];
  }
}

let metaClosing = null;

async function showMeta(itemId) {
  const win = $('#metawin');
  const cuerpo = $('#metabody');
  cuerpo.innerHTML = '<div id="metaempty">Leyendo el archivo...</div>';
  clearTimeout(metaClosing);
  win.classList.remove('closing', 'moved');
  win.hidden = false;
  play('open', 0.55);

  let m;
  try {
    m = await api().metadata(itemId);
  } catch (e) {
    cuerpo.innerHTML = '<div id="metaempty">No se pudieron leer los datos.<br>' +
                       String(e) + '</div>';
    return;
  }
  $('#metatitle').textContent = m.nombre || 'datos';
  cuerpo.innerHTML = '';
  if (!m.secciones || !m.secciones.length) {
    cuerpo.innerHTML = '<div id="metaempty">Este archivo no trae datos.</div>';
    return;
  }
  for (const sec of m.secciones) {
    const h = el('h4');
    h.textContent = sec.titulo;
    cuerpo.appendChild(h);
    for (const [k, v] of sec.filas) {
      const row = el('div', 'meta-row');
      const kk = el('div', 'meta-k'); kk.textContent = k;
      const vv = el('div', 'meta-v'); vv.textContent = v;
      row.append(kk, vv);
      cuerpo.appendChild(row);
    }
  }
}

function closeMeta() {
  const win = $('#metawin');
  if (win.hidden) return;
  win.classList.add('closing');
  play('close', 0.5);
  metaClosing = setTimeout(() => {
    win.hidden = true;
    win.classList.remove('closing');
  }, 260);
}

let infoClosing = null;
function toggleInfo(force) {
  const win = $('#infowin');
  const abrir = force === undefined ? win.hidden : force;
  clearTimeout(infoClosing);
  play(abrir ? 'open' : 'close', 0.6);
  if (abrir) {
    win.classList.remove('closing', 'moved');
    win.hidden = false;
  } else {
    win.classList.add('closing');
    infoClosing = setTimeout(() => {
      win.hidden = true;
      win.classList.remove('closing');
    }, 260);
  }
}

let igClosing = null;
function toggleIG(force) {
  const win = $('#igwin');
  const open = force === undefined ? !state.ig : force;
  if (open === state.ig && !win.hidden === open) return;
  state.ig = open;
  $('#btnIG').classList.toggle('off', !open);
  play(open ? 'open' : 'close', 0.6);

  clearTimeout(igClosing);
  if (open) {
    win.classList.remove('closing', 'moved');
    win.hidden = false;
    renderIG();
  } else {
    win.classList.add('closing');
    igClosing = setTimeout(() => {
      win.hidden = true;
      win.classList.remove('closing');
    }, 260);
  }
}

function igSlides() {
  if (state.tab === 'split' && state.split?.pieces.length) return state.split.pieces;
  const v = state.variants[state.variant];
  return v ? [v] : [];
}

function slideIG(step) {
  const n = igSlides().length;
  if (n < 2) return;
  state.igSlide = (state.igSlide + step + n) % n;
  play('tick', 0.5);
  renderIG();
}

function renderIG() {
  if (!state.ig) return;
  const slides = igSlides();
  const many = slides.length > 1;
  state.igSlide = Math.min(state.igSlide, Math.max(0, slides.length - 1));
  const cur = slides[state.igSlide];

  $('#igimg').src = cur ? cur.thumb : '';
  $('#igimg').style.aspectRatio = cur ? `${cur.size[0]} / ${cur.size[1]}` : '1 / 1';
  $('#igprev').hidden = !many || state.igSlide === 0;
  $('#ignext').hidden = !many || state.igSlide === slides.length - 1;
  $('#igcount').hidden = !many;
  $('#igcount').textContent = `${state.igSlide + 1}/${slides.length}`;

  const dots = $('#igdots');
  dots.innerHTML = '';
  if (many) slides.forEach((_, i) => {
    const d = el('i', i === state.igSlide ? 'on' : '');
    dots.appendChild(d);
  });
}

function dragWindow(win, handle) {
  let from = null;
  handle.addEventListener('mousedown', (e) => {
    if (e.target.closest('button')) return;
    const r = win.getBoundingClientRect();
    from = { x: e.clientX, y: e.clientY, left: r.left, top: r.top };
    win.classList.add('moved');
    win.style.margin = '0';
    win.style.right = 'auto';
    win.style.bottom = 'auto';
    win.style.left = r.left + 'px';
    win.style.top = r.top + 'px';
    e.preventDefault();
  });
  window.addEventListener('mousemove', (e) => {
    if (!from) return;
    const w = win.offsetWidth, h = win.offsetHeight;
    win.style.left = Math.max(0, Math.min(from.left + e.clientX - from.x, innerWidth - w)) + 'px';
    win.style.top = Math.max(0, Math.min(from.top + e.clientY - from.y, innerHeight - h)) + 'px';
  });
  window.addEventListener('mouseup', () => { from = null; });
}

function onKey(e) {
  if (e.target.tagName === 'INPUT') return;
  if (ddKeys(e)) return;
  const n = state.items.length;
  if (e.key === 'ArrowDown' && n) {
    const i = state.items.findIndex(x => x.id === state.current?.id);
    select(state.items[(i + 1) % n].id); e.preventDefault();
  } else if (e.key === 'ArrowUp' && n) {
    const i = state.items.findIndex(x => x.id === state.current?.id);
    select(state.items[(i - 1 + n) % n].id); e.preventDefault();
  } else if (e.key === 'ArrowRight' && state.ig && igSlides().length > 1 && e.shiftKey) {
    slideIG(1); e.preventDefault();
  } else if (e.key === 'ArrowLeft' && state.ig && igSlides().length > 1 && e.shiftKey) {
    slideIG(-1); e.preventDefault();
  } else if (e.key === 'ArrowRight' && state.variants.length) {
    state.variant = (state.variant + 1) % state.variants.length;
    renderVariants(); drawOverlay(); play('select', .6); e.preventDefault();
  } else if (e.key === 'ArrowLeft' && state.variants.length) {
    state.variant = (state.variant - 1 + state.variants.length) % state.variants.length;
    renderVariants(); drawOverlay(); play('select', .6); e.preventDefault();
  } else if (e.key === 'Escape') {
    closeMeta();
    toggleInfo(false);
  } else if (e.key === 'Enter') {
    exportOne();
  }
}

function updateInfo() {
  const it = state.current;
  if (!it) return;
  const v = state.variants[state.variant];
  const sp = state.split;
  const piezas = (state.tab === 'split' && sp?.pieces?.length)
    ? `${sp.pieces.length} piezas de ${sp.pieces[0].size[0]}x${sp.pieces[0].size[1]} px<br>`
    : '';
  const color = it.converted ? `${it.profile} → sRGB` : it.profile;
  $('#info').innerHTML =
    `<b>${it.name}</b><br>` +
    `${it.size[0]} x ${it.size[1]} px<br>` +
    `${it.faces.length} cara(s) detectada(s)<br>` +
    `${color}<br>` +
    piezas;
}
