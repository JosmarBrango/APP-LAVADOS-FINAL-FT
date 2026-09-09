// ─── Vista Todos los Lavados ──────────────────────────────────────────────────
function _populateLavPersonal() {
  const lavPersonal = document.getElementById('lavPersonal');
  if (lavPersonal) {
    const curVal = lavPersonal.value;
    lavPersonal.innerHTML = '<option value="">Todos los lavadores</option>';
    (window._LAVADORES_SISTEMA || []).forEach(l => {
      const opt = document.createElement('option');
      opt.value = l;
      opt.textContent = l;
      if (l === curVal) opt.selected = true;
      lavPersonal.appendChild(opt);
    });
  }
}

function _populatePlacasSelect() {
  const muns = window.getMunicipios();
  const lavMun2 = document.getElementById('lavMun2');
  if (lavMun2) {
    const curMun = lavMun2.value;
    lavMun2.innerHTML = '<option value="">Todos los municipios</option>' +
      muns.map(m => `<option value="${m}">${m}</option>`).join('');
    if (muns.includes(curMun)) lavMun2.value = curMun;
  }

  const dataList = document.getElementById('placasList');
  if (dataList) {
    dataList.innerHTML = (window.state.vehiculos || [])
      .map(v => `<option value="${v.placa}">${v.mun || 'N/D'}</option>`).join('');
  }
}

function _lavLimpiarFiltros() {
  document.getElementById('lavTipo').value = '';
  document.getElementById('lavMun2').value = '';
  document.getElementById('lavPersonal').value = '';
  document.getElementById('lavSearch').value = '';
  document.getElementById('lavDesde').value = '';
  document.getElementById('lavHasta').value = '';
  document.querySelectorAll('.lav-chip').forEach(c => c.classList.remove('active'));
  renderTodosLavados();
}

function _lavSetDateRange(rango, btn) {
  document.querySelectorAll('.lav-chip').forEach(c => c.classList.remove('active'));
  if (btn) btn.classList.add('active');
  const d = new Date();
  const y = d.getFullYear(), m = d.getMonth(), date = d.getDate();
  const dEl = document.getElementById('lavDesde');
  const hEl = document.getElementById('lavHasta');

  if (rango === 'hoy') {
    const hoyStr = d.toISOString().split('T')[0];
    dEl.value = hoyStr;
    hEl.value = hoyStr;
  } else if (rango === 'semana') {
    const day = d.getDay() || 7;
    const diff = d.getDate() - day + 1;
    const lun = new Date(d.setDate(diff));
    const dom = new Date(d.setDate(diff + 6));
    dEl.value = lun.toISOString().split('T')[0];
    hEl.value = dom.toISOString().split('T')[0];
  } else if (rango === 'mes') {
    const prim = new Date(y, m, 1);
    const ult = new Date(y, m + 1, 0);
    dEl.value = prim.toISOString().split('T')[0];
    hEl.value = ult.toISOString().split('T')[0];
  }
  renderTodosLavados();
}

// Helper local 
const _fmtMins = m => {
  if (m === null || m === undefined || m < 0) return '—';
  if (m < 60) return `${m} min`;
  const hrs = Math.floor(m / 60);
  const min = m % 60;
  return min > 0 ? `${hrs}h ${min}m` : `${hrs}h`;
};

