// ─── Constantes ───────────────────────────────────────────────────────────────
const DOW      = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
const DOW_FULL = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];
const CUTOFF   = 990;   // 16:30 en minutos
const NOMBRES_MESES = ['enero','febrero','marzo','abril','mayo','junio',
                        'julio','agosto','septiembre','octubre','noviembre','diciembre'];


// ─── Estado global ────────────────────────────────────────────────────────────
let state = {
  vehiculos:      [],
  serverStats:    null,
  loaded:         false,
  view:           'diagnostico',
  filterMunProm:  '',
  filterEstProm:  '',
  searchProm:     '',
  filterMunVeh:   '',
  searchVeh:      '',
  editTarget:     null,
  progConfig:     null, // Guarda {start_date, end_date, placas} de la última programación generada
  historial:      []
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
const m2s = m => `${Math.floor(m / 60).toString().padStart(2, "0")}:${(m % 60).toString().padStart(2, "0")}`;

const getBestDay = v => {
  let best = null, bestMin = Infinity;
  for (let d = 0; d <= 6; d++) {
    const e = v.horaDow && v.horaDow[d];
    if (e && e.m <= CUTOFF && e.m < bestMin) { bestMin = e.m; best = d; }
  }
  return best;
};

const cellCls = m => m <= 870 ? "ideal" : m <= 930 ? "good" : m <= 990 ? "ok" : m <= 1020 ? "late" : "bad";
const bCls    = n => n === 0 ? "b-crit" : n === 1 ? "b-warn" : "b-ok";
const bTxt    = n => n === 0 ? "Crítico" : n === 1 ? "Bajo" : "OK";


// ─── MEJORA #3: stats siempre del servidor ───────────────────────────────────
function getStats() {
  // Si tenemos stats del servidor, usarlos (n_meses real del CSV)
  if (state.serverStats) return state.serverStats;
  // Fallback: calcular en cliente (sin n_meses real)
  const total     = state.vehiculos.length;
  const sinLav    = state.vehiculos.filter(v => v.lavGen === 0).length;
  const meta      = total * 3;
  const realizados = state.vehiculos.reduce((a, v) => a + v.lavGen, 0);
  const deficit   = Math.max(0, meta - realizados);
  const cumplimiento = total > 0 ? ((realizados / meta) * 100).toFixed(1) : 0;
  return { total_veh: total, sin_gen: sinLav, meta, total_gen: realizados, deficit, pct_cum: cumplimiento, pendientes: deficit };
}

const INVALID_MUNS = new Set(['N/D', '0', '0.0', '0:00', '00:00', 'NAN', 'NONE', '']);

function getMunicipios() {
  return [...new Set(state.vehiculos.map(v => v.mun).filter(m => m && !INVALID_MUNS.has(m.toUpperCase())))].sort();
}

// ─── Carga inicial ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const [dataRes, statsRes, tarifasRes] = await Promise.all([
      fetch('/api/data'),
      fetch('/api/stats'),
      fetch('/api/config/tarifas')
    ]);
    const data     = await dataRes.json();
    const stats    = await statsRes.json();
    const tarifas  = await tarifasRes.json();

    if (data && data.vehiculos) {
      state.vehiculos   = data.vehiculos;
      state.historial   = data.historial_lavados || [];
      state.historial_lavados = state.historial;
      state.lavadores_stats = data.lavadores_stats || {};
    }
    if (stats && !stats.error) {
      state.serverStats = stats;
    }
    if (tarifas && !tarifas.error) {
      state._tarifas = tarifas; // { General: 20000, Sencillo: 15000, Enjuague: 0 }
    }
  } catch (e) {
    console.error("Error cargando datos:", e);
    state.vehiculos = [];
  }

  state.loaded = true;
  document.getElementById('loadingState').style.display = 'none';
  document.getElementById('mainContent').style.display  = 'block';

  populateFilters();
  updateUI();
});

// ─── Actualización de estado ──────────────────────────────────────────────────
async function updateVehiculos(dbResponse) {
  // La API devuelve el objeto completo: { vehiculos, stats, chartData }
  if (dbResponse && dbResponse.vehiculos) {
    state.vehiculos   = dbResponse.vehiculos;
    state.serverStats = dbResponse.stats || null;
    state.historial   = dbResponse.historial_lavados || [];
    state.lavadores_stats = dbResponse.lavadores_stats || {};
  } else if (Array.isArray(dbResponse)) {
    state.vehiculos = dbResponse;
    // Refrescar stats del servidor
    try {
      const r = await fetch('/api/stats');
      const s = await r.json();
      if (!s.error) state.serverStats = s;
    } catch {}
  }
  populateFilters();
  updateUI();
}

// ─── Render general ───────────────────────────────────────────────────────────
function updateUI() {
  const stats = getStats();

  // Sidebar footer
  document.getElementById('ftTotal').textContent       = stats.total_veh ?? stats.total ?? '—';
  document.getElementById('ftSinLav').textContent      = stats.sin_gen   ?? stats.sinLav ?? '—';
  document.getElementById('ftCumplimiento').textContent = (stats.pct_cum ?? stats.cumplimiento ?? '—') + '%';
  document.getElementById('ftRealizados').textContent  = stats.total_gen ?? stats.realizados ?? '—';

  // Topbar
  document.getElementById('tbSub').textContent = `Zona Urabá · ${stats.total_veh ?? stats.total ?? 0} vehículos`;
  const pendientes = stats.deficit ?? stats.pendientes ?? 0;
  const tbBadge = document.getElementById('tbBadge');
  tbBadge.style.display = pendientes > 0 ? 'flex' : 'none';
  document.getElementById('tbBadgeText').textContent = `${pendientes} lavados generales pendientes`;

  // KPIs
  const realizados   = stats.total_gen   ?? stats.realizados ?? 0;
  const meta         = stats.meta        ?? 0;
  const deficit      = stats.deficit     ?? 0;
  const sinLav       = stats.sin_gen     ?? stats.sinLav ?? 0;
  const totalVeh     = stats.total_veh   ?? stats.total ?? 0;
  const cumplimiento = stats.pct_cum     ?? stats.cumplimiento ?? 0;

  document.getElementById('kpiRealizados').textContent     = realizados;
  document.getElementById('kpiMeta').textContent           = `meta: ${meta}`;
  document.getElementById('kpiDeficit').textContent        = deficit;
  document.getElementById('kpiSinLav').textContent         = sinLav;
  document.getElementById('kpiSinLavSub').textContent      = totalVeh > 0 ? ((sinLav / totalVeh) * 100).toFixed(1) + '% de la flota' : '0%';
  document.getElementById('kpiCumplimiento').textContent   = cumplimiento + '%';
  document.getElementById('kpiCumplimientoSub').textContent = `${realizados} de ${meta} requeridos`;

  renderDiagnostico();
  renderPromedios();
  renderVehiculos();
  renderHistorial();
  if (state.view === 'programacion') renderProgramacion();
  if (state.view === 'personal')     renderPersonal();
  if (state.view === 'lavados')      renderTodosLavados();
}

function populateFilters() {
  const muns = getMunicipios();
  const promMun = document.getElementById('promMun');
  const vehMun  = document.getElementById('vehMun');
  const selProm = promMun ? promMun.value : '';
  const selVeh  = vehMun  ? vehMun.value  : '';

  const opts = '<option value="">Todos los municipios</option>' +
               muns.map(m => `<option value="${m}">${m}</option>`).join('');
  if (promMun) { promMun.innerHTML = opts; if (muns.includes(selProm)) promMun.value = selProm; }
  if (vehMun)  { vehMun.innerHTML  = opts; if (muns.includes(selVeh))  vehMun.value  = selVeh; }
}

// ─── Navegación ───────────────────────────────────────────────────────────────
const VIEWS_TITLES = {
  diagnostico:   'Diagnóstico general',
  promedios:     'Promedios por día',
  programacion:  'Propuesta de programación',
  vehiculos:     'Gestión de vehículos',
  lavados:       'Todos los lavados',
  historial:     'Historial y Escáner QR',
  reportes:      'Centro de Reportes'
};

function showView(id, btnEl) {
  state.view = id;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
  document.getElementById(`view-${id}`).classList.add('active');
  document.getElementById('tbTitle').textContent = VIEWS_TITLES[id] || id;
  if (id === 'programacion') renderProgramacion();
  if (id === 'personal')     renderPersonal();
  if (id === 'lavados')      renderTodosLavados();
}

