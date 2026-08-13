// ─── Vista Personal y Rendimiento (Nómina) ──────────────────────────────────
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
    if (btn) { btn.disabled = false; btn.innerHTML = '📄 Exportar Nómina PDF'; }
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
  document.getElementById('personalDesde').value = desde.toISOString().split('T')[0];
  document.getElementById('personalHasta').value = hasta.toISOString().split('T')[0];
  _buildPersonalView(window.state.historial_lavados || []);
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

  const lavadores = {};
  TODOS_LAVADORES.forEach(name => lavadores[name] = []);
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

  const periodoLabel = (desde && hasta) ? `Del ${desde} al ${hasta}` :
    desde ? `Desde ${desde}` :
      hasta ? `Hasta ${hasta}` : 'Todo el historial';
  const totalRegistros = histFiltrado.length;

  let html = `
    <div class="sec-hdr" style="margin-top: 0; margin-bottom: 28px;">
      <div class="sec-title" style="font-size: 28px; font-weight: 800; letter-spacing:-0.02em; color:var(--text);">Registro de Lavadores</div>
      <div style="color: var(--muted); font-size: 15px; margin-top: 6px; font-weight:500;">Historial detallado de los vehículos gestionados por cada integrante del equipo.</div>
    </div>

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
          <button onclick="_setQuincena(1)" style="padding:9px 14px;border:1px solid var(--border);border-radius:10px;background:var(--bg);font-family:var(--sans);font-size:13px;font-weight:600;color:var(--text);cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background='var(--accent-dim)';this.style.borderColor='var(--accent)';this.style.color='var(--accent)';" onmouseout="this.style.background='var(--bg)';this.style.borderColor='var(--border)';this.style.color='var(--text)'">1ra Quincena</button>
          <button onclick="_setQuincena(2)" style="padding:9px 14px;border:1px solid var(--border);border-radius:10px;background:var(--bg);font-family:var(--sans);font-size:13px;font-weight:600;color:var(--text);cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background='var(--accent-dim)';this.style.borderColor='var(--accent)';this.style.color='var(--accent)';" onmouseout="this.style.background='var(--bg)';this.style.borderColor='var(--border)';this.style.color='var(--text)'">2da Quincena</button>
          <button onclick="_setQuincena(0)" style="padding:9px 14px;border:1px solid var(--border);border-radius:10px;background:var(--bg);font-family:var(--sans);font-size:13px;font-weight:600;color:var(--text);cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background='var(--accent-dim)';this.style.borderColor='var(--accent)';this.style.color='var(--accent)';" onmouseout="this.style.background='var(--bg)';this.style.borderColor='var(--border)';this.style.color='var(--text)'">Mes completo</button>
          <button onclick="document.getElementById('personalDesde').value='';document.getElementById('personalHasta').value='';_buildPersonalView(state.historial_lavados||[]);" style="padding:9px 14px;border:1px solid var(--border);border-radius:10px;background:var(--bg);font-family:var(--sans);font-size:13px;font-weight:600;color:var(--muted);cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background='var(--red-dim)';this.style.borderColor='var(--red)';this.style.color='var(--red)';" onmouseout="this.style.background='var(--bg)';this.style.borderColor='var(--border)';this.style.color='var(--muted)'">✕ Limpiar</button>
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

  for (const [name, lavados] of Object.entries(lavadores).sort((a, b) => a[0].localeCompare(b[0]))) {
    let pagoEstimado = 0;
    let totalLavados = 0;
    lavados.forEach(l => {
      const tipo = l.tipo_lavado || 'General';
      const tarifa = parseFloat(tarifas[tipo] || 0);
      const nLavadores = (l.lavadores && l.lavadores.length) ? l.lavadores.length : 1;
      pagoEstimado += tarifa / nLavadores;
      totalLavados += 1 / nLavadores;
    });
    pagoEstimado = Math.round(pagoEstimado);
    
    const displayTotalLavados = Number(totalLavados.toFixed(2));

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
        if (tipo.toLowerCase().includes('sencillo')) { badgeBg = 'rgba(16,185,129,0.1)'; badgeColor = '#059669'; }
        if (tipo.toLowerCase().includes('enjuague')) { badgeBg = 'rgba(245,158,11,0.1)'; badgeColor = '#d97706'; }
        const coLavs = (l.lavadores || []).filter(x => x.trim().toUpperCase() !== name);
        const coInfo = coLavs.length ? `<span style="font-size:10px;color:var(--muted);margin-left:4px;">+ ${coLavs.join(', ')}</span>` : '';

        return `
          <div style="display:flex; justify-content:space-between; align-items:center; padding: 16px 0; border-bottom: ${index === lavados.length - 1 ? 'none' : '1px solid var(--border)'}; gap: 12px; transition: background 0.2s; border-radius: 8px;">
            <div style="display:flex; align-items:center; gap: 16px;">
              <div style="width:40px; height:40px; border-radius:10px; background:var(--bg); display:flex; align-items:center; justify-content:center; font-size:16px; border:1px solid var(--border2); box-shadow:0 2px 4px rgba(0,0,0,0.02);">🚐</div>
              <div>
                <div style="font-weight: 800; color: var(--text); font-size: 16px; letter-spacing: -0.01em;">${l.placa}${coInfo}</div>
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
              <div style="font-size: 16px; font-weight: 800; color: var(--blue); line-height: 1;">${displayTotalLavados}</div>
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
window._buildPersonalView = _buildPersonalView;
window.descargarPDF = descargarPDF;
