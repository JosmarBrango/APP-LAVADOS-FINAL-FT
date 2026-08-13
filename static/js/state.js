// ─── Estado global ────────────────────────────────────────────────────────────
let state = {
  vehiculos: [],
  serverStats: null,
  loaded: false,
  view: 'diagnostico',
  filterMunProm: '',
  filterEstProm: '',
  searchProm: '',
  filterMunVeh: '',
  searchVeh: '',
  editTarget: null,
  progConfig: null, // Guarda {start_date, end_date, placas} de la última programación generada
  historial: [],
  selectedMes: 'mes_actual',  // 'mes_actual' | 'TOTAL' | 'YYYY-MM'
  diagStats: null,             // stats del mes seleccionado para el diagnóstico
  lavadores_stats: {},
  _tarifas: null,
  lavadoresSistema: []
};

// ─── Helpers de Estado ────────────────────────────────────────────────────────
function getStats() {
  if (state.serverStats) return state.serverStats;
  const total = state.vehiculos.length;
  const mesLabel = new Date().toLocaleString('es-CO', { month: 'long', year: 'numeric' });
  return {
    total_veh: total,
    lavados_mes_actual: 0,
    meta_mes: total,
    pendientes_mes_actual: total,
    pct_cum_mes: 0,
    veh_sin_lavado_mes: total,
    mes_actual_label: mesLabel,
    meta_proximo_mes: total,
    total_gen: 0,
    sin_gen: total,
    meta: total,
    deficit: total,
    pct_cum: 0,
    avg_espera: 0,
    avg_lavado_por_tipo: {}
  };
}

function getMunicipios() {
  return [...new Set(state.vehiculos.map(v => v.mun).filter(m => m && !window.INVALID_MUNS.has(m.toUpperCase())))].sort();
}

window.state = state;
window.getStats = getStats;
window.getMunicipios = getMunicipios;