function renderTodosLavados() {
  const tipo = document.getElementById('lavTipo')?.value || '';
  const mun = document.getElementById('lavMun2')?.value || '';
  const personal = document.getElementById('lavPersonal')?.value || '';
  const search = document.getElementById('lavSearch')?.value.toLowerCase() || '';
  const desde = document.getElementById('lavDesde')?.value || '';
  const hasta = document.getElementById('lavHasta')?.value || '';

  // Diccionario vehiculos placa -> mun
  const vMap = {};
  window.state.vehiculos.forEach(v => { vMap[v.placa] = v.mun || 'N/D'; });

  let data = [...window.state.historial];
  if (tipo) data = data.filter(l => l.tipo_lavado === tipo || (tipo === 'Alistamiento' && l.tipo_lavado === 'Sencillo') || (tipo === 'Motor' && l.tipo_lavado === 'Enjuague'));
  if (mun) data = data.filter(l => (vMap[l.placa] || '') === mun);
  if (personal) data = data.filter(l => l.lavador === personal || (l.lavadores && l.lavadores.includes(personal)));
  if (search) data = data.filter(l => l.placa.toLowerCase().includes(search));
  if (desde) data = data.filter(l => l.fecha >= desde);
  if (hasta) data = data.filter(l => l.fecha <= hasta);

  data.sort((a, b) => {
    if (a.fecha !== b.fecha) return (b.fecha || '').localeCompare(a.fecha || '');
    return (b.hora_inicio || '').localeCompare(a.hora_inicio || '');
  });

  const body = document.getElementById('lavBody');
  const empty = document.getElementById('lavEmptyState');
  const countEl = document.getElementById('lavCount');

  if (countEl) countEl.textContent = `${data.length} registros`;

  // Calcular KPIs en base a los datos filtrados
  let gen = 0, sen = 0, enj = 0;
  data.forEach(l => {
    if (l.tipo_lavado === 'General') gen++;
    else if (l.tipo_lavado === 'Alistamiento' || l.tipo_lavado === 'Sencillo') sen++;
    else if (l.tipo_lavado === 'Motor' || l.tipo_lavado === 'Enjuague') enj++;
  });
  const elKpiTotal = document.getElementById('lavKpiTotal'); if (elKpiTotal) elKpiTotal.textContent = data.length;
  const elKpiGen = document.getElementById('lavKpiGen'); if (elKpiGen) elKpiGen.textContent = gen;
  const elKpiSen = document.getElementById('lavKpiSen'); if (elKpiSen) elKpiSen.textContent = sen;
  const elKpiEnj = document.getElementById('lavKpiEnj'); if (elKpiEnj) elKpiEnj.textContent = enj;

  if (data.length === 0) {
    if (body) body.innerHTML = '';
    if (empty) empty.style.display = 'flex';
  } else {
    if (empty) empty.style.display = 'none';
    if (body) {
      body.innerHTML = data.map(l => {
        let badgeBg = 'var(--bg)', badgeColor = 'var(--text)', bBorder = 'var(--border)';
        const tl = l.tipo_lavado || 'General';
        if (tl === 'General') { badgeBg = '#E0F2FE'; badgeColor = '#0284C7'; bBorder = '#BAE6FD'; }
        if (tl === 'Alistamiento' || tl === 'Sencillo') { badgeBg = '#D1FAE5'; badgeColor = '#059669'; bBorder = '#A7F3D0'; }
        if (tl === 'Motor' || tl === 'Enjuague') { badgeBg = '#FEF3C7'; badgeColor = '#D97706'; bBorder = '#FDE68A'; }

        const lavadoMun = vMap[l.placa] || l.municipio_lavado || 'N/D';
        const isAdmin = window.USER_ROLE === 'admin';

        // 1. Lavadores estilizados en pills sin romper texto
        const lavadoresHtml = _renderLavadoresCelda(l);

        // 2. Fecha formateada (ej. "03 Sep 2026")
        const fechaHtml = _formatearFechaTabla(l.fecha);

        // 3. Botones de Control de Calidad (Fotos & Checklist)
        const fotos = l.fotos || [];
        const chk = l.checklist || {};
        const marcados = Object.keys(chk).filter(k => chk[k] === true).length;

        let calidadBtns = [];
        if (fotos.length > 0) {
          calidadBtns.push(`<button class="btn-calidad btn-calidad-foto" onclick="abrirGaleriaFotos(${JSON.stringify(fotos).replace(/"/g, '&quot;')})" title="Ver ${fotos.length} foto(s) de evidencia">📷 ${fotos.length}</button>`);
        }
        if (marcados > 0) {
          calidadBtns.push(`<button class="btn-calidad btn-calidad-chk" onclick="abrirModalChecklist('${l.id}')" title="Verificación de calidad: ${marcados} ítem(s) cumplido(s)">✅ ${marcados}</button>`);
        } else if (l.checklist && typeof l.checklist === 'object' && Object.keys(l.checklist).length > 0) {
          calidadBtns.push(`<button class="btn-calidad" style="background:var(--s2);border-color:var(--border);color:var(--muted);" onclick="abrirModalChecklist('${l.id}')" title="Checklist sin marcar">📋 0</button>`);
        }

        const calidadCelda = calidadBtns.length > 0
          ? `<div class="lav-calidad-wrap">${calidadBtns.join('')}</div>`
          : `<span style="color:var(--muted);font-size:12px;">—</span>`;

        return `
        <tr>
          <td><span class="placa">${l.placa}</span></td>
          <td style="font-size:12.5px;color:var(--text-2);font-weight:600;white-space:nowrap;">${lavadoMun}</td>
          <td><span class="badge" style="background:${badgeBg};color:${badgeColor};border:1px solid ${bBorder};white-space:nowrap;">${tl}</span></td>
          <td>${fechaHtml}</td>
          <td style="font-family:var(--mono);font-size:12.5px;text-align:center;white-space:nowrap;">${l.hora_llegada || '—'}</td>
          <td style="font-family:var(--mono);font-size:12.5px;text-align:center;white-space:nowrap;">${l.hora_inicio || '—'}<span style="color:var(--muted);margin:0 3px;">→</span>${l.hora_fin || '—'}</td>
          <td>${lavadoresHtml}</td>
          <td style="text-align:center;">${calidadCelda}</td>
          <td style="text-align:center;white-space:nowrap;">
            <span class="lav-origen-pill" title="${(l.origen || '').toLowerCase().includes('qr') ? 'Registro mediante código QR' : 'Registro desde Panel Web'}">
              ${(l.origen || '').toLowerCase().includes('qr') ? '📱 QR' : '💻 Panel'}
            </span>
          </td>
          ${isAdmin ? `
          <td style="text-align:right;white-space:nowrap;">
            <button class="act-btn del" onclick="quitarLavado('${l.id}')" title="Eliminar registro">Eliminar</button>
          </td>` : ''}
        </tr>`;
      }).join('');
    }
  }
}

// ── Formateo estético de Fecha (ej. 03 Sep 2026) ──────────────────────────────
function _formatearFechaTabla(f) {
  if (!f) return '<span style="color:var(--muted)">—</span>';
  const parts = String(f).trim().split('-');
  if (parts.length === 3) {
    const meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    const dia = parts[2];
    const mesIdx = parseInt(parts[1], 10) - 1;
    const mes = meses[mesIdx] || parts[1];
    const anio = parts[0];
    return `
      <div class="lav-fecha-badge" title="${dia}/${parts[1]}/${anio}">
        <span class="lav-fecha-dia">${dia} ${mes}</span>
        <span class="lav-fecha-anio">${anio}</span>
      </div>`;
  }
  return `<span style="white-space:nowrap;font-family:var(--mono);font-size:12px;">${f}</span>`;
}