// ─── Vista Diagnóstico ────────────────────────────────────────────────────────
function renderDiagnostico() {
  const total = state.vehiculos.length;
  document.getElementById('diagTotalVeh').textContent = `${total} vehículos`;

  // Filtrar municipios inválidos: 'N/D', vacíos, numéricos, formatos de hora
  const INVALID_MUNS = new Set(['N/D', '0', '0.0', '0:00', '00:00', 'NAN', 'NONE', '']);
  const isValidMun = m => {
    if (!m) return false;
    const u = m.toUpperCase().trim();
    if (INVALID_MUNS.has(u)) return false;
    // Descartar strings que son solo dígitos o parecen horas (ej "12:34")
    if (/^\d+$/.test(u) || /^\d{1,2}:\d{2}$/.test(u)) return false;
    return true;
  };

  const n_meses = state.serverStats?.n_meses ?? 3;
  const muns = [...new Set(state.vehiculos.map(v => v.mun).filter(isValidMun))].sort();

  window.toggleMunRow = function(id, el) {
    const row = document.getElementById('munRow_' + id);
    if (row) {
      if (row.style.display === 'none') {
        row.style.display = 'table-row';
        el.querySelector('.arrow-icon').textContent = '▼';
      } else {
        row.style.display = 'none';
        el.querySelector('.arrow-icon').textContent = '▶';
      }
    }
  };

  document.getElementById('diagBody').innerHTML = muns.map(mun => {
    const vv  = state.vehiculos.filter(v => v.mun === mun);
    const lav = vv.reduce((a, v) => a + v.lavGen, 0);
    const sin = vv.filter(v => v.lavGen === 0).length;
    const meta = vv.length * n_meses;
    const pct  = meta > 0 ? ((lav / meta) * 100).toFixed(1) : 0;
    const barCls  = parseFloat(pct) < 33 ? 'crit' : parseFloat(pct) < 66 ? 'warn' : 'ok';
    const badgeCls = sin > 0 ? 'b-crit' : 'b-ok';
    
    // Lista de vehículos
    const vehiculosList = vv.map(v => `<span class="badge b-info" style="margin:2px">${v.placa}</span>`).join('');
    const idSaf = mun.replace(/[^a-zA-Z0-9]/g, '_');

    return `
      <tr onclick="toggleMunRow('${idSaf}', this)" style="cursor:pointer; transition: background 0.2s;" onmouseover="this.style.background='var(--bg)'" onmouseout="this.style.background='transparent'">
        <td style="font-weight:500"><span class="arrow-icon" style="font-size:10px; color:var(--muted); margin-right:4px;">▶</span> ${mun}</td>
        <td><span class="badge b-info">${vv.length}</span></td>
        <td><span style="font-family:var(--mono);font-size:13px">${lav}</span></td>
        <td><span class="badge ${badgeCls}">${sin}</span></td>
        <td>
          <div class="bar-wrap">
            <div class="bar-bg"><div class="bar-fill ${barCls}" style="width:${pct}%"></div></div>
            <span style="font-family:var(--mono);font-size:11px;color:var(--muted)">${pct}%</span>
          </div>
        </td>
      </tr>
      <tr id="munRow_${idSaf}" style="display:none; background:var(--bg);">
        <td colspan="5" style="padding:16px;">
          <div style="font-size:12px; font-weight:600; color:var(--muted); margin-bottom:8px;">Vehículos asignados en ${mun} (${vv.length}):</div>
          <div style="display:flex; flex-wrap:wrap; gap:4px;">${vehiculosList}</div>
        </td>
      </tr>`;
  }).join('');
}

// ─── Vista Promedios (Heatmap) ────────────────────────────────────────────────
function renderPromedios() {
  state.filterMunProm = document.getElementById('promMun').value;
  state.filterEstProm = document.getElementById('promEst').value;
  state.searchProm    = document.getElementById('promSearch').value.toLowerCase();
  const n_meses       = state.serverStats?.n_meses ?? 3;

  let data = [...state.vehiculos];
  if (state.filterMunProm) data = data.filter(v => v.mun === state.filterMunProm);
  if (state.filterEstProm === 'critico') data = data.filter(v => v.lavGen === 0);
  if (state.filterEstProm === 'con')     data = data.filter(v => v.lavGen > 0);
  if (state.searchProm)   data = data.filter(v => v.placa.toLowerCase().includes(state.searchProm));

  document.getElementById('promCount').textContent = `${data.length} vehículos`;

  document.getElementById('promBody').innerHTML = data.map(v => {
    const best = getBestDay(v);
    const pct  = Math.min((v.lavGen / n_meses) * 100, 100);
    const bc   = v.lavGen === 0 ? "crit" : v.lavGen === 1 ? "warn" : "ok";

    let dowCells = '';
    for (let d = 0; d < 7; d++) {
      const e = v.horaDow && v.horaDow[d];
      if (e) {
        const cls     = cellCls(e.m);
        const outline = d === best ? 'style="outline:2px solid var(--em);outline-offset:1px"' : '';
        // MEJORA: mostrar desviación estándar en tooltip si está disponible
        const stdTip  = e.std ? ` title="σ = ±${Math.round(e.std)} min"` : '';
        dowCells += `<td><div class="dc ${cls}" ${outline}${stdTip}><span class="t">${e.s}</span><span class="c">${e.n} reg.</span></div></td>`;
      } else {
        dowCells += `<td><div class="dc empty">—</div></td>`;
      }
    }

    return `
      <tr>
        <td><span class="placa">${v.placa}</span></td>
        <td style="font-size:11px;color:var(--muted)">${v.mun}</td>
        <td>
          <div class="bar-wrap">
            <div class="bar-bg"><div class="bar-fill ${bc}" style="width:${pct}%"></div></div>
            <span style="font-family:var(--mono);font-size:11px;color:var(--muted)">${v.lavGen}/${n_meses}</span>
            <span class="badge ${bCls(v.lavGen)}" style="font-size:9px">${bTxt(v.lavGen)}</span>
          </div>
        </td>
        ${dowCells}
        <td>
          ${best !== null
            ? `<span style="font-size:10px;font-weight:700;color:var(--em);background:var(--em-dim);padding:2px 6px;border-radius:4px">${DOW_FULL[best]}</span>`
            : `<span style="font-size:10px;color:var(--muted2)">N/D</span>`}
        </td>
      </tr>`;
  }).join('');
}

