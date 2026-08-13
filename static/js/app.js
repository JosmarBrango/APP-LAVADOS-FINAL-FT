// ─── Carga inicial y Estado Global ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const [dataRes, statsRes, tarifasRes, lavadoresRes] = await Promise.all([
      fetch('/api/data?t=' + Date.now()),
      fetch('/api/stats'),
      fetch('/api/config/tarifas').catch(() => ({ json: async () => ({}) })),
      fetch('/api/lavadores?t=' + Date.now()).catch(() => ({ json: async () => [] }))
    ]);
    const data = await dataRes.json();
    const stats = await statsRes.json();
    const tarifas = await tarifasRes.json().catch(() => ({}));
    let lavadores = [];
    try {
        if (lavadoresRes && lavadoresRes.ok) {
            lavadores = await lavadoresRes.json();
        }
    } catch(e) {
        console.error("Error parsing lavadores:", e);
    }

    if (data && data.vehiculos) {
      window.state.vehiculos = data.vehiculos;
      window.state.historial = data.historial_lavados || [];
      window.state.historial_lavados = window.state.historial;
      window.state.lavadores_stats = data.lavadores_stats || {};
    }
    if (stats && !stats.error) {
      window.state.serverStats = stats;
    }
    if (tarifas && !tarifas.error) {
      window.state._tarifas = tarifas;
    }

    if (Array.isArray(lavadores) && lavadores.length > 0) {
      window.state.lavadoresSistema = lavadores.map(l => String(l).trim().toUpperCase());
    } else {
      const fromStats = Object.keys(window.state.lavadores_stats || {});
      window.state.lavadoresSistema = fromStats.map(l => l.trim().toUpperCase());
    }
    window._LAVADORES_SISTEMA = window.state.lavadoresSistema;
    
    if(window._populateLavPersonal) window._populateLavPersonal();
    if(window._populatePlacasSelect) window._populatePlacasSelect();
  } catch (e) {
    console.error("Error cargando datos:", e);
    window.state.vehiculos = [];
  }

  // Listener para autocompletar municipio cuando se seleccione una placa
  const elPlaca = document.getElementById('mlPlaca');
  if (elPlaca) {
    elPlaca.addEventListener('input', () => {
      const placa = elPlaca.value.toUpperCase();
      const vehiculo = (window.state.vehiculos || []).find(v => v.placa === placa);
      const elMun = document.getElementById('mlMunicipio');
      if (elMun) {
        elMun.value = vehiculo && vehiculo.mun ? vehiculo.mun : '';
      }
    });
  }

  window.state.loaded = true;
  document.getElementById('loadingState').style.display = 'none';
  document.getElementById('mainContent').style.display = 'block';

  populateFilters();
  await cargarMesesDisponibles();   
  await seleccionarMes('mes_actual', document.querySelector('.mes-chip[data-mes="mes_actual"]'), true);

  // Inicializar fecha de hoy en el selector de Lavados Diarios
  const elFechaDiario = document.getElementById('pdfFechaDiario');
  const elFechaDiarioHasta = document.getElementById('pdfFechaDiarioHasta');
  const hoy = new Date().toISOString().split('T')[0];
  if (elFechaDiario && !elFechaDiario.value) {
    elFechaDiario.value = hoy;
  }
  if (elFechaDiarioHasta && !elFechaDiarioHasta.value) {
    elFechaDiarioHasta.value = hoy;
  }

  // QR Polling si existe la función
  if (window._initQrPolling) {
    setTimeout(window._initQrPolling, 2000);
  }
});

// ─── Actualización de estado ──────────────────────────────────────────────────
async function refreshAllData() {
  try {
    const [dataRes, lavadoresRes] = await Promise.all([
      fetch('/api/data?t=' + Date.now()),
      fetch('/api/lavadores?t=' + Date.now()).catch(() => ({ json: async () => [] }))
    ]);
    const data = await dataRes.json();
    let lavadores = [];
    try {
        if (lavadoresRes && lavadoresRes.ok) {
            lavadores = await lavadoresRes.json();
        }
    } catch(e) {
        console.error("Error parsing lavadores on refresh:", e);
    }

    if (data && data.vehiculos) {
      window.state.vehiculos = data.vehiculos;
      window.state.historial = data.historial_lavados || [];
      window.state.historial_lavados = window.state.historial;
      window.state.lavadores_stats = data.lavadores_stats || {};
      window.state.chartData = data.chartData || null;
    }
    if (Array.isArray(lavadores) && lavadores.length > 0) {
      window.state.lavadoresSistema = lavadores.map(l => String(l).trim().toUpperCase());
    } else {
      const fromStats = Object.keys(window.state.lavadores_stats || {});
      window.state.lavadoresSistema = fromStats.map(l => l.trim().toUpperCase());
    }
    window._LAVADORES_SISTEMA = window.state.lavadoresSistema;

    populateFilters();
    if(window._populateLavPersonal) window._populateLavPersonal();
    if(window._populatePlacasSelect) window._populatePlacasSelect();

    await cargarMesesDisponibles();
    await seleccionarMes(window.state.selectedMes);
  } catch (e) {
    console.error('Error en refreshAllData:', e);
  }
}
window.refreshAllData = refreshAllData;