// ── Formateo de nombres propios de lavadores ─────────────────────────────────
function _formatearNombre(nombre) {
  if (!nombre) return '';
  return String(nombre).toLowerCase().split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

// ── Renderizado de celda de lavadores (evita amontonamiento con pills) ────────
function _renderLavadoresCelda(l) {
  let lavs = [];
  if (Array.isArray(l.lavadores) && l.lavadores.length > 0) {
    lavs = l.lavadores.map(x => String(x).trim()).filter(Boolean);
  } else if (l.lavador) {
    lavs = [String(l.lavador).trim()];
  }

  if (lavs.length === 0) {
    return `<span style="font-size:11px;color:var(--muted)">—</span>`;
  }

  // Si hay 1 o 2 lavadores: mostrar directamente en pastillas
  if (lavs.length <= 2) {
    return `
      <div class="lav-workers-stack">
        ${lavs.map(name => `
          <span class="lav-worker-pill" title="${name}">
            <span>👤</span> ${_formatearNombre(name)}
          </span>
        `).join('')}
      </div>`;
  }

  // Si hay 3 o más: mostramos los 2 primeros + botón "+N más"
  const primeros = lavs.slice(0, 2);
  const restantes = lavs.length - 2;
  const todosEscapados = JSON.stringify(lavs).replace(/"/g, '&quot;');

  return `
    <div class="lav-workers-stack">
      ${primeros.map(name => `
        <span class="lav-worker-pill" title="${name}">
          <span>👤</span> ${_formatearNombre(name)}
        </span>
      `).join('')}
      <button class="lav-worker-more" onclick="abrirModalEquipo('${l.placa}', ${todosEscapados})" title="Equipo completo: ${lavs.join(', ')}">
        👥 +${restantes} más
      </button>
    </div>`;
}

async function loadModalLavadores() {
  try {
    let lavadores = window.state.lavadoresSistema || window._LAVADORES_SISTEMA || [];
    if (!Array.isArray(lavadores) || lavadores.length === 0) {
      try {
        const res = await fetch('/api/lavadores?t=' + Date.now());
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            lavadores = data;
            window.state.lavadoresSistema = lavadores;
            window._LAVADORES_SISTEMA = lavadores;
          }
        }
      } catch (e) {
        console.error('Error obteniendo lavadores para el modal:', e);
      }
    }

    document.querySelectorAll('.ml-lav-select').forEach(sel => {
      const cur = sel.value;
      sel.innerHTML = '<option value="" disabled selected>Selecciona un lavador...</option>';
      (lavadores || []).forEach(lav => {
        const o = document.createElement('option');
        o.value = lav; o.textContent = lav;
        if (lav === cur) o.selected = true;
        sel.appendChild(o);
      });
    });
  } catch (e) {
    console.error('Error cargando lavadores en modal:', e);
  }
}

function addModalLavRow(selectedValue = '') {
  const list = document.getElementById('mlLavadoresList');
  if (!list) return;

  const row = document.createElement('div');
  row.className = 'lav-row';
  row.style.cssText = 'display:flex;gap:8px;align-items:center;';

  const sel = document.createElement('select');
  sel.name = 'mlLavadorSel';
  sel.className = 'ml-lav-select';
  sel.style.cssText = 'flex:1;padding:11px 14px;border-radius:10px;border:1.5px solid var(--border);background:var(--s2);font-family:var(--sans);font-size:14px;color:var(--text);outline:none;';
  sel.innerHTML = `<option value="" disabled ${selectedValue ? '' : 'selected'}>Selecciona un lavador...</option>`;

  const lavadores = window.state.lavadoresSistema || window._LAVADORES_SISTEMA || [];
  lavadores.forEach(lav => {
    const o = document.createElement('option');
    o.value = lav;
    o.textContent = lav;
    if (lav === selectedValue) o.selected = true;
    sel.appendChild(o);
  });

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.style.cssText = 'padding:10px 14px;border-radius:10px;border:1px solid rgba(239,68,68,0.2);background:rgba(239,68,68,0.08);color:var(--red);font-weight:700;font-size:14px;cursor:pointer;line-height:1;display:flex;align-items:center;justify-content:center;';
  btn.innerHTML = '✕';
  btn.title = 'Eliminar lavador';
  btn.onclick = () => row.remove();

  row.appendChild(sel);
  row.appendChild(btn);
  list.appendChild(row);
}

function _setupModalCalc() {
  const calc = () => {
    const hl = document.getElementById('mlHoraLlegada')?.value;
    const hi = document.getElementById('mlHoraInicio')?.value;
    const hf = document.getElementById('mlHoraFin')?.value;
    const diff = (a, b) => { if (!a || !b) return null; const [ah, am] = a.split(':').map(Number), [bh, bm] = b.split(':').map(Number); let d = (bh * 60 + bm) - (ah * 60 + am); return d < 0 ? d + 1440 : d; };
    const espera = diff(hl, hi), lavado = diff(hi, hf);
    const badges = document.getElementById('mlCalcBadges');
    if (badges) { badges.style.display = (espera !== null || lavado !== null) ? 'flex' : 'none'; }
    const ve = document.getElementById('mlValEspera'); if (ve) ve.textContent = window._fmtMins(espera);
    const vl = document.getElementById('mlValLavado'); if (vl) vl.textContent = window._fmtMins(lavado);
  };
  ['mlHoraLlegada', 'mlHoraInicio', 'mlHoraFin'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', calc);
  });
}

