// ─── Vista Historial (y QR scanner) ───────────────────────────────────────────
let html5QrcodeScanner = null;

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

  if (data.length === 0) {
    bodyEl.innerHTML = `
      <tr class="hist-empty-row">
        <td colspan="9" style="text-align:center;padding:36px 16px;color:var(--muted)">
          <div style="font-size:36px;margin-bottom:10px;">🔍</div>
          <div style="font-size:15px;font-weight:700;color:var(--text);">No hay registros de lavados</div>
          <div style="font-size:13px;margin-top:4px;">No se encontraron lavados con los filtros seleccionados.</div>
        </td>
      </tr>
    `;
    return;
  }

  bodyEl.innerHTML = data.map(l => {
    let badgeBg = 'var(--bg)', badgeColor = 'var(--text)', bBorder = 'var(--border)';
    const tl = l.tipo_lavado || 'General';
    if (tl === 'General') { badgeBg = '#E0F2FE'; badgeColor = '#0284C7'; bBorder = '#BAE6FD'; }
    if (tl === 'Sencillo') { badgeBg = '#D1FAE5'; badgeColor = '#059669'; bBorder = '#A7F3D0'; }
    if (tl === 'Enjuague') { badgeBg = '#FEF3C7'; badgeColor = '#D97706'; bBorder = '#FDE68A'; }

    let lavadoresText = '';
    if (l.lavadores && l.lavadores.length > 0) {
      lavadoresText = l.lavadores.join(', ');
    } else {
      lavadoresText = l.lavador || '---------------';
    }

    const fechaFmt = l.fecha ? l.fecha : '---------------';
    const llegadaFmt = l.hora_llegada ? l.hora_llegada : '---------------';
    const horasFmt = (l.hora_inicio || l.hora_fin) ? `${l.hora_inicio || '--:--'} → ${l.hora_fin || '--:--'}` : '---------------';
    const esperaFmt = window._fmtMins(l.tiempo_espera);
    const duracionFmt = window._fmtMins(l.tiempo_lavado);
    const origenIcon = (l.origen === 'qr' || l.origen === 'qr_registro') ? '📱 QR' : '💻 Panel';

    return `
    <tr class="hist-row">
      <td class="td-hist-placa" data-label="Placa">
        <span class="placa">${l.placa}</span>
      </td>
      <td class="td-hist-tipo" data-label="Tipo">
        <span class="hist-label-mob">Tipo</span>
        <span class="badge hist-tipo-badge" style="background:${badgeBg};color:${badgeColor};border:1px solid ${bBorder}">${tl}</span>
      </td>
      <td class="td-hist-lavadores" data-label="Lavadores">
        <span class="hist-label-mob">Lavadores</span>
        <span class="hist-val-lavadores">${lavadoresText}</span>
      </td>
      <td class="td-hist-fecha" data-label="Fecha">
        <span class="hist-label-mob">Fecha</span>
        <span class="hist-val-mob font-mono">${fechaFmt}</span>
      </td>
      <td class="td-hist-llegada" data-label="Llegada">
        <span class="hist-label-mob">Llegada</span>
        <span class="hist-val-mob font-mono">${llegadaFmt}</span>
      </td>
      <td class="td-hist-horas" data-label="Horario">
        <span class="hist-label-mob">Horario</span>
        <span class="hist-val-mob font-mono">${horasFmt}</span>
      </td>
      <td class="td-hist-espera" data-label="Espera">
        <span class="hist-label-mob">Espera</span>
        <span class="hist-val-mob font-mono text-muted">${esperaFmt}</span>
      </td>
      <td class="td-hist-duracion" data-label="Duración">
        <span class="hist-label-mob">Duración</span>
        <span class="hist-val-mob font-mono font-bold">${duracionFmt}</span>
      </td>
      <td class="td-hist-origen" data-label="Origen">
        <span class="hist-label-mob">Origen</span>
        <span class="hist-origen-tag">${origenIcon}</span>
      </td>
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
    
    // Abrir modal de lavado inicializando correctamente lavadores y fecha
    if (placa && placa.length >= 5) {
      if (typeof window.openLavadoModal === 'function') {
        window.openLavadoModal();
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
