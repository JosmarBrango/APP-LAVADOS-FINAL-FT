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
  return `${Math.floor(m / 60)}h ${m % 60}min`;
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
  if (tipo) data = data.filter(l => l.tipo_lavado === tipo);
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
    else if (l.tipo_lavado === 'Sencillo') sen++;
    else if (l.tipo_lavado === 'Enjuague') enj++;
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
        if (tl === 'Sencillo') { badgeBg = '#D1FAE5'; badgeColor = '#059669'; bBorder = '#A7F3D0'; }
        if (tl === 'Enjuague') { badgeBg = '#FEF3C7'; badgeColor = '#D97706'; bBorder = '#FDE68A'; }

        const lavadoMun = vMap[l.placa] || l.municipio_lavado || 'N/D';
        const isAdmin = window.USER_ROLE === 'admin';
        
        let lavadoresInfo = '';
        if (l.lavadores && l.lavadores.length > 0) {
          lavadoresInfo = `<span style="font-size:11px;font-weight:600">${l.lavadores.join('<br>')}</span>`;
        } else {
          lavadoresInfo = `<span style="font-size:11px;color:var(--muted)">${l.lavador || '—'}</span>`;
        }

        return `
        <tr>
          <td><span class="placa">${l.placa}</span></td>
          <td style="font-size:12px;color:var(--muted)">${lavadoMun}</td>
          <td><span class="badge" style="background:${badgeBg};color:${badgeColor};border:1px solid ${bBorder}">${tl}</span></td>
          <td>${lavadoresInfo}</td>
          <td style="font-family:var(--mono);font-size:12px">${l.fecha || '—'}</td>
          <td style="font-family:var(--mono);font-size:12px">${l.hora_llegada || '—'}</td>
          <td style="font-family:var(--mono);font-size:12px">${l.hora_inicio || '—'} → ${l.hora_fin || '—'}</td>
          <td style="font-family:var(--mono);font-size:12px;color:var(--muted)">${_fmtMins(l.tiempo_espera)}</td>
          <td style="font-family:var(--mono);font-size:12px;font-weight:600">${_fmtMins(l.tiempo_lavado)}</td>
          <td style="font-size:11px;color:var(--muted)">${l.origen === 'qr' ? '📱 QR' : '💻 Panel'}</td>
          ${isAdmin ? `
          <td style="text-align:right">
            <button class="act-btn del" onclick="quitarLavado('${l.id}')">Eliminar</button>
          </td>` : ''}
        </tr>`;
      }).join('');
    }
  }
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

function openLavadoModal() {
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
    if (tipoEl) tipoEl.value = '';
    const munEl = document.getElementById('mlMunicipio');
    if (munEl) munEl.value = '';
    const hlEl = document.getElementById('mlHoraLlegada');
    if (hlEl) hlEl.value = '';
    const hiEl = document.getElementById('mlHoraInicio');
    if (hiEl) hiEl.value = '';
    const hfEl = document.getElementById('mlHoraFin');
    if (hfEl) hfEl.value = '';
  }

  const badges = document.getElementById('mlCalcBadges');
  if (badges) badges.style.display = 'none';
  
  const fechaVis = document.getElementById('mlFechaVisible');
  const fechaHid = document.getElementById('mlFecha');
  if (fechaVis && fechaHid) {
    const todayStr = new Date().toISOString().split('T')[0];
    fechaVis.value   = todayStr;
    fechaHid.value   = todayStr;
    fechaVis.style.background = 'var(--s3)';
    fechaVis.style.cursor     = 'default';
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

  try {
    const payload = {
      placa,
      tipo_lavado,
      municipio,
      fecha,
      hora_llegada,
      hora_inicio,
      hora_fin,
      lavadores
    };

    const res = await window.apiCall('/api/lavado/add_manual', 'POST', payload);
    if (res && res.error) {
      return window.showToast(res.error, 'err');
    }

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