function openLavadoModal(origen = 'dashboard_manual') {
  window._modalLavadoOrigen = origen || 'dashboard_manual';
  const list = document.getElementById('mlLavadoresList');
  if (list) {
    list.innerHTML = `<div style="display:flex;gap:8px;align-items:center;" class="lav-row">
      <select name="mlLavadorSel" class="ml-lav-select" style="flex:1;padding:11px 14px;border-radius:10px;border:1.5px solid var(--border);background:var(--s2);font-family:var(--sans);font-size:14px;color:var(--text);outline:none;">
        <option value="" disabled selected>Selecciona un lavador...</option>
      </select>
    </div>`;
  }
  loadModalLavadores();
  setTimeout(_setupModalCalc, 100);

  const form = document.getElementById('formLavado');
  if (form) {
    const placaEl = document.getElementById('mlPlaca');
    if (placaEl) placaEl.value = '';
    const tipoEl = document.getElementById('mlTipoLavado');
    if (tipoEl) { tipoEl.value = ''; }
    const munEl = document.getElementById('mlMunicipio');
    if (munEl) munEl.value = '';
    const hlEl = document.getElementById('mlHoraLlegada');
    if (hlEl) hlEl.value = '';
    const hiEl = document.getElementById('mlHoraInicio');
    if (hiEl) hiEl.value = '';
    const hfEl = document.getElementById('mlHoraFin');
    if (hfEl) hfEl.value = '';
  }

  // Resetear fotos del modal
  _mlFotosFiles = [];
  _mlRenderFotoPreviews();

  // Resetear checklist del modal
  const clWrap = document.getElementById('mlChecklistWrap');
  if (clWrap) clWrap.innerHTML = '<div style="font-size:12px;color:var(--muted);text-align:center;padding:8px;">Selecciona el tipo de lavado primero</div>';

  const badges = document.getElementById('mlCalcBadges');
  if (badges) badges.style.display = 'none';

  const fechaVis = document.getElementById('mlFechaVisible');
  const fechaHid = document.getElementById('mlFecha');
  if (fechaVis && fechaHid) {
    const todayStr = new Date().toISOString().split('T')[0];
    fechaVis.value = todayStr;
    fechaHid.value = todayStr;
    fechaVis.style.background = 'var(--s3)';
    fechaVis.style.cursor = 'default';
    fechaVis.title = 'La fecha se establece automáticamente al día de hoy';
  }
  window.openModal('modalLavado');
}

async function saveLavado(e) {
  if (e) e.preventDefault();
  const placa = document.getElementById('mlPlaca')?.value.trim().toUpperCase();
  const tipo_lavado = document.getElementById('mlTipoLavado')?.value;
  const municipio = document.getElementById('mlMunicipio')?.value.trim();
  const fecha = document.getElementById('mlFecha')?.value;
  const hora_llegada = document.getElementById('mlHoraLlegada')?.value;
  const hora_inicio = document.getElementById('mlHoraInicio')?.value;
  const hora_fin = document.getElementById('mlHoraFin')?.value;

  const lavSelects = document.querySelectorAll('#mlLavadoresList .ml-lav-select');
  const lavadores = Array.from(lavSelects).map(s => s.value).filter(v => v && v.trim() !== '');

  if (!placa) {
    return window.showToast('Ingresa la placa del vehículo', 'err');
  }
  if (!tipo_lavado) {
    return window.showToast('Selecciona el tipo de lavado', 'err');
  }
  if (lavadores.length === 0) {
    return window.showToast('Debes seleccionar al menos un lavador', 'err');
  }

  // Recopilar checklist
  const checklistChecked = document.querySelectorAll('#mlChecklistWrap input[type="checkbox"]:checked');
  const checklist = {};
  checklistChecked.forEach(cb => { checklist[cb.value] = true; });

  try {
    // Primero subir las fotos si hay
    let fotosUrls = [];
    if (_mlFotosFiles.length > 0) {
      const fdFotos = new FormData();
      _mlFotosFiles.forEach(f => fdFotos.append('fotos', f));
      fdFotos.append('lavado_id', 'panel_' + Date.now());
      const fotosRes = await fetch('/api/lavado/upload_foto', {
        method: 'POST',
        body: fdFotos
      });
      if (fotosRes.ok) {
        const fotosData = await fotosRes.json();
        fotosUrls = fotosData.fotos || [];
      }
    }

    const payload = {
      placa,
      tipo_lavado,
      municipio,
      fecha,
      hora_llegada,
      hora_inicio,
      hora_fin,
      lavadores,
      origen: window._modalLavadoOrigen || 'dashboard_manual',
      fotos: fotosUrls,
      checklist,
    };

    const res = await window.apiCall('/api/lavado/add_manual', 'POST', payload);
    if (res && res.error) {
      return window.showToast(res.error, 'err');
    }

    window._modalLavadoOrigen = 'dashboard_manual';
    window.closeModal('modalLavado');
    window.showToast('✅ Lavado registrado con éxito');
    await window.refreshAllData();
  } catch (err) {
    console.error(err);
    window.showToast('Error al registrar el lavado', 'err');
  }
}

async function quitarLavado(id) {
  if (!confirm('¿Estás seguro de eliminar este registro de lavado?')) return;
  try {
    const res = await window.apiCall('/api/lavado/remove', 'POST', { id });
    if (res && res.error) {
      return window.showToast(res.error, 'err');
    }
    window.showToast('Lavado eliminado correctamente');
    await window.refreshAllData();
  } catch (e) {
    console.error(e);
    window.showToast('Error al eliminar lavado', 'err');
  }
}

