// ─── Vista Personal y Rendimiento (Nómina Corporativa) ────────────────────────
async function exportarNominaPdf() {
  const desde = document.getElementById('personalDesde')?.value || '';
  const hasta = document.getElementById('personalHasta')?.value || '';
  const resp = document.getElementById('personalResponsable')?.value || 'Administrador';

  const btn = document.getElementById('btnExportNomina');
  if (btn) { btn.disabled = true; btn.innerHTML = '⏳ Generando PDF...'; }

  try {
    const blob = await fetch('/api/exportar-nomina-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ desde, hasta, responsable: resp })
    }).then(r => {
      if (!r.ok) throw new Error();
      return r.blob();
    });
    
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const periodo = (desde && hasta) ? `${desde}_al_${hasta}` : (desde || hasta || 'completo');
    a.download = `Nomina_FlotaUraba_${periodo}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    window.showToast('📄 PDF de nómina generado ✓');
  } catch (e) {
    window.showToast('Error al generar PDF', 'err');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '⬇ Exportar Nómina PDF'; }
  }
}

function renderPersonal() {
  _buildPersonalView(window.state.historial_lavados || []);
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
  const dStr = desde.toISOString().split('T')[0];
  const hStr = hasta.toISOString().split('T')[0];
  
  const dEl = document.getElementById('personalDesde');
  const hEl = document.getElementById('personalHasta');
  if (dEl) dEl.value = dStr;
  if (hEl) hEl.value = hStr;
  
  _buildPersonalView(window.state.historial_lavados || []);
}

function toggleNominaDetalle(key) {
  const row = document.getElementById(`nom-detail-${key}`);
  const btn = document.getElementById(`nom-btn-${key}`);
  if (!row || !btn) return;

  const isHidden = row.style.display === 'none';
  row.style.display = isHidden ? 'table-row' : 'none';
  btn.innerHTML = isHidden 
    ? 'Ocultar <span class="material-symbols-outlined" style="font-size:16px;">expand_less</span>' 
    : 'Detalle <span class="material-symbols-outlined" style="font-size:16px;">expand_more</span>';
}

function _buildPersonalView(historial) {
  const view = document.getElementById('view-personal');
  if (!view) return;

  const TODOS_LAVADORES = (window.state.lavadoresSistema && window.state.lavadoresSistema.length)
    ? window.state.lavadoresSistema
    : [];

  const desdeEl = document.getElementById('personalDesde');
  const hastaEl = document.getElementById('personalHasta');
  const desde = desdeEl ? desdeEl.value : '';
  const hasta = hastaEl ? hastaEl.value : '';

  // 1. Filtrar registros por período
  let histFiltrado = historial.filter(h => {
    const lavs = h.lavadores && h.lavadores.length ? h.lavadores : (h.lavador ? [h.lavador] : []);
    return lavs.some(l => l && l.trim() !== '');
  });

  if (desde || hasta) {
    histFiltrado = histFiltrado.filter(h => {
      if (!h.fecha) return false;
      if (desde && h.fecha < desde) return false;
      if (hasta && h.fecha > hasta) return false;
      return true;
    });
  }

  const tarifas = window.state._tarifas || {};

  // 2. Agrupar por lavador
  const lavadores = {};
  TODOS_LAVADORES.forEach(name => lavadores[name.trim().toUpperCase()] = []);
  
  histFiltrado.forEach(h => {
    const lavsList = h.lavadores && h.lavadores.length
      ? h.lavadores
      : (h.lavador ? [h.lavador] : []);
    lavsList.forEach(lav => {
      if (!lav || !lav.trim()) return;
      const key = lav.trim().toUpperCase();
      if (!lavadores[key]) lavadores[key] = [];
      lavadores[key].push(h);
    });
  });

  // 3. Cálculos globales y por especialista
  let totalNominaGlobal = 0;
  let totalServiciosGlobal = 0;
  let lavadoresActivosCount = 0;

  const workersData = [];

  for (const [name, lavados] of Object.entries(lavadores)) {
    let pagoEstimado = 0;
    let totalFracc = 0;
    let genCount = 0;
    let senCount = 0;
    let enjCount = 0;
    let totalMinutos = 0;

    lavados.forEach(l => {
      const tipo = l.tipo_lavado || 'General';
      const tarifa = parseFloat(tarifas[tipo] || 0);
      const nLav = (l.lavadores && l.lavadores.length) ? l.lavadores.length : 1;
      const fracc = 1 / nLav;

      pagoEstimado += tarifa / nLav;
      totalFracc += fracc;

      const tLow = tipo.toLowerCase();
      if (tLow.includes('sencillo')) senCount += fracc;
      else if (tLow.includes('enjuague')) enjCount += fracc;
      else genCount += fracc;

      // Calcular tiempo
      if (l.hora_inicio && l.hora_fin) {
        const [h1, m1] = l.hora_inicio.split(':').map(Number);
        const [h2, m2] = l.hora_fin.split(':').map(Number);
        if (!isNaN(h1) && !isNaN(m1) && !isNaN(h2) && !isNaN(m2)) {
          const diff = (h2 * 60 + m2) - (h1 * 60 + m1);
          if (diff > 0) totalMinutos += diff / nLav;
        }
      }
    });

    pagoEstimado = Math.round(pagoEstimado);
    totalNominaGlobal += pagoEstimado;
    totalServiciosGlobal += totalFracc;

    if (lavados.length > 0) {
      lavadoresActivosCount++;
    }

    // Iniciales para monograma
    const parts = name.split(' ').filter(p => p.length > 0);
    const initials = parts.length >= 2 ? (parts[0][0] + parts[1][0]) : (parts[0] ? parts[0].slice(0, 2) : 'LV');

    const totalHorasStr = totalMinutos > 0 
      ? `${Math.floor(totalMinutos / 60)}h ${(Math.round(totalMinutos) % 60).toString().padStart(2, '0')}m`
      : '—';

    workersData.push({
      key: name.replace(/[^a-zA-Z0-9]/g, '_'),
      name,
      initials,
      lavados,
      pagoEstimado,
      totalFracc: Number(totalFracc.toFixed(1)),
      genCount: Number(genCount.toFixed(1)),
      senCount: Number(senCount.toFixed(1)),
      enjCount: Number(enjCount.toFixed(1)),
      totalHorasStr
    });
  }

  // Ordenar alfabéticamente
  workersData.sort((a, b) => a.name.localeCompare(b.name));

  const promedioNomina = lavadoresActivosCount > 0 
    ? Math.round(totalNominaGlobal / lavadoresActivosCount) 
    : 0;

  const periodoLabel = (desde && hasta) ? `Del ${desde} al ${hasta}` :
    desde ? `Desde ${desde}` :
      hasta ? `Hasta ${hasta}` : 'Histórico completo';

  // ── Render HTML ──
  let html = `
    <!-- Header -->
    <div class="nom-header">
      <div class="nom-title">Liquidación de Nómina</div>
      <div class="nom-sub">Consolidado de servicios y valores devengados por el equipo de lavado.</div>
    </div>

    <!-- Panel de Filtros -->
    <div class="nom-filter-panel">
      <div class="nom-filter-top">
        <div class="nom-filter-dates">
          <div class="nom-field">
            <label class="nom-label">Fecha Desde</label>
            <input type="date" id="personalDesde" value="${desde}" class="nom-input" onchange="_buildPersonalView(state.historial_lavados||[])">
          </div>
          <div class="nom-field">
            <label class="nom-label">Fecha Hasta</label>
            <input type="date" id="personalHasta" value="${hasta}" class="nom-input" onchange="_buildPersonalView(state.historial_lavados||[])">
          </div>
          <div class="nom-chips-wrap">
            <button class="nom-chip" onclick="_setQuincena(1)">1ra Quincena</button>
            <button class="nom-chip" onclick="_setQuincena(2)">2da Quincena</button>
            <button class="nom-chip" onclick="_setQuincena(0)">Mes Completo</button>
            <button class="nom-chip nom-chip-clear" onclick="document.getElementById('personalDesde').value='';document.getElementById('personalHasta').value='';_buildPersonalView(state.historial_lavados||[]);">✕ Limpiar</button>
          </div>
        </div>

        ${window.USER_ROLE === 'admin' ? `
        <div class="nom-actions-right">
          <div class="nom-field">
            <label class="nom-label">Responsable del reporte</label>
            <input type="text" id="personalResponsable" placeholder="Firma autorizada..." class="nom-input" style="width: 200px;">
          </div>
          <button id="btnExportNomina" onclick="exportarNominaPdf()" class="nom-btn-export">
            <span class="material-symbols-outlined" style="font-size:18px;">description</span> Exportar Nómina PDF
          </button>
        </div>
        ` : ''}
      </div>
    </div>

    <!-- Ribbon de KPIs Globales -->
    <div class="nom-kpi-grid">
      <div class="nom-kpi-card">
        <div class="nom-kpi-header">
          <span class="nom-kpi-label">Total a Liquidar</span>
          <span class="material-symbols-outlined nom-kpi-icon">payments</span>
        </div>
        <div class="nom-kpi-value highlight">$ ${totalNominaGlobal.toLocaleString('es-CO')}</div>
        <div class="nom-kpi-sub">${periodoLabel}</div>
      </div>

      <div class="nom-kpi-card">
        <div class="nom-kpi-header">
          <span class="nom-kpi-label">Servicios Liquidados</span>
          <span class="material-symbols-outlined nom-kpi-icon">local_car_wash</span>
        </div>
        <div class="nom-kpi-value">${Number(totalServiciosGlobal.toFixed(1))}</div>
        <div class="nom-kpi-sub">Total servicios en el período</div>
      </div>

      <div class="nom-kpi-card">
        <div class="nom-kpi-header">
          <span class="nom-kpi-label">Personal Activo</span>
          <span class="material-symbols-outlined nom-kpi-icon">group</span>
        </div>
        <div class="nom-kpi-value">${lavadoresActivosCount} <span style="font-size:14px;color:var(--muted);font-weight:600;">/ ${workersData.length}</span></div>
        <div class="nom-kpi-sub">Especialistas con servicios</div>
      </div>

      <div class="nom-kpi-card">
        <div class="nom-kpi-header">
          <span class="nom-kpi-label">Promedio por Lavador</span>
          <span class="material-symbols-outlined nom-kpi-icon">analytics</span>
        </div>
        <div class="nom-kpi-value">$ ${promedioNomina.toLocaleString('es-CO')}</div>
        <div class="nom-kpi-sub">Promedio devengado</div>
      </div>
    </div>

    <!-- Master Table de Liquidación -->
    <div class="nom-table-card">
      <div class="nom-table-wrap">
        <table class="nom-table">
          <thead>
            <tr>
              <th>Especialista</th>
              <th style="text-align:center;">Generales</th>
              <th style="text-align:center;">Sencillos</th>
              <th style="text-align:center;">Enjuagues</th>
              <th style="text-align:center;">Total Serv.</th>
              <th style="text-align:center;">Tiempo</th>
              <th style="text-align:right;">Monto a Liquidar</th>
              <th style="text-align:center;">Acción</th>
            </tr>
          </thead>
          <tbody>
  `;

  if (workersData.length === 0) {
    html += `
      <tr>
        <td colspan="8" style="text-align:center;padding:48px 16px;color:var(--muted);">
          <div style="font-size:15px;font-weight:700;color:var(--text);">No hay especialistas registrados</div>
          <div style="font-size:13px;margin-top:4px;">No se encontraron registros de lavadores en el sistema.</div>
        </td>
      </tr>
    `;
  } else {
    workersData.forEach(w => {
      let subtableHtml = '';
      if (w.lavados.length === 0) {
        subtableHtml = `
          <div style="padding:20px;text-align:center;color:var(--muted);font-size:13px;background:#FFF;border-radius:10px;border:1px dashed var(--border);">
            Este especialista no registra lavados en el período seleccionado (${periodoLabel}).
          </div>
        `;
      } else {
        const sortedLavs = [...w.lavados].sort((a, b) => (b.fecha || '').localeCompare(a.fecha || ''));
        subtableHtml = `
          <div style="overflow-x:auto;">
            <table class="nom-subtable">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Placa</th>
                  <th>Tipo</th>
                  <th>Municipio</th>
                  <th>Horario</th>
                  <th>Duración</th>
                  <th>Co-Lavadores</th>
                  <th style="text-align:right;">Tarifa Base</th>
                  <th style="text-align:right;">Liquidado</th>
                </tr>
              </thead>
              <tbody>
                ${sortedLavs.map(l => {
                  const tipo = l.tipo_lavado || 'General';
                  const tarifaBase = parseFloat(tarifas[tipo] || 0);
                  const lavsList = (l.lavadores && l.lavadores.length) ? l.lavadores : (l.lavador ? [l.lavador] : []);
                  const nLav = lavsList.length || 1;
                  const liqVal = Math.round(tarifaBase / nLav);
                  const coLavs = lavsList.filter(x => x.trim().toUpperCase() !== w.name);
                  const coStr = coLavs.length ? coLavs.join(', ') : '—';
                  const horario = (l.hora_inicio && l.hora_fin) ? `${l.hora_inicio} → ${l.hora_fin}` : (l.hora_inicio || l.hora_llegada || '—');

                  return `
                    <tr>
                      <td style="font-weight:600;white-space:nowrap;">${l.fecha || '—'}</td>
                      <td><span class="placa" style="font-size:12px;padding:3px 8px;">${l.placa || '—'}</span></td>
                      <td><span class="nom-tag">${tipo}</span></td>
                      <td style="color:var(--muted);font-size:12px;">${l.municipio || '—'}</td>
                      <td style="white-space:nowrap;font-family:var(--mono);font-size:12px;">${horario}</td>
                      <td style="color:var(--muted);">${l.duracion || '—'}</td>
                      <td style="color:var(--muted);font-size:11.5px;">${coStr}</td>
                      <td style="text-align:right;color:var(--muted);font-variant-numeric:tabular-nums;">$ ${tarifaBase.toLocaleString('es-CO')}</td>
                      <td style="text-align:right;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums;">$ ${liqVal.toLocaleString('es-CO')}</td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        `;
      }

      html += `
        <tr class="nom-row">
          <td>
            <div class="nom-worker-cell">
              <div class="nom-avatar">${w.initials}</div>
              <div>
                <div class="nom-worker-name">${w.name}</div>
                <div class="nom-worker-role">Especialista de Lavado</div>
              </div>
            </div>
          </td>
          <td style="text-align:center;"><span class="nom-tag">${w.genCount}</span></td>
          <td style="text-align:center;"><span class="nom-tag">${w.senCount}</span></td>
          <td style="text-align:center;"><span class="nom-tag">${w.enjCount}</span></td>
          <td style="text-align:center;"><span class="nom-tag nom-tag-total">${w.totalFracc}</span></td>
          <td style="text-align:center;color:var(--muted);font-size:12.5px;">${w.totalHorasStr}</td>
          <td style="text-align:right;">
            <div class="nom-pay-amount">$ ${w.pagoEstimado.toLocaleString('es-CO')}</div>
          </td>
          <td style="text-align:center;">
            <button class="nom-toggle-btn" id="nom-btn-${w.key}" onclick="toggleNominaDetalle('${w.key}')">
              Detalle <span class="material-symbols-outlined" style="font-size:16px;">expand_more</span>
            </button>
          </td>
        </tr>
        <tr id="nom-detail-${w.key}" class="nom-detail-row" style="display:none;">
          <td colspan="8" style="padding:0;">
            <div class="nom-detail-box">
              <div class="nom-detail-title">
                <span class="material-symbols-outlined" style="font-size:16px;color:var(--muted);">receipt_long</span>
                Servicios Detallados — ${w.name} (${w.lavados.length} registros)
              </div>
              ${subtableHtml}
            </div>
          </td>
        </tr>
      `;
    });
  }

  html += `
          </tbody>
        </table>
      </div>
    </div>
  `;

  view.innerHTML = html;
}

