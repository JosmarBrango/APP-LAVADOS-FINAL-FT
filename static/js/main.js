// ─── Constantes ───────────────────────────────────────────────────────────────
const DOW      = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
const DOW_FULL = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];
const CUTOFF   = 990;   // 16:30 en minutos
const NOMBRES_MESES = ['enero','febrero','marzo','abril','mayo','junio',
                        'julio','agosto','septiembre','octubre','noviembre','diciembre'];

// Meses dinámicos eliminados, ya no son necesarios para el tablero Kanban

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
    const [dataRes, statsRes] = await Promise.all([
      fetch('/api/data'),
      fetch('/api/stats')
    ]);
    const data  = await dataRes.json();
    const stats = await statsRes.json();

    if (data && data.vehiculos) {
      state.vehiculos   = data.vehiculos;
      state.historial   = data.historial_lavados || [];
    }
    if (stats && !stats.error) {
      state.serverStats = stats;
    }
  } catch (e) {
    console.error("Error cargando datos:", e);
    state.vehiculos = [];
  }

  state.loaded = true;
  document.getElementById('loadingState').style.display = 'none';
  document.getElementById('mainContent').style.display  = 'block';

  populateFilters();
  // _populatePdfMeses(); ya no es necesario
  updateUI();
});

// ─── Actualización de estado ──────────────────────────────────────────────────
async function updateVehiculos(dbResponse) {
  // La API devuelve el objeto completo: { vehiculos, stats, chartData }
  if (dbResponse && dbResponse.vehiculos) {
    state.vehiculos   = dbResponse.vehiculos;
    state.serverStats = dbResponse.stats || null;
    state.historial   = dbResponse.historial_lavados || [];
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
  // Programación se renderiza solo cuando el tab está activo o se cambia el mes
  if (state.view === 'programacion') renderProgramacion();
}

function populateFilters() {
  const muns = getMunicipios();
  const promMun = document.getElementById('promMun');
  const vehMun  = document.getElementById('vehMun');
  const selProm = promMun.value;
  const selVeh  = vehMun.value;

  const opts = '<option value="">Todos los municipios</option>' +
               muns.map(m => `<option value="${m}">${m}</option>`).join('');
  promMun.innerHTML = opts;
  vehMun.innerHTML  = opts;

  if (muns.includes(selProm)) promMun.value = selProm;
  if (muns.includes(selVeh))  vehMun.value  = selVeh;
}

// ─── Navegación ───────────────────────────────────────────────────────────────
const VIEWS_TITLES = {
  diagnostico:   'Diagnóstico general',
  promedios:     'Promedios por día',
  programacion:  'Propuesta de programación',
  vehiculos:     'Gestión de vehículos',
  historial:     'Historial y Escáner QR'
};

function showView(id, btnEl) {
  state.view = id;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
  document.getElementById(`view-${id}`).classList.add('active');
  document.getElementById('tbTitle').textContent = VIEWS_TITLES[id];
  if (id === 'programacion') renderProgramacion();
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

  document.getElementById('diagBody').innerHTML = muns.map(mun => {
    const vv  = state.vehiculos.filter(v => v.mun === mun);
    const lav = vv.reduce((a, v) => a + v.lavGen, 0);
    const sin = vv.filter(v => v.lavGen === 0).length;
    const meta = vv.length * n_meses;
    const pct  = meta > 0 ? ((lav / meta) * 100).toFixed(1) : 0;
    const barCls  = parseFloat(pct) < 33 ? 'crit' : parseFloat(pct) < 66 ? 'warn' : 'ok';
    const badgeCls = sin > 0 ? 'b-crit' : 'b-ok';
    return `
      <tr>
        <td style="font-weight:500">${mun}</td>
        <td><span class="badge b-info">${vv.length}</span></td>
        <td><span style="font-family:var(--mono);font-size:13px">${lav}</span></td>
        <td><span class="badge ${badgeCls}">${sin}</span></td>
        <td>
          <div class="bar-wrap">
            <div class="bar-bg"><div class="bar-fill ${barCls}" style="width:${pct}%"></div></div>
            <span style="font-family:var(--mono);font-size:11px;color:var(--muted)">${pct}%</span>
          </div>
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

  const renderMiniCard = (v) => {
    const turnoCls = (v.turno && v.turno.cls) ? v.turno.cls : 'noday';
    return `
      <div class="prog-card mini t-${turnoCls}" draggable="true" ondragstart="onDragStart(event, '${v.placa}')" ondragend="onDragEnd(event)" id="veh-${v.placa}" style="margin-bottom:8px;background:var(--card);padding:10px;border-radius:8px;border-left:4px solid ${v.turno?.color || '#ccc'};box-shadow:0 1px 3px rgba(0,0,0,0.05);cursor:grab;transition:transform 0.1s;">
        <div class="prog-placa" style="font-weight:700;font-size:14px;color:var(--text);display:flex;justify-content:space-between;">
           ${v.placa} <span class="badge ${bCls(v.lavGen)}" style="font-size:9px">${v.lavGen} lav.</span>
        </div>
        <div class="prog-meta" style="font-size:11px;color:var(--muted);margin-top:4px;">${v.mun} · ${v.ruta}</div>
      </div>
    `;
  };

  let html = '';
  
  // Columna: Sin asignar
  html += `
    <div class="kanban-col" style="flex:0 0 240px;background:#f8fafc;border-radius:12px;padding:12px;display:flex;flex-direction:column;height:100%;border:2px dashed #e2e8f0;transition:border-color 0.2s;"
         ondragover="onDragOverUnassigned(event, this)" 
         ondragleave="onDragLeaveUnassigned(event, this)" 
         ondrop="onDrop(event, null)">
      <div style="font-size:13px;font-weight:700;margin-bottom:12px;color:#64748b;">
        Sin Asignar <span class="badge b-crit" style="font-size:10px;float:right">${unassigned.length}</span>
      </div>
      <div style="overflow-y:auto;flex-grow:1;min-height:100px;">
        ${unassigned.map(renderMiniCard).join('')}
      </div>
    </div>
  `;
  
  // Columnas: Fechas
  days.forEach(d => {
    const items = assigned[d] || [];
    const dateObj = new Date(d + 'T12:00:00');
    const isFull = items.length >= 4;
    const dayLabel = `${DOW_FULL[dateObj.getDay()]} ${dateObj.getDate()} ${NOMBRES_MESES[dateObj.getMonth()].substr(0,3)}`;
    
    html += `
      <div class="kanban-col ${isFull ? 'full' : ''}" style="flex:0 0 240px;background:#f1f5f9;border-radius:12px;padding:12px;display:flex;flex-direction:column;height:100%;border:1px solid #e2e8f0;transition:all 0.2s;"
           ondragover="onDragOver(event, this, ${items.length})" 
           ondragleave="onDragLeave(event, this)" 
           ondrop="onDrop(event, '${d}')"
           data-day="${d}">
        <div style="font-size:13px;font-weight:700;margin-bottom:12px;color:var(--text);display:flex;justify-content:space-between;align-items:center;">
          ${dayLabel}
          <span style="font-size:11px;font-weight:600;color:var(--muted);background:#e2e8f0;padding:2px 6px;border-radius:10px;">${items.length}/4</span>
        </div>
        <div style="overflow-y:auto;flex-grow:1;min-height:100px;">
          ${items.map(renderMiniCard).join('')}
        </div>
      </div>
    `;
  });

  body.innerHTML = html;
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
      <td style="text-align:right">
        <button class="act-btn wash" onclick="quitarLavado('${v.placa}')">−</button>
        <button class="act-btn wash" onclick="sumarLavado('${v.placa}')">+</button>
        <button class="act-btn qr"   onclick="showQR('${v.placa}')" title="Ver QR para registro en campo">QR</button>
        <button class="act-btn edit" onclick="editVehicle('${v.placa}')" style="margin-left:6px">Editar</button>
        <button class="act-btn del"  onclick="deleteVehicle('${v.placa}')">Eliminar</button>
      </td>
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
  toast.textContent = msg;
  toast.className   = `toast open ${type}`;
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
  const hora  = document.getElementById('mlHora').value;

  try {
    const res    = await fetch('/api/lavado/add_manual', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ placa, fecha, hora }) });
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


async function descargarPDF() {
  if (!state.progConfig) {
    return showToast('Primero debes generar la programación en el tablero', 'err');
  }

  const { start_date, end_date, placas } = state.progConfig;
  const maxDia      = document.getElementById('pdfMaxDia').value;
  const responsable = encodeURIComponent(document.getElementById('pdfResponsable').value.trim());

  const btn = document.getElementById('pdfBtn');
  const originalText = btn.innerHTML;
  btn.disabled   = true;
  btn.innerHTML  = '⏳ Generando PDF…';

  try {
    const res = await fetch(`/exportar-pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        start_date,
        end_date,
        placas,
        max_dia: maxDia,
        responsable
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Error desconocido' }));
      showToast(err.error || 'Error al generar el PDF', 'err');
      return;
    }

    // Descargar el archivo
    const blob     = await res.blob();
    const objUrl   = URL.createObjectURL(blob);
    const link     = document.createElement('a');
    link.href      = objUrl;
    link.download  = `Reporte_Lavados_${start_date}_al_${end_date}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(objUrl);

    showToast('✓ Reporte PDF descargado correctamente');
    closeModal('modalPDF');
  } catch (e) {
    showToast('Error de conexión al generar el PDF', 'err');
  } finally {
    btn.disabled  = false;
    btn.innerHTML = originalText;
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
                     
    return `
      <tr>
        <td><span class="placa">${r.placa}</span></td>
        <td style="font-family:var(--mono)">${r.fecha}</td>
        <td style="font-family:var(--mono);font-weight:600">${r.hora}</td>
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
    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    const today = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`;
    const time  = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
    
    document.getElementById('mlPlaca').value = placa;
    document.getElementById('mlFecha').value = today;
    document.getElementById('mlHora').value  = time;
    
    openModal('modalLavado');
    showToast(`QR detectado: ${placa}. Confirma el lavado.`, 'good');
  } else {
    showToast('QR no reconocido o placa inválida', 'err');
  }
}

function onScanFailure(error) {
  // Ignore errors as it parses each frame
}