// ── Checklist dinámico para el modal admin ────────────────────────────────────
const ML_CHECKLIST_ITEMS = {
  'Alistamiento': [
    { key: 'exterior_limpio', label: 'Exterior limpio' },
    { key: 'llantas_limpias', label: 'Llantas y ruedas limpias' },
  ],
  'General': [
    { key: 'exterior_limpio', label: 'Exterior limpio' },
    { key: 'llantas_limpias', label: 'Llantas y ruedas limpias' },
    { key: 'cero_residuos', label: 'Cero residuos en la carrocería' },
  ],
  'Motor': [
    { key: 'motor_limpio', label: 'Motor limpio / sin grasa' },
  ],
};

function mlActualizarChecklist(tipo) {
  const wrap = document.getElementById('mlChecklistWrap');
  if (!wrap) return;
  const items = ML_CHECKLIST_ITEMS[tipo] || [];
  if (!items.length) {
    wrap.innerHTML = '<div style="font-size:12px;color:var(--muted);text-align:center;padding:8px;">Sin ítems para este tipo</div>';
    return;
  }
  wrap.innerHTML = items.map(item => `
    <div class="ml-chk-item" onclick="mlToggleChk(this)" data-key="${item.key}" style="display:flex;align-items:center;gap:10px;background:var(--s2);border:1.5px solid var(--border);border-radius:12px;padding:11px 13px;cursor:pointer;transition:all .2s;user-select:none;">
      <div class="ml-chk-box" style="width:20px;height:20px;border-radius:6px;border:2px solid var(--border);background:#fff;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .2s;font-size:12px;"></div>
      <span style="font-size:13px;font-weight:600;color:var(--text);">${item.label}</span>
      <input type="checkbox" name="ml_checklist" value="${item.key}" style="display:none;">
    </div>
  `).join('');
}

function mlToggleChk(el) {
  const isNowChecked = !el.classList.contains('ml-checked');
  el.classList.toggle('ml-checked', isNowChecked);
  el.style.background = isNowChecked ? '#F0FDF4' : 'var(--s2)';
  el.style.borderColor = isNowChecked ? '#86EFAC' : 'var(--border)';
  const box = el.querySelector('.ml-chk-box');
  if (box) {
    box.textContent = isNowChecked ? '✓' : '';
    box.style.background = isNowChecked ? 'var(--green,#10B981)' : '#fff';
    box.style.borderColor = isNowChecked ? 'var(--green,#10B981)' : 'var(--border)';
    box.style.color = isNowChecked ? '#fff' : 'inherit';
  }
  const cb = el.querySelector('input[type="checkbox"]');
  if (cb) cb.checked = isNowChecked;
}

// ── Fotos para el modal admin ──────────────────────────────────────────────
let _mlFotosFiles = [];
let _mlCamaraStream = null;
let _mlCamaraFacingMode = 'environment';
let _mlCamaraCanvas = null;
let _camaraModo = null;

function mlAgregarFotosPreview(input) {
  const nuevas = Array.from(input.files);
  const disponibles = 3 - _mlFotosFiles.length;
  _mlFotosFiles = _mlFotosFiles.concat(nuevas.slice(0, disponibles));
  _mlRenderFotoPreviews();
  input.value = '';
}

function _mlRenderFotoPreviews() {
  const wrap = document.getElementById('mlFotoPreviewWrap');
  const btnWrap = document.getElementById('mlFotoBtnsWrap');
  const btnTxt = document.getElementById('mlBtnCamaraTxt');
  if (!wrap) return;

  wrap.innerHTML = _mlFotosFiles.map((f, i) => {
    const url = URL.createObjectURL(f);
    return `<div style="position:relative;width:100%;padding-top:100%;border-radius:10px;overflow:hidden;border:1.5px solid var(--border);background:var(--s2);">
      <img src="${url}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;" alt="Foto ${i + 1}">
      <button type="button" onclick="mlEliminarFoto(${i})" style="position:absolute;top:4px;right:4px;background:rgba(15,23,42,.72);color:#fff;border:none;border-radius:50%;width:22px;height:22px;font-size:11px;display:flex;align-items:center;justify-content:center;cursor:pointer;">✕</button>
    </div>`;
  }).join('');

  const lleno = _mlFotosFiles.length >= 3;
  if (btnWrap) { btnWrap.style.opacity = lleno ? '0.4' : '1'; btnWrap.style.pointerEvents = lleno ? 'none' : 'auto'; }
  if (btnTxt) btnTxt.textContent = _mlFotosFiles.length === 0 ? 'Tomar foto' : `${_mlFotosFiles.length}/3 — Otra foto`;
}

function mlEliminarFoto(idx) {
  _mlFotosFiles.splice(idx, 1);
  _mlRenderFotoPreviews();
}

// ── Cámara para el modal admin ─────────────────────────────────────────────
async function mlAbrirCamara() {
  if (_mlFotosFiles.length >= 3) return;

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    const inp = document.getElementById('mlInputCamaraNativa');
    if (inp) inp.click();
    return;
  }

  _camaraModo = 'ml';
  window._camaraModo = 'ml'; // Sincronizar con modal_camara.html
  const modal = document.getElementById('camaraModal');
  if (!modal) {
    const inp = document.getElementById('mlInputCamaraNativa');
    if (inp) inp.click();
    return;
  }

  modal.classList.add('activo');
  document.body.style.overflow = 'hidden';
  _mlActualizarHUD();

  try {
    await _mlIniciarStream();
  } catch (err) {
    console.warn('[Cámara panel] Error al iniciar stream:', err);
    mlCerrarCamara();
    const inp = document.getElementById('mlInputCamaraNativa');
    if (inp) inp.click();
  }
}