// Mantener esto por compatibilidad
async function updateVehiculos(dbResponse) {
  await refreshAllData();
}
window.updateVehiculos = updateVehiculos;

// ─── Filtro de mes ───────────────────────────────────────────────────────────
async function cargarMesesDisponibles() {
  try {
    const res = await fetch('/api/meses-disponibles');
    const meses = await res.json();
    const selectEl = document.getElementById('mesSelect');
    if (!selectEl || !Array.isArray(meses)) return;
    
    Array.from(selectEl.options).forEach(opt => {
      if (opt.value !== 'TOTAL') opt.remove();
    });
    
    meses.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.valor;
      opt.textContent = m.label;
      opt.style.cssText = 'background-color: white; color: #1e293b; font-weight: 500;';
      selectEl.appendChild(opt);
    });
    
    if (window.state.selectedMes === 'mes_actual') {
      window.state.selectedMes = meses.length > 0 ? meses[0].valor : 'TOTAL';
    }
    
    if (window.state.selectedMes) {
      selectEl.value = window.state.selectedMes;
    }
  } catch (e) {
    console.warn('No se pudo cargar meses disponibles:', e);
  }
}
window.cargarMesesDisponibles = cargarMesesDisponibles;

async function seleccionarMes(mes, silent = false) {
  window.state.selectedMes = mes;
  const mesParam = (mes === 'mes_actual') ? '' : `?mes=${mes}`;
  try {
    const res = await fetch('/api/stats' + mesParam);
    const stats = await res.json();
    if (!stats.error) window.state.diagStats = stats;
  } catch (e) {
    console.warn('Error cargando stats por mes:', e);
  }
  updateUI();
}
window.seleccionarMes = seleccionarMes;

function populateFilters() {
  const muns = window.getMunicipios();
  const promMun = document.getElementById('promMun');
  const vehMun = document.getElementById('vehMun');
  const selProm = promMun ? promMun.value : '';
  const selVeh = vehMun ? vehMun.value : '';

  const opts = '<option value="">Todos los municipios</option>' +
    muns.map(m => `<option value="${m}">${m}</option>`).join('');
  if (promMun) { promMun.innerHTML = opts; if (muns.includes(selProm)) promMun.value = selProm; }
  if (vehMun) { vehMun.innerHTML = opts; if (muns.includes(selVeh)) vehMun.value = selVeh; }
}

// ─── Render General ───────────────────────────────────────────────────────────
function updateUI() {
  const stats = window.state.diagStats || window.getStats();
  const isTotalMode = window.state.selectedMes === 'TOTAL';

  const mesLabel = stats.mes_actual_label || '';
  const realizadosMes = stats.lavados_mes_actual ?? 0;
  const metaMes = stats.meta_mes ?? stats.meta ?? 0;
  const pendientesMes = stats.pendientes_mes_actual ?? stats.deficit ?? 0;
  const sinLavMes = stats.veh_sin_lavado_mes ?? stats.sin_gen ?? 0;
  const cumplimientoMes = stats.pct_cum_mes ?? stats.pct_cum ?? 0;
  const totalVeh = stats.total_veh ?? 0;
  const proximoMes = stats.meta_proximo_mes ?? totalVeh;

  const globalStats = window.getStats();
  document.getElementById('ftTotal').textContent = globalStats.total_veh ?? totalVeh;
  document.getElementById('ftSinLav').textContent = globalStats.veh_sin_lavado_mes ?? sinLavMes;
  document.getElementById('ftCumplimiento').textContent = (globalStats.pct_cum_mes ?? cumplimientoMes) + '%';
  document.getElementById('ftRealizados').textContent = globalStats.lavados_mes_actual ?? realizadosMes;

  document.getElementById('tbSub').textContent = `Zona Urabá · ${totalVeh} vehículos`;
  const tbBadge = document.getElementById('tbBadge');
  tbBadge.style.display = pendientesMes > 0 && !isTotalMode ? 'flex' : 'none';
  document.getElementById('tbBadgeText').textContent = `${pendientesMes} lavados pendientes en ${mesLabel}`;

  if (document.getElementById('kpiMesLabel'))
    document.getElementById('kpiMesLabel').textContent = mesLabel || 'Mes actual';
  document.getElementById('kpiRealizados').textContent = realizadosMes;
  document.getElementById('kpiMeta').textContent = isTotalMode
    ? 'lavados generales totales'
    : `de ${metaMes} esperados`;

  const pendLbl = document.getElementById('kpiPendientesLbl');
  const pendCard = document.getElementById('kpiCardPendientes');
  if (isTotalMode) {
    if (pendLbl) pendLbl.textContent = 'Vehículos sin lavado';
    document.getElementById('kpiDeficit').textContent = sinLavMes;
    if (pendCard) pendCard.className = sinLavMes === 0 ? 'kpi ok' : 'kpi danger';
  } else {
    if (pendLbl) pendLbl.textContent = 'Pendientes este mes';
    document.getElementById('kpiDeficit').textContent = pendientesMes;
    if (pendCard) pendCard.className = pendientesMes === 0 ? 'kpi ok' : 'kpi danger';
  }

  const cumplLbl = document.getElementById('kpiCumplimientoLbl');
  if (cumplLbl) cumplLbl.textContent = isTotalMode ? 'Cobertura flota' : 'Cumplimiento del mes';
  document.getElementById('kpiCumplimiento').textContent = cumplimientoMes + '%';
  document.getElementById('kpiCumplimientoSub').textContent = isTotalMode
    ? `${totalVeh - sinLavMes} de ${totalVeh} vehículos lavados`
    : `${realizadosMes} de ${metaMes} requeridos`;

  if (document.getElementById('kpiProximoMes')) {
    document.getElementById('kpiProximoMes').textContent = isTotalMode ? '—' : proximoMes;
    document.getElementById('kpiProximoMesSub').textContent = isTotalMode ? 'no aplica en vista total' : 'lavados a programar';
  }

  const card1 = document.getElementById('kpiRealizados')?.closest('.kpi');
  if (card1) {
    card1.className = 'kpi ' + (cumplimientoMes >= 80 ? 'ok' : cumplimientoMes >= 40 ? 'warn' : 'danger');
  }

  if (window.renderDiagnostico) window.renderDiagnostico();
  if (window.renderPromedios) window.renderPromedios();
  if (window.renderVehiculos) window.renderVehiculos();
  if (window.renderHistorial) window.renderHistorial();
  if (window.state.view === 'personal' && window.renderPersonal) window.renderPersonal();
  if (window.state.view === 'lavados' && window.renderTodosLavados) window.renderTodosLavados();
}
window.updateUI = updateUI;

