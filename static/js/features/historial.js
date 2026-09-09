// ─── Vista Historial (y QR scanner) ───────────────────────────────────────────
let html5QrcodeScanner = null;

// Helpers de formateo si no están disponibles en window
function _formatearNombre(nombre) {
  if (!nombre) return '';
  return String(nombre).toLowerCase().split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

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

function _renderLavadoresCelda(l) {
  let lavs = [];
  if (Array.isArray(l.lavadores) && l.lavadores.length > 0) {
    lavs = l.lavadores.map(x => String(x).trim()).filter(Boolean);
  } else if (l.lavador) {
    lavs = [String(l.lavador).trim()];
  }
  if (lavs.length === 0) return `<span style="font-size:11px;color:var(--muted)">—</span>`;
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

function renderHistorial() {
  const hDesde = document.getElementById('histDesde')?.value || '';
  const hHasta = document.getElementById('histHasta')?.value || '';
  const hSearch = document.getElementById('histSearch')?.value.toLowerCase() || '';

  let data = [...window.state.historial];
  if (hDesde) data = data.filter(h => h.fecha >= hDesde);
  if (hHasta) data = data.filter(h => h.fecha <= hHasta);
  if (hSearch) data = data.filter(h => (h.placa || '').toLowerCase().includes(hSearch));

  data.sort((a, b) => {
    if (a.fecha !== b.fecha) return (b.fecha || '').localeCompare(a.fecha || '');
    return (b.hora_inicio || '').localeCompare(a.hora_inicio || '');
  });

  const countEl = document.getElementById('histCount');
  if (countEl) countEl.textContent = `${data.length} registro${data.length === 1 ? '' : 's'}`;

  const bodyEl = document.getElementById('histBody');
  if (!bodyEl) return;

  const isAdmin = window.USER_ROLE === 'admin';
  const totalCols = isAdmin ? 9 : 8;

  if (data.length === 0) {
    bodyEl.innerHTML = `
      <tr class="hist-empty-row">
        <td colspan="${totalCols}" style="text-align:center;padding:36px 16px;color:var(--muted)">
          <div style="font-size:36px;margin-bottom:10px;">🔍</div>
          <div style="font-size:15px;font-weight:700;color:var(--text);">No hay registros de lavados</div>
          <div style="font-size:13px;margin-top:4px;">No se encontraron lavados con los filtros seleccionados.</div>
        </td>
      </tr>
    `;
    return;
  }

  // Diccionario vehiculos placa -> mun
  const vMap = {};
  (window.state.vehiculos || []).forEach(v => { vMap[v.placa] = v.mun || 'N/D'; });

  bodyEl.innerHTML = data.map(l => {
    let badgeBg = 'var(--bg)', badgeColor = 'var(--text)', bBorder = 'var(--border)';
    const tl = l.tipo_lavado || 'General';
    if (tl === 'General') { badgeBg = '#E0F2FE'; badgeColor = '#0284C7'; bBorder = '#BAE6FD'; }
    if (tl === 'Alistamiento' || tl === 'Sencillo') { badgeBg = '#D1FAE5'; badgeColor = '#059669'; bBorder = '#A7F3D0'; }
    if (tl === 'Motor' || tl === 'Enjuague') { badgeBg = '#FEF3C7'; badgeColor = '#D97706'; bBorder = '#FDE68A'; }

    const lavadoMun = vMap[l.placa] || l.municipio_lavado || 'N/D';

    // 1. Lavadores estilizados en pastillas (pills)
    const lavadoresHtml = _renderLavadoresCelda(l);

    // 2. Fecha formateada (ej. "03 Sep 2026")
    const fechaHtml = _formatearFechaTabla(l.fecha);

    // 3. Botón de Información Completa del Lavado (INFO)
    const infoCelda = `
      <button class="btn-calidad btn-calidad-info" onclick="abrirModalInfoLavado('${l.id}')" title="Ver detalles del lavado: tiempos, lavadores, etc.">
        <span class="material-symbols-outlined" style="font-size:14px;vertical-align:middle;">info</span>
        <span>Info</span>
      </button>
    `;

    return `
    <tr>
      <td><span class="placa">${l.placa}</span></td>
      <td style="font-size:12.5px;color:var(--text-2);font-weight:600;white-space:nowrap;">${lavadoMun}</td>
      <td><span class="badge" style="background:${badgeBg};color:${badgeColor};border:1px solid ${bBorder};white-space:nowrap;">${tl}</span></td>
      <td>${fechaHtml}</td>
      <td style="font-family:var(--mono);font-size:12.5px;text-align:center;white-space:nowrap;">${l.hora_llegada || '—'}</td>
      <td>${lavadoresHtml}</td>
      <td style="text-align:center;">${infoCelda}</td>
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

function startQRScanner() {
  const container = document.getElementById('qr-reader-container');
  if (container) container.style.display = 'block';

  if (!html5QrcodeScanner) {
    html5QrcodeScanner = new Html5QrcodeScanner(
      "qr-reader", { fps: 10, qrbox: { width: 250, height: 250 } }, false);
  }

  html5QrcodeScanner.render((decodedText, decodedResult) => {
    stopQRScanner();
    // Extraer la placa de la URL del QR (ej: http://dominio/registro/ABC123)
    let placa = '';
    try {
      const urlParts = decodedText.split('/');
      placa = urlParts[urlParts.length - 1].toUpperCase().trim();
    } catch {
      placa = decodedText.toUpperCase().trim();
    }

    // Abrir modal de lavado inicializando correctamente lavadores y fecha con origen 'qr'
    if (placa && placa.length >= 5) {
      window._modalLavadoOrigen = 'qr';
      if (typeof window.openLavadoModal === 'function') {
        window.openLavadoModal('qr');
      } else {
        window.openModal('modalLavado');
      }
      setTimeout(() => {
        const mlPlaca = document.getElementById('mlPlaca');
        if (mlPlaca) {
          mlPlaca.value = placa;
          // Disparar evento input para autocompletar municipio si existe
          mlPlaca.dispatchEvent(new Event('input'));
        }
      }, 150);
      window.showToast(`Código escaneado: ${placa}`);
    } else {
      window.showToast("QR no reconocido o placa inválida", 'err');
    }
  }, (error) => {
    // Ignorar errores de escaneo continuo
  });
}

function stopQRScanner() {
  const container = document.getElementById('qr-reader-container');
  if (container) container.style.display = 'none';
  if (html5QrcodeScanner) {
    html5QrcodeScanner.clear().catch(err => console.error("Error al detener el scanner", err));
  }
}

window.renderHistorial = renderHistorial;
window.startQRScanner = startQRScanner;
window.stopQRScanner = stopQRScanner;

// ── Helpers de cálculo y formato de tiempos ──────────────────────────────────
function _calcDiffMins(h1, h2) {
  if (!h1 || !h2) return null;
  try {
    const [h1h, h1m] = h1.split(':').map(Number);
    const [h2h, h2m] = h2.split(':').map(Number);
    let diff = (h2h * 60 + h2m) - (h1h * 60 + h1m);
    if (diff < 0) diff += 24 * 60;
    return diff;
  } catch (e) {
    return null;
  }
}

function _formatMinutosInfo(m) {
  if (m === null || m === undefined || m === '' || isNaN(m)) return '—';
  const val = parseInt(m, 10);
  if (val < 0) return '—';
  const h = Math.floor(val / 60);
  const min = val % 60;
  if (h > 0) return `${h}h ${min > 0 ? min + 'm' : ''}`.trim();
  return `${min}m`;
}

function _formatearFechaLarga(f) {
  if (!f) return '—';
  const parts = String(f).trim().split('-');
  if (parts.length === 3) {
    const meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
    const dia = parts[2];
    const mesIdx = parseInt(parts[1], 10) - 1;
    const mes = meses[mesIdx] || parts[1];
    const anio = parts[0];
    return `${dia} de ${mes}, ${anio}`;
  }
  return f;
}

// ── Modal de Información Detallada del Lavado (INFO) ─────────────────────────
function abrirModalInfoLavado(lavadoId) {
  const l = (window.state.historial || []).find(item => String(item.id) === String(lavadoId));
  if (!l) {
    window.showToast('No se encontró el registro de lavado', 'err');
    return;
  }

  // Diccionario vehiculos placa -> mun
  const vMap = {};
  (window.state.vehiculos || []).forEach(v => { vMap[v.placa] = v.mun || 'N/D'; });
  const mun = l.municipio || vMap[l.placa] || 'N/D';

  const tl = l.tipo_lavado || 'General';
  let badgeBg = '#E0F2FE', badgeColor = '#0284C7', bBorder = '#BAE6FD';
  if (tl === 'Alistamiento' || tl === 'Sencillo') { badgeBg = '#D1FAE5'; badgeColor = '#059669'; bBorder = '#A7F3D0'; }
  if (tl === 'Motor' || tl === 'Enjuague') { badgeBg = '#FEF3C7'; badgeColor = '#D97706'; bBorder = '#FDE68A'; }

  // Tiempos (con cálculo automático de respaldo si no vinieron precargados)
  let tEspera = l.tiempo_espera;
  if (tEspera === null || tEspera === undefined) {
    tEspera = _calcDiffMins(l.hora_llegada, l.hora_inicio);
  }
  let tLavado = l.tiempo_lavado;
  if (tLavado === null || tLavado === undefined) {
    tLavado = _calcDiffMins(l.hora_inicio, l.hora_fin);
  }

  // Lavadores
  let lavs = [];
  if (Array.isArray(l.lavadores) && l.lavadores.length > 0) {
    lavs = l.lavadores.map(x => String(x).trim()).filter(Boolean);
  } else if (l.lavador) {
    lavs = [String(l.lavador).trim()];
  }

  // Fotos y Checklist
  const fotos = l.fotos || [];
  const chk = l.checklist || {};
  const marcados = Object.keys(chk).filter(k => chk[k] === true).length;
  const totalChk = Object.keys(chk).length;

  const overlay = document.createElement('div');
  overlay.id = 'modalInfoLavadoView';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,0.75);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:16px;';

  const close = () => {
    window.removeEventListener('keydown', onKey);
    overlay.remove();
  };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  window.addEventListener('keydown', onKey);
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });

  overlay.innerHTML = `
    <div class="chk-modal-card" style="max-width:520px;padding:24px;">
      <!-- Encabezado con Placa y Tipo -->
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:20px;">
        <div style="display:flex;align-items:center;gap:12px;">
          <div style="width:46px;height:46px;border-radius:14px;background:#EFF6FF;border:1.5px solid #BFDBFE;display:flex;align-items:center;justify-content:center;font-size:22px;color:#2563EB;flex-shrink:0;">
            <span class="material-symbols-outlined" style="font-size:26px;">info</span>
          </div>
          <div>
            <div style="font-size:18px;font-weight:800;color:var(--text);letter-spacing:-0.01em;">Detalle del Lavado</div>
            <div style="font-size:13px;color:var(--muted);margin-top:2px;display:flex;align-items:center;gap:8px;">
              <span>Vehículo</span>
              <span class="placa" style="font-size:12px;padding:2px 8px;">${l.placa}</span>
              <span class="badge" style="background:${badgeBg};color:${badgeColor};border:1px solid ${bBorder};font-size:11.5px;">${tl}</span>
            </div>
          </div>
        </div>
        <button type="button" onclick="document.getElementById('modalInfoLavadoView').remove()" style="background:var(--s2);border:1px solid var(--border);border-radius:10px;width:34px;height:34px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:var(--muted);font-size:16px;transition:all .15s;" title="Cerrar">✕</button>
      </div>

      <!-- Tarjetas de Métricas de Tiempos (Tiempo en Espera y Duración) -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
        <!-- Espera -->
        <div style="background:var(--s2);border:1px solid var(--border);border-radius:14px;padding:14px;">
          <div style="display:flex;align-items:center;gap:6px;font-size:11.5px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:0.04em;">
            <span>⏳</span> Tiempo en Espera
          </div>
          <div style="font-size:22px;font-weight:800;color:#2563EB;margin:6px 0 2px;">
            ${_formatMinutosInfo(tEspera)}
          </div>
          <div style="font-size:11.5px;color:var(--muted);font-family:var(--mono);">
            ${l.hora_llegada || '—'} → ${l.hora_inicio || '—'}
          </div>
        </div>

        <!-- Duración -->
        <div style="background:var(--s2);border:1px solid var(--border);border-radius:14px;padding:14px;">
          <div style="display:flex;align-items:center;gap:6px;font-size:11.5px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:0.04em;">
            <span>⏱️</span> Duración del Lavado
          </div>
          <div style="font-size:22px;font-weight:800;color:#059669;margin:6px 0 2px;">
            ${_formatMinutosInfo(tLavado)}
          </div>
          <div style="font-size:11.5px;color:var(--muted);font-family:var(--mono);">
            ${l.hora_inicio || '—'} → ${l.hora_fin || '—'}
          </div>
        </div>
      </div>

      <!-- Resumen General (Fecha, Municipio, Canal) -->
      <div style="background:var(--s2);border:1px solid var(--border);border-radius:14px;padding:14px;margin-bottom:16px;display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:12.5px;">
        <div>
          <span style="color:var(--muted);font-size:11px;display:block;margin-bottom:2px;font-weight:600;text-transform:uppercase;letter-spacing:0.03em;">Fecha del Lavado</span>
          <strong style="color:var(--text);font-size:13.5px;">${_formatearFechaLarga(l.fecha)}</strong>
        </div>
        <div>
          <span style="color:var(--muted);font-size:11px;display:block;margin-bottom:2px;font-weight:600;text-transform:uppercase;letter-spacing:0.03em;">Municipio / Sede</span>
          <strong style="color:var(--text);font-size:13.5px;">📍 ${mun}</strong>
        </div>
        <div style="grid-column:1 / -1;display:flex;align-items:center;justify-content:space-between;border-top:1px dashed var(--border);padding-top:10px;margin-top:2px;">
          <span style="color:var(--muted);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.03em;">Canal de Registro</span>
          <span class="lav-origen-pill" style="font-size:12px;font-weight:700;">
            ${(l.origen || '').toLowerCase().includes('qr') ? '📱 Escaneo Móvil QR (Patio)' : '💻 Panel Administrativo Web'}
          </span>
        </div>
      </div>

      <!-- Equipo de Lavadores -->
      <div style="margin-bottom:18px;">
        <div style="font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);margin-bottom:8px;">
          Lavador(es) Asignado(s) (${lavs.length})
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;">
          ${lavs.length > 0 ? lavs.map(name => `
            <div style="display:inline-flex;align-items:center;gap:6px;background:var(--s2);border:1px solid var(--border);border-radius:10px;padding:6px 12px;font-size:12.5px;font-weight:700;color:var(--text);">
              <span>👤</span>
              <span>${_formatearNombre(name)}</span>
            </div>
          `).join('') : `<span style="color:var(--muted);font-size:12.5px;">Sin lavadores asignados</span>`}
        </div>
      </div>

      <!-- Sección de Control de Calidad y Fotos (si aplican) -->
      ${(fotos.length > 0 || totalChk > 0) ? `
        <div style="background:var(--s2);border:1px solid var(--border);border-radius:14px;padding:12px 14px;margin-bottom:18px;display:flex;align-items:center;justify-content:space-between;gap:10px;">
          <div>
            <div style="font-size:12.5px;font-weight:700;color:var(--text);">Verificación y Evidencias</div>
            <div style="font-size:11.5px;color:var(--muted);margin-top:2px;">
              ${totalChk > 0 ? `✅ ${marcados}/${totalChk} ítems cumplidos · ` : ''}
              ${fotos.length > 0 ? `📷 ${fotos.length} foto(s) disponible(s)` : 'Sin fotos'}
            </div>
          </div>
          <div style="display:flex;gap:6px;">
            ${totalChk > 0 ? `
              <button type="button" class="btn btn-sm" onclick="document.getElementById('modalInfoLavadoView').remove();if(typeof abrirModalChecklist==='function')abrirModalChecklist('${l.id}')" style="background:#ECFDF5;color:#059669;border:1px solid #A7F3D0;font-size:11.5px;padding:6px 11px;border-radius:8px;font-weight:700;cursor:pointer;">
                Checklist
              </button>
            ` : ''}
            ${fotos.length > 0 ? `
              <button type="button" class="btn btn-sm" onclick="document.getElementById('modalInfoLavadoView').remove();if(typeof abrirGaleriaFotos==='function')abrirGaleriaFotos(${JSON.stringify(fotos).replace(/"/g, '&quot;')})" style="background:#0284C7;color:#fff;border:none;font-size:11.5px;padding:6px 11px;border-radius:8px;font-weight:700;cursor:pointer;">
                Ver fotos
              </button>
            ` : ''}
          </div>
        </div>
      ` : ''}

      <!-- Botón de Cerrar -->
      <button type="button" class="btn btn-ghost" onclick="document.getElementById('modalInfoLavadoView').remove()" style="width:100%;justify-content:center;padding:11px;font-size:13.5px;font-weight:700;border-radius:12px;">
        Entendido
      </button>
    </div>
  `;

  document.body.appendChild(overlay);
}

window.abrirModalInfoLavado = abrirModalInfoLavado;