async function _mlIniciarStream() {
  if (_mlCamaraStream) {
    _mlCamaraStream.getTracks().forEach(t => t.stop());
    _mlCamaraStream = null;
  }
  const video = document.getElementById('camaraVideo');
  const constraints = {
    video: { facingMode: { ideal: _mlCamaraFacingMode }, width: { ideal: 1920 }, height: { ideal: 1080 } },
    audio: false
  };
  _mlCamaraStream = await navigator.mediaDevices.getUserMedia(constraints);
  video.srcObject = _mlCamaraStream;
  await video.play();
}

function mlCerrarCamara() {
  if (_mlCamaraStream) {
    _mlCamaraStream.getTracks().forEach(t => t.stop());
    _mlCamaraStream = null;
  }
  const video = document.getElementById('camaraVideo');
  if (video) video.srcObject = null;
  const modal = document.getElementById('camaraModal');
  if (modal) modal.classList.remove('activo');
  document.body.style.overflow = '';
  _camaraModo = null;
  window._camaraModo = null; // Sincronizar con modal_camara.html
}

async function mlFlipCamara() {
  _mlCamaraFacingMode = _mlCamaraFacingMode === 'environment' ? 'user' : 'environment';
  try { await _mlIniciarStream(); } catch(e) {
    _mlCamaraFacingMode = _mlCamaraFacingMode === 'environment' ? 'user' : 'environment';
    await _mlIniciarStream();
  }
}

function mlCapturarFoto() {
  if (_mlFotosFiles.length >= 3) { mlCerrarCamara(); return; }
  const video = document.getElementById('camaraVideo');
  if (!video || !_mlCamaraStream) return;

  const flash = document.getElementById('camaraFlash');
  if (flash) { flash.classList.add('on'); setTimeout(() => flash.classList.remove('on'), 120); }
  if (navigator.vibrate) navigator.vibrate(40);

  if (!_mlCamaraCanvas) _mlCamaraCanvas = document.createElement('canvas');
  _mlCamaraCanvas.width = video.videoWidth || 1280;
  _mlCamaraCanvas.height = video.videoHeight || 720;
  const ctx = _mlCamaraCanvas.getContext('2d');
  if (_mlCamaraFacingMode === 'user') { ctx.translate(_mlCamaraCanvas.width, 0); ctx.scale(-1, 1); }
  ctx.drawImage(video, 0, 0, _mlCamaraCanvas.width, _mlCamaraCanvas.height);

  _mlCamaraCanvas.toBlob(blob => {
    if (!blob) return;
    const file = new File([blob], `foto_panel_${Date.now()}.jpg`, { type: 'image/jpeg' });
    _mlFotosFiles.push(file);
    _mlRenderFotoPreviews();
    _mlActualizarHUD();
    _mlActualizarThumbs();
    if (_mlFotosFiles.length >= 3) setTimeout(() => mlCerrarCamara(), 400);
  }, 'image/jpeg', 0.88);
}

function _mlActualizarHUD() {
  const counter = document.getElementById('camaraCounter');
  if (counter) counter.textContent = `📷 ${_mlFotosFiles.length} / 3`;
  const finBtn = document.getElementById('camaraFinBtn');
  if (finBtn) finBtn.classList.toggle('visible', _mlFotosFiles.length > 0);
}

function _mlActualizarThumbs() {
  const thumbsWrap = document.getElementById('camaraThumbs');
  if (!thumbsWrap) return;
  thumbsWrap.innerHTML = '';
  for (let i = 0; i < 3; i++) {
    if (i < _mlFotosFiles.length) {
      const url = URL.createObjectURL(_mlFotosFiles[i]);
      const img = document.createElement('img');
      img.src = url; img.className = 'camara-thumb-item'; img.alt = `Foto ${i+1}`;
      thumbsWrap.appendChild(img);
    } else {
      const empty = document.createElement('div');
      empty.className = 'camara-thumb-empty';
      thumbsWrap.appendChild(empty);
    }
  }
}