// ─── Exportar PDF Genérico ──────────────────────────────────────────────────
async function descargarPDF(tipo_reporte, btnEl) {
  let start_date, end_date, placas = [], maxDia = 4, responsable = '';
  const today = new Date().toISOString().split('T')[0];

  if (tipo_reporte === 'programacion') {
    if (!window.state.progConfig) {
      return window.showToast('Primero genera la programación en la pestaña "Propuesta de programación"', 'err');
    }
    start_date = window.state.progConfig.start_date;
    end_date = window.state.progConfig.end_date;
    placas = window.state.progConfig.placas;
    maxDia = document.getElementById('pdfMaxDia')?.value || 4;
    responsable = (document.getElementById('pdfRespProg')?.value || '').trim();
  } else if (tipo_reporte === 'diagnostico') {
    start_date = today;
    end_date = today;
    responsable = (document.getElementById('pdfRespDiag')?.value || '').trim();
  } else if (tipo_reporte === 'flota') {
    start_date = today;
    end_date = today;
    responsable = (document.getElementById('pdfRespFlota')?.value || '').trim();
  } else if (tipo_reporte === 'diarios') {
    start_date = document.getElementById('pdfFechaDiario')?.value || today;
    end_date = document.getElementById('pdfFechaDiarioHasta')?.value || start_date;
    responsable = (document.getElementById('pdfRespDiario')?.value || '').trim();
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
      window.showToast(err.error || 'Error al generar el PDF', 'err');
      return;
    }

    const blob = await res.blob();
    const objUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objUrl;
    const nombres = {
      diagnostico: `Diagnostico_${today}.pdf`,
      programacion: `Programacion_${start_date}_al_${end_date}.pdf`,
      flota: `Flota_${today}.pdf`,
      diarios: start_date === end_date ? `Lavados_Diarios_${start_date}.pdf` : `Lavados_Diarios_${start_date}_al_${end_date}.pdf`
    };
    link.download = nombres[tipo_reporte] || `Reporte_${today}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(objUrl);
    window.showToast('✓ PDF descargado correctamente');
  } catch (e) {
    window.showToast('Error de conexión al generar el PDF', 'err');
  } finally {
    btnEl.disabled = false;
    btnEl.innerHTML = originalText;
  }
}

window.exportarNominaPdf = exportarNominaPdf;
window.renderPersonal = renderPersonal;
window._setQuincena = _setQuincena;
window.toggleNominaDetalle = toggleNominaDetalle;
window._buildPersonalView = _buildPersonalView;
window.descargarPDF = descargarPDF;