// ─── Vista Personal y Rendimiento ─────────────────────────────────────────────
async function exportarNominaPdf() {
  const desde  = document.getElementById('personalDesde')?.value  || '';
  const hasta  = document.getElementById('personalHasta')?.value  || '';
  const resp   = document.getElementById('personalResponsable')?.value || 'Administrador';

  const btn = document.getElementById('btnExportNomina');
  if (btn) { btn.disabled = true; btn.innerHTML = '⏳ Generando PDF...'; }

  try {
    const res = await fetch('/api/exportar-nomina-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ desde, hasta, responsable: resp })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return showToast(err.error || 'Error al generar PDF', 'err');
    }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    const periodo = (desde && hasta) ? `${desde}_al_${hasta}` : (desde || hasta || 'completo');
    a.download = `Nomina_FlotaUraba_${periodo}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('📄 PDF de nómina generado ✓');
  } catch (e) {
    showToast('Error de conexión', 'err');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '📄 Exportar Nómina PDF'; }
  }
}

function renderPersonal() {
  _buildPersonalView(state.historial_lavados || []);
}

function _setQuincena(q) {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth();
  let desde, hasta;
  if (q === 1) {
    desde = new Date(y, m, 1);
    hasta = new Date(y, m, 15);
  } else if (q === 2) {
    desde = new Date(y, m, 16);
    hasta = new Date(y, m + 1, 0);
  } else {
    desde = new Date(y, m, 1);
    hasta = new Date(y, m + 1, 0);
  }
  document.getElementById('personalDesde').value = desde.toISOString().split('T')[0];
  document.getElementById('personalHasta').value = hasta.toISOString().split('T')[0];
  _buildPersonalView(state.historial_lavados || []);
}

function _buildPersonalView(historial) {
  const view = document.getElementById('view-personal');

  const TODOS_LAVADORES = [
    "ELIFELE SIMANCA",
    "HADER CORREA",
    "LUIS GOMEZ",
    "JAIDER MORENO",
    "MOISES GOMEZ",
    "JORGE ARROYO"
  ];

  // Leer fechas del filtro (preservar si ya existen)
  const desdeEl = document.getElementById('personalDesde');
  const hastaEl = document.getElementById('personalHasta');
  const desde = desdeEl ? desdeEl.value : '';
  const hasta = hastaEl ? hastaEl.value : '';

  // Filtrar historial (solo los que tienen lavador asignado y por fechas)
  let histFiltrado = historial.filter(h => h.lavador && h.lavador.trim() !== '');
  if (desde || hasta) {
    histFiltrado = histFiltrado.filter(h => {
      if (!h.fecha) return false;
      if (desde && h.fecha < desde) return false;
      if (hasta && h.fecha > hasta) return false;
      return true;
    });
  }

  // Tarifas guardadas en estado global (cargadas con loadTarifas)
  const tarifas = state._tarifas || {};

  // Agrupar por lavador (período filtrado)
  const lavadores = {};
  TODOS_LAVADORES.forEach(name => lavadores[name] = []);
  histFiltrado.forEach(h => {
    if (!h.lavador) return;
    const key = h.lavador.trim().toUpperCase();
    if (!lavadores[key]) lavadores[key] = [];
    lavadores[key].push(h);
  });

  const periodoLabel = (desde && hasta) ? `Del ${desde} al ${hasta}` :
                        desde ? `Desde ${desde}` :
                        hasta ? `Hasta ${hasta}` : 'Todo el historial';
  const totalRegistros = histFiltrado.length;

  let html = `
    <div class="sec-hdr" style="margin-top: 0; margin-bottom: 28px;">
      <div class="sec-title" style="font-size: 28px; font-weight: 800; letter-spacing:-0.02em; color:var(--text);">Registro de Lavadores</div>
      <div style="color: var(--muted); font-size: 15px; margin-top: 6px; font-weight:500;">Historial detallado de los vehículos gestionados por cada integrante del equipo.</div>
    </div>

    <!-- Panel de filtro de fechas -->
    <div style="background:var(--surface);border-radius:16px;border:1px solid var(--border);padding:20px 24px;margin-bottom:28px;box-shadow:var(--shadow-sm);">
      <div style="font-size:13px;font-weight:800;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);margin-bottom:16px;">📅 Filtrar por período</div>
      <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;">
        <div style="display:flex;flex-direction:column;gap:6px;">
          <label style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em;">Desde</label>
          <input type="date" id="personalDesde" value="${desde}" onchange="_buildPersonalView(state.historial_lavados||[])" style="padding:9px 12px;border:1px solid var(--border);border-radius:10px;font-family:var(--sans);font-size:14px;color:var(--text);background:var(--bg);outline:none;">
        </div>
        <div style="display:flex;flex-direction:column;gap:6px;">
          <label style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em;">Hasta</label>
          <input type="date" id="personalHasta" value="${hasta}" onchange="_buildPersonalView(state.historial_lavados||[])" style="padding:9px 12px;border:1px solid var(--border);border-radius:10px;font-family:var(--sans);font-size:14px;color:var(--text);background:var(--bg);outline:none;">
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button onclick="_setQuincena(1)" style="padding:9px 14px;border:1px solid var(--border);border-radius:10px;background:var(--bg);font-family:var(--sans);font-size:13px;font-weight:600;color:var(--text);cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background='var(--accent-dim)';this.style.borderColor='var(--accent)';this.style.color='var(--accent)';" onmouseout="this.style.background='var(--bg)';this.style.borderColor='var(--border)';this.style.color='var(--text)';">1ra Quincena</button>
          <button onclick="_setQuincena(2)" style="padding:9px 14px;border:1px solid var(--border);border-radius:10px;background:var(--bg);font-family:var(--sans);font-size:13px;font-weight:600;color:var(--text);cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background='var(--accent-dim)';this.style.borderColor='var(--accent)';this.style.color='var(--accent)';" onmouseout="this.style.background='var(--bg)';this.style.borderColor='var(--border)';this.style.color='var(--text)';">2da Quincena</button>
          <button onclick="_setQuincena(0)" style="padding:9px 14px;border:1px solid var(--border);border-radius:10px;background:var(--bg);font-family:var(--sans);font-size:13px;font-weight:600;color:var(--text);cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background='var(--accent-dim)';this.style.borderColor='var(--accent)';this.style.color='var(--accent)';" onmouseout="this.style.background='var(--bg)';this.style.borderColor='var(--border)';this.style.color='var(--text)';">Mes completo</button>
          <button onclick="document.getElementById('personalDesde').value='';document.getElementById('personalHasta').value='';_buildPersonalView(state.historial_lavados||[]);" style="padding:9px 14px;border:1px solid var(--border);border-radius:10px;background:var(--bg);font-family:var(--sans);font-size:13px;font-weight:600;color:var(--muted);cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background='var(--red-dim)';this.style.borderColor='var(--red)';this.style.color='var(--red)';" onmouseout="this.style.background='var(--bg)';this.style.borderColor='var(--border)';this.style.color='var(--muted)';">✕ Limpiar</button>
        </div>
      </div>
      <div style="margin-top:16px;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
          <span style="font-size:12px;background:var(--accent-dim);color:var(--accent);padding:4px 12px;border-radius:20px;font-weight:700;">${periodoLabel}</span>
          <span style="font-size:12px;color:var(--muted);font-weight:600;">${totalRegistros} lavado${totalRegistros !== 1 ? 's' : ''} en el período</span>
        </div>
        ${window.USER_ROLE === 'admin' ? `
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
          <div style="display:flex;flex-direction:column;gap:4px;">
            <label style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em;">Responsable del reporte</label>
            <input type="text" id="personalResponsable" placeholder="Nombre de quien firma..." style="padding:7px 12px;border:1px solid var(--border);border-radius:8px;font-family:var(--sans);font-size:13px;color:var(--text);background:var(--bg);outline:none;width:220px;">
          </div>
          <button id="btnExportNomina" onclick="exportarNominaPdf()" style="padding:10px 18px;border:none;border-radius:10px;background:linear-gradient(135deg,#16a34a,#15803d);color:#fff;font-family:var(--sans);font-size:13px;font-weight:700;cursor:pointer;transition:all 0.2s;box-shadow:0 4px 12px rgba(22,163,74,0.3);white-space:nowrap;" onmouseover="this.style.transform='translateY(-1px)';this.style.boxShadow='0 6px 16px rgba(22,163,74,0.4)';" onmouseout="this.style.transform='';this.style.boxShadow='0 4px 12px rgba(22,163,74,0.3)';">📄 Exportar Nómina PDF</button>
        </div>
        ` : ''}
      </div>
    </div>

    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 24px; padding-bottom: 40px;">
  `;

  for (const [name, lavados] of Object.entries(lavadores).sort((a,b) => a[0].localeCompare(b[0]))) {
    // Calcular pago para el período filtrado usando las tarifas actuales
    let pagoEstimado = 0;
    lavados.forEach(l => {
      const tipo = l.tipo_lavado || 'General';
      pagoEstimado += parseFloat(tarifas[tipo] || 0);
    });

    let listHtml = '';
    if (lavados.length === 0) {
      listHtml = `
        <div style="display:flex; justify-content:center; align-items:center; padding: 40px 0; color: var(--muted2); font-weight: 600; font-size: 14px; text-align: center; border: 2px dashed var(--border); border-radius: 12px; margin-bottom: 12px;">
          Sin lavados en este período
        </div>
      `;
    } else {
      listHtml = lavados.map((l, index) => {
        const tipo = l.tipo_lavado || 'General';
        let badgeBg = 'rgba(59,130,246,0.1)';
        let badgeColor = '#2563eb';
        if(tipo.toLowerCase().includes('sencillo')) { badgeBg = 'rgba(16,185,129,0.1)'; badgeColor = '#059669'; }
        if(tipo.toLowerCase().includes('enjuague')) { badgeBg = 'rgba(245,158,11,0.1)'; badgeColor = '#d97706'; }

        return `
          <div style="display:flex; justify-content:space-between; align-items:center; padding: 16px 0; border-bottom: ${index === lavados.length - 1 ? 'none' : '1px solid var(--border)'}; gap: 12px; transition: background 0.2s; border-radius: 8px;">
            <div style="display:flex; align-items:center; gap: 16px;">
              <div style="width:40px; height:40px; border-radius:10px; background:var(--bg); display:flex; align-items:center; justify-content:center; font-size:16px; border:1px solid var(--border2); box-shadow:0 2px 4px rgba(0,0,0,0.02);">🚐</div>
              <div>
                <div style="font-weight: 800; color: var(--text); font-size: 16px; letter-spacing: -0.01em;">${l.placa}</div>
                <div style="font-size: 12px; color: var(--muted); margin-top: 4px; font-weight: 500;">
                  <span style="display:inline-block; margin-right:8px;">📅 ${l.fecha}</span>
                  <span>⏱️ ${l.hora_inicio || '--'} a ${l.hora_fin || '--'}</span>
                </div>
              </div>
            </div>
            <div>
              <span style="font-size:11px; font-weight:700; padding:6px 14px; border-radius:20px; background: ${badgeBg}; color: ${badgeColor}; text-transform:uppercase; letter-spacing:0.05em;">${tipo}</span>
            </div>
          </div>
        `;
      }).join('');
    }

    html += `
      <div style="background: #ffffff; border-radius: 20px; box-shadow: 0 12px 30px rgba(0,0,0,0.04), 0 4px 6px rgba(0,0,0,0.02); overflow: hidden; border: 1px solid rgba(226, 232, 240, 0.8); transition: transform 0.3s ease, box-shadow 0.3s ease; display:flex; flex-direction:column; max-height:450px;" onmouseover="this.style.transform='translateY(-4px)'; this.style.boxShadow='0 20px 40px rgba(0,0,0,0.08), 0 8px 12px rgba(0,0,0,0.04)';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 12px 30px rgba(0,0,0,0.04), 0 4px 6px rgba(0,0,0,0.02)';">
        <div style="padding: 24px; background: linear-gradient(to right, #f8fafc, #ffffff); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; flex-shrink:0;">
          <div style="display: flex; align-items: center; gap: 16px;">
            <div style="width: 52px; height: 52px; border-radius: 16px; background: var(--blue-dim); color: var(--blue); display: flex; align-items: center; justify-content: center; font-size: 26px; box-shadow: inset 0 2px 4px rgba(255,255,255,0.5);">🧑‍🔧</div>
            <div>
              <div style="font-size: 19px; font-weight: 800; color: var(--text); letter-spacing: -0.02em;">${name}</div>
              <div style="font-size: 13px; color: var(--muted); font-weight: 600; margin-top: 2px;">Especialista de Lavado</div>
            </div>
          </div>
          <div style="display:flex; gap:12px;">
            <div style="text-align: right; background: var(--bg); padding: 8px 16px; border-radius: 12px; border: 1px solid var(--border2);">
              <div style="font-size: 16px; font-weight: 800; color: var(--green); line-height: 1;">$ ${pagoEstimado.toLocaleString('es-CO')}</div>
              <div style="font-size: 10px; text-transform: uppercase; color: var(--muted); font-weight: 800; letter-spacing: 0.05em; margin-top: 4px;">Nómina período</div>
            </div>
            <div style="text-align: right; background: var(--bg); padding: 8px 16px; border-radius: 12px; border: 1px solid var(--border2);">
              <div style="font-size: 16px; font-weight: 800; color: var(--blue); line-height: 1;">${lavados.length}</div>
              <div style="font-size: 10px; text-transform: uppercase; color: var(--muted); font-weight: 800; letter-spacing: 0.05em; margin-top: 4px;">Lavados</div>
            </div>
          </div>
        </div>
        <div style="padding: 0 24px; overflow-y: auto; flex-grow:1; margin-top: 16px;">
          ${listHtml}
        </div>
      </div>
    `;
  }
  
  html += '</div>';
  view.innerHTML = html;
}

// ─── Vista Programación Kanban ────────────────────────────────────────────────
function initFechasProg() {
  const sd = document.getElementById('progStartDate');
  const ed = document.getElementById('progEndDate');
  if (sd && !sd.value) {
    const today = new Date();
    sd.value = today.toISOString().split('T')[0];
    const nextWeek = new Date(today);
    nextWeek.setDate(today.getDate() + 6);
    ed.value = nextWeek.toISOString().split('T')[0];
  }
}

async function renderProgramacion() {
  initFechasProg();
  const startDate = document.getElementById('progStartDate').value;
  const endDate = document.getElementById('progEndDate').value;
  const filtroVeh = document.getElementById('progVehiculosFiltro').value;
  
  if (!startDate || !endDate) return showToast('Selecciona un rango de fechas', 'err');
  if (new Date(startDate) > new Date(endDate)) return showToast('La fecha de inicio debe ser anterior a la de fin', 'err');

  const body = document.getElementById('progBody');
  body.innerHTML = `<div style="color:var(--muted);font-size:13px;padding:20px;width:100%;text-align:center;">Calculando programación…</div>`;

  let placas = [];
  if (filtroVeh === 'sin_lavado') {
    placas = state.vehiculos.filter(v => v.lavGen === 0).map(v => v.placa);
  }

  try {
    const res = await fetch('/api/programacion', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start_date: startDate, end_date: endDate, placas })
    });
    const data = await res.json();
    if (data.error) {
      body.innerHTML = `<div style="color:var(--red);font-size:13px;padding:20px">${data.error}</div>`;
      return;
    }
    
    // Guardar para exportar PDF luego
    state.progConfig = { start_date: startDate, end_date: endDate, placas };
    
    // Lista de fechas del rango
    const s = new Date(startDate + 'T12:00:00'); // T12 para evitar offset de timezone local
    const e = new Date(endDate + 'T12:00:00');
    const days = [];
    let curr = new Date(s);
    while (curr <= e) {
      days.push(curr.toISOString().split('T')[0]);
      curr.setDate(curr.getDate() + 1);
    }
    
    renderKanbanBoard(data.programacion, days);
    
    const pdfRango = document.getElementById('pdfRango');
    if (pdfRango) {
      pdfRango.textContent = `Del ${startDate} al ${endDate}`;
      pdfRango.style.background = '#e0f2fe';
      pdfRango.style.color = '#0284c7';
      pdfRango.style.borderColor = '#bae6fd';
    }
    
  } catch (err) {
    body.innerHTML = `<div style="color:var(--red);font-size:13px;padding:20px">Error al cargar la programación.</div>`;
  }
}

function renderKanbanBoard(prog, days) {
  const body = document.getElementById('progBody');
  
  const assigned = {};
  const unassigned = [];
  
  prog.forEach(v => {
    if (v.diaAsignado && days.includes(v.diaAsignado)) {
      if (!assigned[v.diaAsignado]) assigned[v.diaAsignado] = [];
      assigned[v.diaAsignado].push(v);
    } else {
      unassigned.push(v);
    }
  });

  const renderMiniCard = (v, d) => {
    // Rediseño minimalista: Fondo blanco, borde suave, línea lateral o punto
    const color = v.turno?.color || '#cbd5e1';
    
    // Generar texto para el tooltip (hover)
    let tooltipHTML = `
      <div class="tt-header">
        <i class="fas fa-bus" style="color: var(--accent);"></i> ${v.placa}
      </div>
      <div class="tt-body">
        <div class="tt-row"><span>Municipio:</span> <strong>${v.mun || 'N/D'}</strong></div>
        <div class="tt-row"><span>Ruta:</span> <strong>${v.ruta || 'N/D'}</strong></div>
    `;

    if (d && v.horaDow) {
      const dateObj = new Date(d + 'T12:00:00');
      const dow = dateObj.getDay();
      const hw = v.horaDow[String(dow)];
      if (hw && hw.s) {
        tooltipHTML += `
          <div class="tt-divider"></div>
          <div class="tt-highlight">
            <div><i class="fas fa-clock" style="color: var(--gold); margin-right: 4px;"></i> Hora esperada: <strong>${hw.s}</strong></div>
            <span class="tt-muted">Calculado basado en ${hw.n} registros históricos</span>
          </div>
        `;
      } else {
        tooltipHTML += `
          <div class="tt-divider"></div>
          <div class="tt-muted text-center"><i class="fas fa-info-circle"></i> Sin historial suficiente para predecir hora</div>
        `;
      }
    } else if (!d) {
      tooltipHTML += `
        <div class="tt-divider"></div>
        <div class="tt-muted text-center"><i class="fas fa-info-circle"></i> Asígnale un día para calcular hora esperada</div>
      `;
    }
    tooltipHTML += `</div>`; // close tt-body
    
    const draggableStr = window.USER_ROLE === 'admin' ? `draggable="true" ondragstart="onDragStart(event, '${v.placa}')" ondragend="onDragEnd(event)"` : '';
    const cursorStr = window.USER_ROLE === 'admin' ? 'cursor:grab;' : 'cursor:default;';
    
    return `
      <div class="prog-card mini tooltip-container" ${draggableStr} id="veh-${v.placa}" style="margin-bottom:8px;background:var(--surface);padding:12px;border-radius:10px;border:1px solid var(--border);box-shadow:var(--shadow-sm);${cursorStr}transition:transform 0.1s;position:relative;">
        <div class="custom-tooltip">${tooltipHTML}</div>
        <div style="position:absolute;left:0;top:10px;bottom:10px;width:3px;background:${color};border-radius:0 3px 3px 0;"></div>
        <div class="prog-placa" style="font-weight:600;font-size:14px;color:var(--text);display:flex;justify-content:space-between;align-items:center;padding-left:8px;">
           ${v.placa} 
           <span style="font-size:11px;color:var(--muted);background:var(--bg);padding:2px 6px;border-radius:6px;border:1px solid var(--border2);">${v.lavGen} lav.</span>
        </div>
        <div class="prog-meta" style="font-size:11px;color:var(--muted);margin-top:6px;padding-left:8px;">${v.mun} · ${v.ruta}</div>
      </div>
    `;
  };

  let html = '';
  
  // Columna: Sin asignar
  const dropUnassignedStr = window.USER_ROLE === 'admin' ? `ondragover="onDragOverUnassigned(event, this)" ondragleave="onDragLeaveUnassigned(event, this)" ondrop="onDrop(event, null)"` : '';
  
  html += `
    <div id="unassignedPanel" class="kanban-col" style="background:transparent;border-radius:12px;display:flex;flex-direction:column;height:100%;border:1px dashed var(--border2);transition:opacity 0.2s;"
         ${dropUnassignedStr}>
      <div style="font-size:13px;font-weight:600;margin-bottom:12px;color:var(--text);padding:12px 12px 0;">
        Vehículos sin asignar <span style="font-size:11px;color:var(--muted);float:right">${unassigned.length}</span>
      </div>
      <div style="overflow-y:auto;flex-grow:1;min-height:100px;padding:0 12px 12px;">
        ${unassigned.map(v => renderMiniCard(v, null)).join('')}
      </div>
    </div>
  `;
  
  // Columnas: Fechas
  days.forEach(d => {
    const items = assigned[d] || [];
    const dateObj = new Date(d + 'T12:00:00');
    const isFull = items.length >= 4;
    const dayLabel = `${DOW_FULL[dateObj.getDay()]} ${dateObj.getDate()} ${NOMBRES_MESES[dateObj.getMonth()].substr(0,3)}`;
    
    const dropStr = window.USER_ROLE === 'admin' ? `ondragover="onDragOver(event, this, ${items.length})" ondragleave="onDragLeave(event, this)" ondrop="onDrop(event, '${d}')"` : '';
    
    html += `
      <div class="kanban-col ${isFull ? 'full' : ''}" style="background:var(--surface);border-radius:12px;display:flex;flex-direction:column;height:100%;border:1px solid var(--border);transition:border-color 0.2s;"
           ${dropStr}
           data-day="${d}">
        <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;padding:12px 12px 0;">
          <span style="font-size:14px;font-weight:800;color:#fff;background:var(--accent);padding:8px 16px;border-radius:12px;box-shadow:0 4px 12px rgba(37,99,235,.25);letter-spacing:0.02em;text-transform:uppercase;">${dayLabel}</span>
          <span style="font-size:12px;font-weight:700;color:var(--text);background:var(--s2);padding:6px 12px;border-radius:8px;border:1px solid var(--border);">${items.length} / 4</span>
        </div>
        <div style="overflow-y:auto;flex-grow:1;min-height:100px;padding:0 12px 12px;">
          ${items.map(v => renderMiniCard(v, d)).join('')}
        </div>
      </div>
    `;
  });

  body.innerHTML = html;
  
  // Lógica de mostrar/ocultar "Sin asignar"
  const btn = document.getElementById('toggleUnassignedBtn');
  btn.style.display = 'inline-flex';
  const panel = document.getElementById('unassignedPanel');
  
  // Por defecto, si hay programación lista, esconder el panel de sin asignar
  if (Object.keys(assigned).length > 0) {
    panel.style.display = 'none';
    btn.textContent = 'Mostrar Vehículos Sin Asignar';
  } else {
    panel.style.display = 'flex';
    btn.textContent = 'Ocultar Vehículos Sin Asignar';
  }
}

window.toggleUnassigned = function() {
  const panel = document.getElementById('unassignedPanel');
  const btn = document.getElementById('toggleUnassignedBtn');
  if (!panel) return;
  if (panel.style.display === 'none') {
    panel.style.display = 'flex';
    btn.textContent = 'Ocultar Vehículos Sin Asignar';
  } else {
    panel.style.display = 'none';
    btn.textContent = 'Mostrar Vehículos Sin Asignar';
  }
}

// Drag & Drop Kanban
let draggedPlaca = null;

window.onDragStart = function(e, placa) {
  draggedPlaca = placa;
  e.dataTransfer.effectAllowed = 'move';
  setTimeout(() => e.target.style.opacity = '0.5', 0);
};

window.onDragEnd = function(e) {
  e.target.style.opacity = '1';
  document.querySelectorAll('.kanban-col').forEach(el => {
    el.style.borderColor = el.classList.contains('full') ? '#e2e8f0' : (el.style.borderStyle === 'dashed' ? '#e2e8f0' : '#e2e8f0');
    el.style.backgroundColor = el.style.borderStyle === 'dashed' ? '#f8fafc' : '#f1f5f9';
  });
  draggedPlaca = null;
};

window.onDragOver = function(e, el, currentItems) {
  if (currentItems >= 4) {
    e.dataTransfer.dropEffect = 'none';
    return false;
  }
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  el.style.borderColor = 'var(--blue)';
  el.style.backgroundColor = '#e0f2fe';
};

window.onDragLeave = function(e, el) {
  el.style.borderColor = '#e2e8f0';
  el.style.backgroundColor = '#f1f5f9';
};

window.onDragOverUnassigned = function(e, el) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  el.style.borderColor = 'var(--red)';
  el.style.backgroundColor = '#fef2f2';
};

window.onDragLeaveUnassigned = function(e, el) {
  el.style.borderColor = '#e2e8f0';
  el.style.backgroundColor = '#f8fafc';
};

window.onDrop = async function(e, nuevoDia) {
  e.preventDefault();
  
  if (!draggedPlaca) return;

  const msg = nuevoDia ? `Asignando ${draggedPlaca} al ${nuevoDia}...` : `Moviendo ${draggedPlaca} a sin asignar...`;
  showToast(msg);

  try {
    const res = await fetch('/api/programacion/update_fecha', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        placa: draggedPlaca,
        nuevo_dia: nuevoDia
      })
    });
    const data = await res.json();
    if (data.error) {
      showToast(data.error, 'err');
    } else {
      renderProgramacion(); 
      showToast('Programación actualizada ✓');
    }
  } catch (err) {
    showToast('Error al guardar fecha', 'err');
  }
  
  draggedPlaca = null;
};

// ─── Vista Vehículos ──────────────────────────────────────────────────────────
function renderVehiculos() {
  state.filterMunVeh = document.getElementById('vehMun').value;
  state.searchVeh    = document.getElementById('vehSearch').value.toLowerCase();

  let data = [...state.vehiculos];
  if (state.filterMunVeh) data = data.filter(v => v.mun === state.filterMunVeh);
  if (state.searchVeh)    data = data.filter(v => v.placa.toLowerCase().includes(state.searchVeh));

  document.getElementById('vehCount').textContent = `${data.length} vehículos`;

  document.getElementById('vehBody').innerHTML = data.map(v => `
    <tr>
      <td><span class="placa">${v.placa}</span></td>
      <td>${v.mun}</td>
      <td style="font-size:11px;color:var(--muted)">${v.tipo}</td>
      <td style="font-size:11px;color:var(--muted)">${v.ruta}</td>
      <td style="font-size:11px;color:var(--muted)">${v.sup}</td>
      <td style="font-family:var(--mono);font-size:11px">${v.ultimo}</td>
      <td style="font-family:var(--mono);font-size:14px;font-weight:600">${v.lavGen}</td>
      ${window.USER_ROLE === 'admin' ? `
      <td style="text-align:right">
        <button class="act-btn wash" onclick="quitarLavado('${v.placa}')">−</button>
        <button class="act-btn wash" onclick="sumarLavado('${v.placa}')">+</button>
        <button class="act-btn qr"   onclick="showQR('${v.placa}')" title="Ver QR para registro en campo">QR</button>
        <button class="act-btn edit" onclick="editVehicle('${v.placa}')" style="margin-left:6px">Editar</button>
        <button class="act-btn del"  onclick="deleteVehicle('${v.placa}')">Eliminar</button>
      </td>` : ''}
    </tr>`).join('');
}

// ─── Modales ──────────────────────────────────────────────────────────────────
function openModal(id) {
  document.getElementById(id).classList.add('open');
  if (id === 'modalVehicle' && !state.editTarget) {
    document.getElementById('mvTitle').textContent = 'Agregar vehículo';
    document.getElementById('mvSub').textContent   = 'Ingresa los datos del nuevo vehículo.';
    document.getElementById('formVehicle').reset();
    document.getElementById('mvPlaca').readOnly = false;
  }
  if (id === 'modalQR') return; // QR modal is managed by showQR()
}

// ─── QR: mostrar, descargar e imprimir ───────────────────────────────────────
let _qrPlacaActual = null;

function showQR(placa) {
  _qrPlacaActual = placa;

  // Limpiar QR anterior
  const canvas = document.getElementById('qrCanvas');
  canvas.innerHTML = '';

  // URL de registro (usar IP real de la red para que los móviles puedan acceder)
  const url = `${window.location.origin}/registro/${placa}`;
  document.getElementById('qrTitleText').textContent = `Código QR — ${placa}`;
  document.getElementById('qrUrlText').textContent   = url;

  // Generar QR (oscuro sobre blanco para imprimir bien)
  new QRCode(canvas, {
    text:          url,
    width:         220,
    height:        220,
    colorDark:     '#0D1117',
    colorLight:    '#FFFFFF',
    correctLevel:  QRCode.CorrectLevel.H
  });

  document.getElementById('modalQR').classList.add('open');
}

function _getQRImageSrc() {
  const container = document.getElementById('qrCanvas');
  const c = container.querySelector('canvas');
  const i = container.querySelector('img');
  return c ? c.toDataURL('image/png') : (i ? i.src : null);
}

function downloadCurrentQR() {
  if (!_qrPlacaActual) return;
  const src = _getQRImageSrc();
  if (!src) return showToast('No se pudo generar la imagen', 'err');
  const link = document.createElement('a');
  link.download = `QR-Lavado-${_qrPlacaActual}.png`;
  link.href = src;
  link.click();
  showToast(`QR de ${_qrPlacaActual} descargado`);
}

function printCurrentQR() {
  if (!_qrPlacaActual) return;
  const src = _getQRImageSrc();
  const url = `${window.location.origin}/registro/${_qrPlacaActual}`;
  const placa = _qrPlacaActual;

  const win = window.open('', '_blank', 'width=480,height=640');
  win.document.write(`
    <!DOCTYPE html><html lang="es"><head>
    <meta charset="UTF-8">
    <title>QR — ${placa}</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;800&display=swap" rel="stylesheet">
    <style>
      * { margin:0; padding:0; box-sizing:border-box; }
      body { font-family:'Plus Jakarta Sans',sans-serif; background:#fff; display:flex; align-items:center; justify-content:center; min-height:100vh; }
      .card { border: 2px solid #e0e0e0; border-radius: 20px; padding: 36px 32px; text-align:center; max-width:340px; width:100%; }
      .brand { font-size:12px; color:#888; margin-bottom:16px; letter-spacing:.05em; text-transform:uppercase; }
      .placa { font-size:40px; font-weight:800; letter-spacing:.12em; font-family:monospace; color:#1a1a2e; margin-bottom:6px; }
      .sub { font-size:12px; color:#555; margin-bottom:20px; }
      img { border-radius:12px; border:1px solid #eee; }
      .url { font-size:9px; color:#888; margin-top:14px; word-break:break-all; font-family:monospace; }
      .footer { font-size:10px; color:#bbb; margin-top:16px; }
      @media print { body { min-height:auto; } .card { border:none; } }
    </style>
    </head><body>
    <div class="card">
      <div class="brand">Flota Urabá · Registro de Lavado</div>
      <div class="placa">${placa}</div>
      <div class="sub">Escanea para registrar lavado general</div>
      <img src="${src}" width="220" height="220" alt="QR ${placa}">
      <div class="url">${url}</div>
      <div class="footer">Sistema de Gestión de Lavados — Zona Urabá</div>
    </div>
    <script>window.onload = () => { setTimeout(() => window.print(), 400); }<\/script>
    </body></html>
  `);
  win.document.close();
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
  state.editTarget = null;
}

function showToast(msg, type = "good") {
  const toast = document.getElementById('toast');
  const msgEl = document.getElementById('toastMsg');
  if (msgEl) msgEl.textContent = msg; else toast.textContent = msg;
  toast.className = `toast open ${type}`;
  setTimeout(() => { toast.className = 'toast'; }, 3500);
}

// ─── CRUD Vehículos (frontend) ────────────────────────────────────────────────
async function saveVehicle(e) {
  e.preventDefault();
  const vData = {
    placa: document.getElementById('mvPlaca').value.toUpperCase(),
    mun:   document.getElementById('mvMun').value.toUpperCase(),
    tipo:  document.getElementById('mvTipo').value.toUpperCase(),
    ruta:  document.getElementById('mvRuta').value.toUpperCase(),
    sup:   document.getElementById('mvSup').value.toUpperCase()
  };

  const url = state.editTarget ? '/api/vehiculo/edit' : '/api/vehiculo/add';
  try {
    const res    = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(vData) });
    const result = await res.json();
    if (result.error) {
      showToast(result.error, 'err');
    } else {
      showToast(state.editTarget ? `Vehículo ${vData.placa} actualizado` : `Vehículo ${vData.placa} agregado`);
      await updateVehiculos(result);
      closeModal('modalVehicle');
    }
  } catch { showToast('Error de conexión', 'err'); }
}

function editVehicle(placa) {
  const v = state.vehiculos.find(x => x.placa === placa);
  if (!v) return;
  state.editTarget = placa;
  document.getElementById('mvTitle').textContent  = 'Editar vehículo';
  document.getElementById('mvSub').textContent    = `Modificando datos de ${placa}.`;
  document.getElementById('mvPlaca').value        = v.placa;
  document.getElementById('mvPlaca').readOnly     = true;
  document.getElementById('mvMun').value          = v.mun;
  document.getElementById('mvTipo').value         = v.tipo;
  document.getElementById('mvRuta').value         = v.ruta;
  document.getElementById('mvSup').value          = v.sup;
  openModal('modalVehicle');
}

function deleteVehicle(placa) {
  document.getElementById('mcMsg').textContent = `¿Eliminar el vehículo ${placa}?`;
  openModal('modalConfirm');
  document.getElementById('mcBtn').onclick = async () => {
    try {
      const res    = await fetch('/api/vehiculo/remove', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ placa }) });
      const result = await res.json();
      if (result.error) { showToast(result.error, 'err'); }
      else { showToast(`Vehículo ${placa} eliminado`, 'err'); await updateVehiculos(result); closeModal('modalConfirm'); }
    } catch { showToast('Error', 'err'); }
  };
}

// ─── Lavados ──────────────────────────────────────────────────────────────────
async function saveLavado(e) {
  e.preventDefault();
  const placa = document.getElementById('mlPlaca').value.toUpperCase();
  const fecha = document.getElementById('mlFecha').value;
  const hora_inicio  = document.getElementById('mlHoraInicio').value;
  const hora_fin = document.getElementById('mlHoraFin').value;
  const tipo_lavado = document.getElementById('mlTipoLavado').value;
  const lavador = document.getElementById('mlLavador').value;

  try {
    const res    = await fetch('/api/lavado/add_manual', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ placa, fecha, hora_inicio, hora_fin, tipo_lavado, lavador }) });
    const result = await res.json();
    if (result.error) { showToast(result.error, 'err'); }
    else { showToast(`Lavado registrado para ${placa}`); await updateVehiculos(result); closeModal('modalLavado'); }
  } catch { showToast('Error al registrar lavado', 'err'); }
}

async function sumarLavado(placa) {
  try {
    const res    = await fetch('/api/lavado/add', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ placa, tipo:'lavGen' }) });
    const result = await res.json();
    if (result.error) showToast(result.error, 'err');
    else { await updateVehiculos(result); showToast('Lavado general añadido ✓'); }
  } catch {}
}

async function quitarLavado(placa) {
  try {
    const res    = await fetch('/api/lavado/remove', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ placa, tipo:'lavGen' }) });
    const result = await res.json();
    if (result.error) showToast(result.error, 'err');
    else { await updateVehiculos(result); showToast('Lavado general removido', 'err'); }
  } catch {}
}

async function importCSV(e) {
  e.preventDefault();
  const fileInput = document.getElementById('miFile');
  if (!fileInput.files.length) return;

  const btn = document.getElementById('miBtn');
  btn.disabled   = true;
  btn.textContent = 'Procesando…';

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  try {
    const res  = await fetch('/upload', { method:'POST', body:formData });
    const data = await res.json();
    if (data.error) { showToast(data.error, 'err'); }
    else { showToast('Datos importados correctamente ✓'); await updateVehiculos(data); closeModal('modalImport'); }
  } catch { showToast('Error de conexión', 'err'); }
  finally {
    btn.disabled    = false;
    btn.textContent = 'Procesar e Importar';
    document.getElementById('formImport').reset();
  }
}

// ─── PDF Export ───────────────────────────────────────────────────────────────


async function descargarPDF(tipo_reporte, btnEl) {
  let start_date, end_date, placas = [], maxDia = 4, responsable = '';
  const today = new Date().toISOString().split('T')[0];

  if (tipo_reporte === 'programacion') {
    if (!state.progConfig) {
      return showToast('Primero genera la programación en la pestaña "Propuesta de programación"', 'err');
    }
    start_date  = state.progConfig.start_date;
    end_date    = state.progConfig.end_date;
    placas      = state.progConfig.placas;
    maxDia      = document.getElementById('pdfMaxDia')?.value || 4;
    responsable = (document.getElementById('pdfRespProg')?.value.trim() || '');
  } else if (tipo_reporte === 'diagnostico') {
    start_date  = today;
    end_date    = today;
    responsable = (document.getElementById('pdfRespDiag')?.value.trim() || '');
  } else if (tipo_reporte === 'lavadores') {
    start_date  = today;
    end_date    = today;
    responsable = (document.getElementById('pdfRespLav')?.value.trim() || '');
  } else if (tipo_reporte === 'flota') {
    start_date  = today;
    end_date    = today;
    responsable = (document.getElementById('pdfRespFlota')?.value.trim() || '');
  }

  const originalText = btnEl.innerHTML;
  btnEl.disabled = true;
  btnEl.innerHTML = '⏳ Generando…';

  try {
    const res = await fetch(`/exportar-pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start_date, end_date, placas, max_dia: maxDia, responsable, tipo_reporte })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Error desconocido' }));
      showToast(err.error || 'Error al generar el PDF', 'err');
      return;
    }

    const blob   = await res.blob();
    const objUrl = URL.createObjectURL(blob);
    const link   = document.createElement('a');
    link.href    = objUrl;
    const nombres = {
      diagnostico: `Diagnostico_${today}.pdf`,
      programacion: `Programacion_${start_date}_al_${end_date}.pdf`,
      lavadores: `Lavadores_${today}.pdf`,
      flota: `Flota_${today}.pdf`
    };
    link.download = nombres[tipo_reporte] || `Reporte_${today}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(objUrl);
    showToast('✓ PDF descargado correctamente');
  } catch (e) {
    showToast('Error de conexión al generar el PDF', 'err');
  } finally {
    btnEl.disabled  = false;
    btnEl.innerHTML = originalText;
  }
}

// ─── Historial y Escáner QR ───────────────────────────────────────────────────
function renderHistorial() {
  const data = state.historial || [];
  document.getElementById('histCount').textContent = `${data.length} registros`;

  document.getElementById('histBody').innerHTML = data.map(r => {
    let origenHtml = r.origen === 'qr_registro' ? '<span class="badge b-ok" style="font-size:10px">QR Público</span>' : 
                     r.origen === 'dashboard_sumar' ? '<span class="badge b-warn" style="font-size:10px">App (Botón +)</span>' : 
                     '<span class="badge b-info" style="font-size:10px">Manual</span>';
                     
    const tipo = r.tipo_lavado || 'General';
    const lavador = r.lavador || 'N/D';
    const horas = (r.hora_inicio && r.hora_fin) ? `${r.hora_inicio} - ${r.hora_fin}` : (r.hora || 'N/D');
    
    return `
      <tr>
        <td><span class="placa">${r.placa}</span></td>
        <td>${tipo}</td>
        <td>${lavador}</td>
        <td style="font-family:var(--mono)">${r.fecha}</td>
        <td style="font-family:var(--mono);font-weight:600">${horas}</td>
        <td>${origenHtml}</td>
      </tr>
    `;
  }).join('');
}

let html5QrcodeScanner = null;

function startQRScanner() {
  document.getElementById('qr-reader-container').style.display = 'block';
  if (!html5QrcodeScanner) {
    html5QrcodeScanner = new Html5QrcodeScanner(
      "qr-reader",
      { fps: 10, qrbox: {width: 250, height: 250} },
      /* verbose= */ false
    );
  }
  
  html5QrcodeScanner.render(onScanSuccess, onScanFailure);
}

function stopQRScanner() {
  if (html5QrcodeScanner) {
    html5QrcodeScanner.clear().then(() => {
      document.getElementById('qr-reader-container').style.display = 'none';
    }).catch(error => {
      console.error("Failed to clear html5QrcodeScanner. ", error);
      document.getElementById('qr-reader-container').style.display = 'none';
    });
  } else {
    document.getElementById('qr-reader-container').style.display = 'none';
  }
}

function onScanSuccess(decodedText, decodedResult) {
  // decodedText should be something like http://127.0.0.1:5001/registro/ABC123
  const parts = decodedText.split('/');
  const placa = parts[parts.length - 1].trim().toUpperCase();
  
  if (placa && placa.length >= 5 && placa.length <= 7) {
    stopQRScanner();
    // Redirigir directamente a la página de registro QR para que mantenga el origen 'qr_registro' y notifique
    window.location.href = `/registro/${placa}`;
  } else {
    showToast('QR no reconocido o placa inválida', 'err');
  }
}

function onScanFailure(error) {
  // Ignore errors as it parses each frame
}

// ─── Vista: Todos los Lavados ──────────────────────────────────────────────
function renderTodosLavados() {
  const historial = state.historial || [];
  const filterTipo = document.getElementById('lavTipo')?.value || '';
  const filterLav  = document.getElementById('lavPersonal')?.value || '';
  const filterMun  = document.getElementById('lavMun2')?.value || '';
  const search     = (document.getElementById('lavSearch')?.value || '').toLowerCase();

  // Build municipio map
  const munMap = {};
  (state.vehiculos || []).forEach(v => munMap[v.placa] = v.mun);

  let data = [...historial];
  if (filterTipo) data = data.filter(h => (h.tipo_lavado || 'General') === filterTipo);
  if (filterLav)  data = data.filter(h => h.lavador === filterLav);
  if (filterMun)  data = data.filter(h => munMap[h.placa] === filterMun);
  if (search)     data = data.filter(h =>
    (h.placa || '').toLowerCase().includes(search) ||
    (h.lavador || '').toLowerCase().includes(search)
  );

  const countEl = document.getElementById('lavCount');
  if (countEl) countEl.textContent = `${data.length} registros`;

  const origMap = {
    qr_registro:      'QR (campo)',
    dashboard_manual: 'Manual (app)',
    dashboard_sumar:  'Botón +'
  };

  const tipoCls = { General: 'b-ok', Sencillo: 'b-info', Enjuague: 'b-warn' };

  const bodyEl = document.getElementById('lavBody');
  if (!bodyEl) return;
  bodyEl.innerHTML = data.map(r => {
    const tipo   = r.tipo_lavado || 'General';
    const cls    = tipoCls[tipo] || 'b-info';
    const horas  = (r.hora_inicio && r.hora_fin) ? `${r.hora_inicio} — ${r.hora_fin}` : (r.hora || 'N/D');
    const mun    = munMap[r.placa] || 'N/D';
    const origen = origMap[r.origen] || r.origen || 'N/D';
    return `
      <tr>
        <td><span class="placa">${r.placa}</span></td>
        <td style="font-size:12px;color:var(--muted)">${mun}</td>
        <td><span class="badge ${cls}">${tipo}</span></td>
        <td style="font-weight:500">${r.lavador || 'N/D'}</td>
        <td style="font-family:var(--mono);font-size:12px">${r.fecha}</td>
        <td style="font-family:var(--mono);font-size:12px">${horas}</td>
        <td><span class="badge b-info" style="font-size:10px">${origen}</span></td>
      </tr>`;
  }).join('');
}

// ─── QR Polling & Alertas en Tiempo Real ──────────────────────────────────
let _lastQrTs = null;

// Pedir permiso para notificaciones nativas
if ('Notification' in window) {
  Notification.requestPermission();
}

// Función para generar un sonido "ding" usando Web Audio API
function playDing() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gainNode = ctx.createGain();
    
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime); // Nota A5
    osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.1);
    
    gainNode.gain.setValueAtTime(0.5, ctx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
    
    osc.connect(gainNode);
    gainNode.connect(ctx.destination);
    
    osc.start();
    osc.stop(ctx.currentTime + 0.5);
  } catch (e) {
    console.log('Audio error:', e);
  }
}

async function _initQrPolling() {
  // Capture current timestamp silently (no alert on first load)
  try {
    const res  = await fetch('/api/last-qr-event');
    const data = await res.json();
    if (data.event) _lastQrTs = data.event.timestamp;
  } catch(e) {}

  // Poll every 8 seconds
  setInterval(async () => {
    try {
      const res  = await fetch('/api/last-qr-event');
      const data = await res.json();
      if (data.event && data.event.timestamp !== _lastQrTs) {
        _lastQrTs = data.event.timestamp;
        _showQrAlert(data.event);
        // Refresh data
        const dr = await fetch('/api/data');
        const dd = await dr.json();
        if (dd && dd.vehiculos) {
          state.vehiculos = dd.vehiculos;
          state.historial = dd.historial_lavados || [];
          populateFilters();
          updateUI();
        }
      }
    } catch(e) {}
  }, 8000);
}

function _showQrAlert(event) {
  const placa = event.placa || 'Desconocida';
  const tipo = event.tipo_lavado || 'General';
  
  // 1. Toast Visual
  showToast(`✅ Lavado Registrado: ${placa} (${tipo})`);
  
  // 2. Sonido Ding
  playDing();
  
  // 3. Notificación Nativa de OS
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification('Nuevo Lavado Registrado', {
      body: `Vehículo: ${placa}\nTipo: ${tipo}\nLavador: ${event.lavador || 'N/D'}`,
      icon: '/static/img/icon.svg'
    });
  }
}

function closeQrAlert() {
  // Ya no se usa la alerta flotante intrusiva
}

function _playNotificationSound() {
  // El usuario pidió quitar el sonido
}

// ─── Inicializar polling cuando carga la app ──────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Se llama aquí para asegurar que se ejecuta después del DOMContentLoaded principal
  // El DOMContentLoaded de arriba ya carga los datos; este encola el polling.
  setTimeout(_initQrPolling, 2000);
});

// ─── Configuración y Gestión de Usuarios ──────────────────────────────────────
function switchConfigTab(tabId, btnEl) {
  // Ocultar paneles
  document.querySelectorAll('.config-panel').forEach(p => p.style.display = 'none');
  // Quitar active de botones
  document.querySelectorAll('.config-tab').forEach(b => {
    b.classList.remove('active');
    b.style.color = 'var(--muted)';
    b.style.borderBottomColor = 'transparent';
    b.style.fontWeight = '500';
  });
  
  // Activar tab
  document.getElementById('tab-' + tabId).style.display = 'block';
  btnEl.classList.add('active');
  btnEl.style.color = 'var(--accent)';
  btnEl.style.borderBottomColor = 'var(--accent)';
  btnEl.style.fontWeight = '600';
  
  if (tabId === 'cuentas') {
    loadUsers();
  } else if (tabId === 'nomina') {
    loadTarifas();
  }
}

async function loadTarifas() {
  try {
    const res = await fetch('/api/config/tarifas');
    const data = await res.json();
    document.getElementById('tarifaGeneral').value = '$ ' + (data['General'] || 0).toLocaleString('es-CO');
    document.getElementById('tarifaSencillo').value = '$ ' + (data['Sencillo'] || 0).toLocaleString('es-CO');
    document.getElementById('tarifaEnjuague').value = '$ ' + (data['Enjuague'] || 0).toLocaleString('es-CO');
  } catch(e) {
    showToast('Error cargando tarifas', 'err');
  }
}

document.addEventListener('input', e => {
  if (e.target && e.target.classList.contains('money-input')) {
    let val = e.target.value.replace(/\D/g, '');
    if (!val) { e.target.value = ''; return; }
    e.target.value = '$ ' + parseInt(val, 10).toLocaleString('es-CO');
  }
});

async function saveTarifas(e) {
  e.preventDefault();
  const getVal = (id) => parseFloat(document.getElementById(id).value.replace(/\D/g, '')) || 0;
  
  const data = {
    'General': getVal('tarifaGeneral'),
    'Sencillo': getVal('tarifaSencillo'),
    'Enjuague': getVal('tarifaEnjuague'),
  };
  
  const btn = e.target.querySelector('button');
  btn.disabled = true;
  btn.textContent = 'Guardando...';
  
  try {
    const res = await fetch('/api/config/tarifas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (res.ok) {
      showToast('Tarifas actualizadas ✓');
      state._tarifas = data; // Actualizar tarifas en el estado global
      const dr = await fetch('/api/data');
      const dd = await dr.json();
      if (dd && dd.vehiculos) {
        state.vehiculos = dd.vehiculos;
        state.historial = dd.historial_lavados || [];
        state.historial_lavados = state.historial;
        updateUI();
      }
    } else {
      showToast('Error al guardar', 'err');
    }
  } catch(err) {
    showToast('Error de conexión', 'err');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Guardar Tarifas';
  }
}

async function loadUsers() {
  try {
    const res = await fetch('/api/users');
    const users = await res.json();
    
    document.getElementById('usersBody').innerHTML = users.map(u => `
      <tr>
        <td style="font-weight:600">${u.username}</td>
        <td>${u.name}</td>
        <td><span class="badge ${u.role === 'admin' ? 'b-ok' : 'b-warn'}">${u.role}</span></td>
        <td><span class="badge ${u.active ? 'b-ok' : 'b-crit'}">${u.active ? 'Activo' : 'Inactivo'}</span></td>
        <td style="text-align:right">
          <button class="act-btn edit" onclick="editUser('${u.username}')">Editar</button>
          <button class="act-btn del" onclick="deleteUser('${u.username}')">Eliminar</button>
        </td>
      </tr>
    `).join('');
    
    // Guardar temporalmente
    window._usersCache = users;
  } catch(e) {
    showToast('Error cargando usuarios', 'err');
  }
}

function openUserModal() {
  document.getElementById('muTitle').textContent = 'Nuevo Usuario';
  document.getElementById('muSub').textContent = 'Crea una nueva cuenta de acceso al sistema.';
  document.getElementById('formUser').reset();
  document.getElementById('muUsername').readOnly = false;
  openModal('modalUser');
}

function editUser(username) {
  const users = window._usersCache || [];
  const u = users.find(x => x.username === username);
  if (!u) return;
  
  document.getElementById('muTitle').textContent = 'Editar Usuario';
  document.getElementById('muSub').textContent = `Modificando datos de ${username}`;
  document.getElementById('muUsername').value = u.username;
  document.getElementById('muUsername').readOnly = true;
  document.getElementById('muPassword').value = u.password || ''; // Enviar contraseña en caso de json local
  document.getElementById('muName').value = u.name;
  document.getElementById('muRole').value = u.role;
  document.getElementById('muActive').checked = u.active;
  
  openModal('modalUser');
}

async function saveUser(e) {
  e.preventDefault();
  const username = document.getElementById('muUsername').value.trim();
  const password = document.getElementById('muPassword').value.trim();
  const name = document.getElementById('muName').value.trim();
  const role = document.getElementById('muRole').value;
  const active = document.getElementById('muActive').checked;
  
  try {
    const res = await fetch('/api/users/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, name, role, active })
    });
    const result = await res.json();
    if (result.error) {
      showToast(result.error, 'err');
    } else {
      showToast('Usuario guardado');
      closeModal('modalUser');
      loadUsers();
    }
  } catch(e) {
    showToast('Error al guardar', 'err');
  }
}

async function deleteUser(username) {
  if (!confirm(`¿Estás seguro de eliminar el usuario ${username}?`)) return;
  
  try {
    const res = await fetch('/api/users/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username })
    });
    const result = await res.json();
    if (result.error) {
      showToast(result.error, 'err');
    } else {
      showToast('Usuario eliminado', 'err');
      loadUsers();
    }
  } catch(e) {
    showToast('Error al eliminar', 'err');
  }
}