// ── Lightbox de galería de fotos ─────────────────────────────────────────────
function abrirGaleriaFotos(fotosJson) {
  let fotos;
  try { fotos = typeof fotosJson === 'string' ? JSON.parse(fotosJson) : fotosJson; } catch (e) { fotos = []; }
  if (!fotos || !fotos.length) return;

  let idx = 0;
  const overlay = document.createElement('div');
  overlay.id = 'galeriaOverlay';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.92);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:24px;';

  const close = () => overlay.remove();
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });

  const render = () => {
    overlay.innerHTML = `
      <div style="color:#fff;font-size:13px;font-weight:600;opacity:.6;">Foto ${idx + 1} de ${fotos.length}</div>
      <div style="position:relative;width:100%;max-width:480px;">
        <img src="${fotos[idx]}" style="width:100%;max-height:70vh;object-fit:contain;border-radius:16px;display:block;" alt="Evidencia fotográfica">
      </div>
      <div style="display:flex;gap:12px;align-items:center;">
        ${fotos.length > 1 ? `<button onclick="_galPrev()" style="background:rgba(255,255,255,0.15);border:none;border-radius:12px;color:#fff;padding:10px 18px;font-size:20px;cursor:pointer;">&#8592;</button>` : ''}
        <button onclick="document.getElementById('galeriaOverlay').remove()" style="background:rgba(255,255,255,0.15);border:none;border-radius:12px;color:#fff;padding:10px 22px;font-size:14px;font-weight:700;cursor:pointer;">Cerrar</button>
        ${fotos.length > 1 ? `<button onclick="_galNext()" style="background:rgba(255,255,255,0.15);border:none;border-radius:12px;color:#fff;padding:10px 18px;font-size:20px;cursor:pointer;">&#8594;</button>` : ''}
      </div>
    `;
  };

  window._galPrev = () => { idx = (idx - 1 + fotos.length) % fotos.length; render(); };
  window._galNext = () => { idx = (idx + 1) % fotos.length; render(); };

  document.body.appendChild(overlay);
  render();
}

// ── Modal de Verificación de Calidad (Checklist) ─────────────────────────────
function abrirModalChecklist(lavadoId) {
  const l = (window.state.historial || []).find(item => String(item.id) === String(lavadoId));
  if (!l) {
    window.showToast('No se encontró el registro de lavado', 'err');
    return;
  }

  const chk = l.checklist || {};
  const tipo = l.tipo_lavado || 'General';
  const itemsEsperados = ML_CHECKLIST_ITEMS[tipo] || [
    { key: 'exterior_limpio', label: 'Exterior limpio' },
    { key: 'llantas_limpias', label: 'Llantas y ruedas limpias' },
    { key: 'cero_residuos', label: 'Cero residuos en la carrocería' },
  ];

  const marcadosCount = itemsEsperados.filter(it => chk[it.key] === true).length;
  const totalEsperados = itemsEsperados.length;
  const esCompleto = marcadosCount === totalEsperados && totalEsperados > 0;

  // Formatear lavadores
  let lavsStr = '—';
  if (Array.isArray(l.lavadores) && l.lavadores.length > 0) {
    lavsStr = l.lavadores.map(_formatearNombre).join(', ');
  } else if (l.lavador) {
    lavsStr = _formatearNombre(l.lavador);
  }

  // Fotos si tiene
  const fotos = l.fotos || [];
  const tieneFotos = fotos.length > 0;

  const overlay = document.createElement('div');
  overlay.id = 'modalChecklistView';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,0.75);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:16px;';

  const close = () => overlay.remove();
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });

  overlay.innerHTML = `
    <div class="chk-modal-card">
      <!-- Encabezado -->
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:18px;">
        <div style="display:flex;align-items:center;gap:12px;">
          <div style="width:44px;height:44px;border-radius:14px;background:${esCompleto ? '#ECFDF5' : '#F0F9FF'};border:1.5px solid ${esCompleto ? '#A7F3D0' : '#BAE6FD'};display:flex;align-items:center;justify-content:center;font-size:22px;color:${esCompleto ? '#059669' : '#0284C7'};flex-shrink:0;">
            ${esCompleto ? '✓' : '📋'}
          </div>
          <div>
            <div style="font-size:17px;font-weight:800;color:var(--text);letter-spacing:-0.01em;">Verificación de Calidad</div>
            <div style="font-size:12.5px;color:var(--muted);margin-top:2px;display:flex;align-items:center;gap:6px;">
              <span>Vehículo</span>
              <span class="placa" style="font-size:11px;padding:2px 7px;">${l.placa}</span>
              <span>· ${tipo}</span>
            </div>
          </div>
        </div>
        <button type="button" onclick="document.getElementById('modalChecklistView').remove()" style="background:var(--s2);border:1px solid var(--border);border-radius:10px;width:34px;height:34px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:var(--muted);font-size:16px;transition:all .15s;" title="Cerrar">✕</button>
      </div>

      <!-- Resumen del Servicio -->
      <div style="background:var(--s2);border:1px solid var(--border);border-radius:14px;padding:12px 14px;margin-bottom:16px;display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:12px;">
        <div>
          <span style="color:var(--muted);font-size:11px;display:block;margin-bottom:2px;">Fecha del lavado</span>
          <strong style="color:var(--text);">${l.fecha || '—'}</strong>
        </div>
        <div>
          <span style="color:var(--muted);font-size:11px;display:block;margin-bottom:2px;">Duración / Espera</span>
          <strong style="color:var(--text);">${_fmtMins(l.tiempo_lavado)}</strong>
          <span style="color:var(--muted);font-size:11px;">(esp. ${_fmtMins(l.tiempo_espera)})</span>
        </div>
        <div style="grid-column:1 / -1;">
          <span style="color:var(--muted);font-size:11px;display:block;margin-bottom:2px;">Lavador(es) responsable(s)</span>
          <span style="color:var(--text);font-weight:600;">👤 ${lavsStr}</span>
        </div>
      </div>

      <!-- Barra de Estado de Cumplimiento -->
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;padding:0 2px;">
        <span style="font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);">Criterios de Inspección</span>
        <span style="font-size:11.5px;font-weight:800;color:${marcadosCount > 0 ? '#059669' : 'var(--muted)'};background:${marcadosCount > 0 ? '#ECFDF5' : 'var(--s2)'};border:1px solid ${marcadosCount > 0 ? '#A7F3D0' : 'var(--border)'};border-radius:20px;padding:2px 9px;">
          ${marcadosCount} de ${totalEsperados} cumplidos
        </span>
      </div>

      <!-- Lista de Ítems del Checklist -->
      <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:18px;">
        ${itemsEsperados.map(item => {
    const cumplido = chk[item.key] === true;
    return `
            <div class="chk-item-card ${cumplido ? 'chk-item-ok' : 'chk-item-no'}">
              <div style="display:flex;align-items:center;gap:10px;">
                <div style="width:24px;height:24px;border-radius:7px;background:${cumplido ? '#10B981' : 'transparent'};border:1.5px solid ${cumplido ? '#10B981' : 'var(--border)'};display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:800;flex-shrink:0;">
                  ${cumplido ? '✓' : ''}
                </div>
                <span style="font-size:13px;font-weight:${cumplido ? '700' : '500'};color:${cumplido ? '#0F172A' : 'var(--muted)'};">
                  ${item.label}
                </span>
              </div>
              <span style="font-size:10.5px;font-weight:700;padding:3px 8px;border-radius:6px;background:${cumplido ? 'rgba(16,185,129,0.15)' : 'rgba(100,116,139,0.1)'};color:${cumplido ? '#059669' : 'var(--muted)'};white-space:nowrap;">
                ${cumplido ? 'CUMPLIDO' : 'NO MARCADO'}
              </span>
            </div>
          `;
  }).join('')}
      </div>

      ${tieneFotos ? `
        <!-- Acceso directo a fotos desde el checklist -->
        <div style="background:#F0F9FF;border:1px dashed #BAE6FD;border-radius:12px;padding:10px 14px;margin-bottom:18px;display:flex;align-items:center;justify-content:space-between;">
          <div style="display:flex;align-items:center;gap:8px;font-size:12.5px;color:#0369A1;font-weight:600;">
            <span>📷</span>
            <span>Evidencia fotográfica disponible (${fotos.length})</span>
          </div>
          <button type="button" class="btn btn-sm" onclick="document.getElementById('modalChecklistView').remove();abrirGaleriaFotos(${JSON.stringify(fotos).replace(/"/g, '&quot;')})" style="background:#0284C7;color:#fff;font-size:11.5px;padding:6px 12px;border-radius:8px;border:none;cursor:pointer;font-weight:700;">
            Ver fotos
          </button>
        </div>
      ` : ''}

      <!-- Botón de Cerrar -->
      <div style="display:flex;justify-content:flex-end;gap:8px;">
        <button type="button" class="btn btn-ghost" onclick="document.getElementById('modalChecklistView').remove()" style="width:100%;justify-content:center;padding:11px;font-size:13.5px;font-weight:700;border-radius:12px;">
          Entendido
        </button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);
}

