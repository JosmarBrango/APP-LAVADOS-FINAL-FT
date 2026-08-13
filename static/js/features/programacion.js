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
  const filtroVeh = document.getElementById('progVehiculosFiltro')?.value || 'todos';

  if (!startDate || !endDate) return window.showToast('Selecciona un rango de fechas', 'err');
  if (new Date(startDate) > new Date(endDate)) return window.showToast('La fecha de inicio debe ser anterior a la de fin', 'err');

  const body = document.getElementById('progBody');
  if (!body) return;
  body.innerHTML = `<div style="color:var(--muted);font-size:13px;padding:20px;width:100%;text-align:center;">Calculando programación…</div>`;

  let placas = [];
  if (filtroVeh === 'sin_lavado') {
    placas = window.state.vehiculos.filter(v => v.lavGen === 0).map(v => v.placa);
  }

  try {
    const data = await window.apiCall('/api/programacion', 'POST', { start_date: startDate, end_date: endDate, placas });

    window.state.progConfig = { start_date: startDate, end_date: endDate, placas };

    // Activar el botón de descarga en Centro de Reportes
    const btnDescarga = document.getElementById('btnDescargaProgramacion');
    if (btnDescarga) {
      btnDescarga.disabled = false;
      btnDescarga.style.opacity = '1';
      btnDescarga.style.cursor = 'pointer';
    }
    const pdfRango = document.getElementById('pdfRango');
    if (pdfRango) {
      pdfRango.textContent = `✓ Del ${startDate} al ${endDate}`;
      pdfRango.style.color = 'var(--green)';
      pdfRango.style.background = 'rgba(5,150,105,0.1)';
      pdfRango.style.border = 'none';
    }

    const diasUnicos = [...new Set(data.programacion.filter(p => p.diaAsignado).map(p => p.diaAsignado))].sort();
    
    // El backend nos debe devolver qué vehículos no pudieron ser asignados
    // por ahora lo calculamos en el frontend temporalmente
    const asignados = new Set(data.programacion.filter(p => p.diaAsignado).map(p => p.placa));
    let vehiculosObjetivo = window.state.vehiculos;
    if (placas.length > 0) vehiculosObjetivo = window.state.vehiculos.filter(v => placas.includes(v.placa));
    const sinAsignar = vehiculosObjetivo.filter(v => !asignados.has(v.placa));

    let html = '';

    // Columna "Sin Asignar"
    if (sinAsignar.length > 0) {
      document.getElementById('toggleUnassignedBtn').style.display = 'inline-block';
      html += `
        <div class="kb-col" id="col-unassigned">
          <div class="kb-hdr">
            <div>
              <div class="kb-title" style="color:var(--red);">No asignados</div>
              <div class="kb-sub">Exceden capacidad (${sinAsignar.length})</div>
            </div>
            <div class="kb-count" style="background:var(--red);color:#fff">${sinAsignar.length}</div>
          </div>
          <div class="kb-cards">
            ${sinAsignar.map(v => `
              <div class="kb-card">
                <div class="kbc-placa">${v.placa}</div>
                <div class="kbc-mun">${v.mun}</div>
                <div style="font-size:11px;color:var(--muted);margin-top:6px;padding-top:6px;border-top:1px dashed var(--border);">
                  El sistema no encontró cupo para este vehículo en las fechas seleccionadas.
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    } else {
      document.getElementById('toggleUnassignedBtn').style.display = 'none';
    }

    // Columnas por día
    diasUnicos.forEach(fecha => {
      const lavsDia = data.programacion.filter(p => p.diaAsignado === fecha);
      lavsDia.sort((a, b) => (a.horaMejorDia || '').localeCompare(b.horaMejorDia || ''));
      
      const parts = fecha.split('-');
      const dObj = new Date(parts[0], parts[1] - 1, parts[2]);
      const diaTxt = window.DOW_FULL[dObj.getDay()];

      html += `
        <div class="kb-col">
          <div class="kb-hdr">
            <div>
              <div class="kb-title">${diaTxt}</div>
              <div class="kb-sub">${fecha}</div>
            </div>
            <div class="kb-count">${lavsDia.length}</div>
          </div>
          <div class="kb-cards">
            ${lavsDia.map(p => {
              const histVeh = window.state.vehiculos.find(v => v.placa === p.placa);
              const m = histVeh ? histVeh.mun : 'N/D';
              
              // Determinar color de la hora
              const mns = p.bestMin;
              const cl = mns <= 870 ? '#10b981' : mns <= 930 ? '#3b82f6' : mns <= 990 ? '#f59e0b' : '#ef4444';
              
              return `
                <div class="kb-card">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start">
                    <div class="kbc-placa">${p.placa}</div>
                    <div class="kbc-time" style="color:${cl};border-color:${cl}33;background:${cl}11">
                      ${p.horaMejorDia || 'N/D'}
                    </div>
                  </div>
                  <div class="kbc-mun">${m}</div>
                  <div class="kbc-motivo">${(p.turno && p.turno.label) || ''}</div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      `;
    });

    if (html === '') {
      html = `<div style="color:var(--muted);font-size:13px;padding:20px;width:100%;text-align:center;">No hay lavados programables en este rango.</div>`;
    }
    body.innerHTML = html;
  } catch (e) {
    body.innerHTML = `<div style="color:var(--red);font-size:13px;padding:20px">Error generando programación.</div>`;
  }
}

function toggleUnassigned() {
  const col = document.getElementById('col-unassigned');
  const btn = document.getElementById('toggleUnassignedBtn');
  if (col.style.display === 'none') {
    col.style.display = 'flex';
    btn.textContent = 'Ocultar Sin Asignar';
  } else {
    col.style.display = 'none';
    btn.textContent = 'Mostrar Sin Asignar';
  }
}

window.initFechasProg = initFechasProg;
window.renderProgramacion = renderProgramacion;
window.toggleUnassigned = toggleUnassigned;