// ─── Navegación ───────────────────────────────────────────────────────────────
const VIEWS_TITLES = {
  diagnostico: 'Diagnóstico general',
  promedios: 'Promedios por día',
  programacion: 'Propuesta de programación',
  vehiculos: 'Gestión de vehículos',
  lavados: 'Todos los lavados',
  historial: 'Historial y Escáner QR',
  reportes: 'Centro de Reportes'
};

function showView(id, btnEl) {
  window.state.view = id;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
  document.getElementById(`view-${id}`).classList.add('active');
  document.getElementById('tbTitle').textContent = VIEWS_TITLES[id] || id;
  if (id === 'programacion' && window.initFechasProg) window.initFechasProg();
  if (id === 'personal' && window.renderPersonal) window.renderPersonal();
  if (id === 'lavados' && window.renderTodosLavados) window.renderTodosLavados();
  if (id === 'configuracion' && window.loadUsers) window.loadUsers();
}
window.showView = showView;

// QR Polling & Alertas en Tiempo Real
let _lastQrTs = null;

if ('Notification' in window) {
  Notification.requestPermission();
}

function playDing() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gainNode = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime); 
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
  try {
    const res = await fetch('/api/last-qr-event?t=' + Date.now());
    const data = await res.json();
    if (data.event) _lastQrTs = data.event.timestamp;
  } catch (e) { }

  setInterval(async () => {
    try {
      const res = await fetch('/api/last-qr-event?t=' + Date.now());
      const data = await res.json();
      if (data.event && data.event.timestamp !== _lastQrTs) {
        _lastQrTs = data.event.timestamp;
        _showQrAlert(data.event);
        const dr = await fetch('/api/data?t=' + Date.now());
        const dd = await dr.json();
        if (dd && dd.vehiculos) {
          updateVehiculos(dd);
        }
      }
    } catch (e) { }
  }, 8000);
}
window._initQrPolling = _initQrPolling;

function _showQrAlert(event) {
  const placa = event.placa || 'Desconocida';
  const tipo = event.tipo_lavado || 'General';
  const lavsList = event.lavadores && event.lavadores.length
    ? event.lavadores : (event.lavador ? [event.lavador] : []);
  const lavsStr = lavsList.join(', ') || 'N/D';

  window.showToast(`✅ Lavado Registrado: ${placa} (${tipo})`);

  const el = document.getElementById('qrAlert');
  if (el) {
    document.getElementById('qaPlaca').textContent = placa;
    document.getElementById('qaLavador').textContent = lavsStr;
    document.getElementById('qaTipo').textContent = tipo;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 8000);
  }

  playDing();

  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification('Nuevo Lavado Registrado', {
      body: `Vehículo: ${placa}\nTipo: ${tipo}\nLavadores: ${lavsStr}`,
      icon: '/static/img/icon.svg'
    });
  }
}
window.closeQrAlert = function() {};