// ── Modal para Ver Equipo Completo de Lavadores ──────────────────────────────
function abrirModalEquipo(placa, lavadores) {
  if (!Array.isArray(lavadores) || lavadores.length === 0) return;

  const overlay = document.createElement('div');
  overlay.id = 'modalEquipoView';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,0.75);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:16px;';

  const close = () => overlay.remove();
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });

  overlay.innerHTML = `
    <div class="chk-modal-card" style="max-width:420px;">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="width:40px;height:40px;border-radius:12px;background:rgba(14,165,233,0.1);border:1.5px solid rgba(14,165,233,0.25);display:flex;align-items:center;justify-content:center;font-size:20px;color:var(--accent);">
            👥
          </div>
          <div>
            <div style="font-size:16px;font-weight:800;color:var(--text);">Equipo de Lavadores</div>
            <div style="font-size:12px;color:var(--muted);">Vehículo <span class="placa" style="font-size:11px;padding:2px 7px;">${placa}</span></div>
          </div>
        </div>
        <button type="button" onclick="document.getElementById('modalEquipoView').remove()" style="background:var(--s2);border:1px solid var(--border);border-radius:10px;width:32px;height:32px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:var(--muted);font-size:15px;">✕</button>
      </div>

      <div style="font-size:11.5px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px;">
        ${lavadores.length} lavadores participaron:
      </div>

      <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:20px;">
        ${lavadores.map((name, i) => `
          <div style="display:flex;align-items:center;gap:10px;background:var(--s2);border:1px solid var(--border);border-radius:10px;padding:10px 14px;">
            <div style="width:26px;height:26px;border-radius:50%;background:rgba(14,165,233,0.15);color:var(--accent);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;">
              ${i + 1}
            </div>
            <span style="font-size:13px;font-weight:700;color:var(--text);">${_formatearNombre(name)}</span>
          </div>
        `).join('')}
      </div>

      <button type="button" class="btn btn-ghost" onclick="document.getElementById('modalEquipoView').remove()" style="width:100%;justify-content:center;padding:10px;font-size:13px;border-radius:10px;">
        Cerrar
      </button>
    </div>
  `;

  document.body.appendChild(overlay);
}

window._populateLavPersonal = _populateLavPersonal;
window._populatePlacasSelect = _populatePlacasSelect;
window._lavLimpiarFiltros = _lavLimpiarFiltros;
window._lavSetDateRange = _lavSetDateRange;
window.renderTodosLavados = renderTodosLavados;
window._fmtMins = _fmtMins;
window.loadModalLavadores = loadModalLavadores;
window.addModalLavRow = addModalLavRow;
window.saveLavado = saveLavado;
window.quitarLavado = quitarLavado;
window._setupModalCalc = _setupModalCalc;
window.openLavadoModal = openLavadoModal;
window.mlActualizarChecklist = mlActualizarChecklist;
window.mlToggleChk = mlToggleChk;
window.mlAgregarFotosPreview = mlAgregarFotosPreview;
window.mlEliminarFoto = mlEliminarFoto;
window.mlAbrirCamara = mlAbrirCamara;
window.mlCerrarCamara = mlCerrarCamara;
window.mlFlipCamara = mlFlipCamara;
window.mlCapturarFoto = mlCapturarFoto;
window.abrirGaleriaFotos = abrirGaleriaFotos;
window.abrirModalChecklist = abrirModalChecklist;
window.abrirModalEquipo = abrirModalEquipo;
