// ─── Vista Historial (y QR scanner) ───────────────────────────────────────────
let html5QrcodeScanner = null;

function renderHistorial() {
  const hDesde = document.getElementById('histDesde')?.value || '';
  const hHasta = document.getElementById('histHasta')?.value || '';
  const hSearch = document.getElementById('histSearch')?.value.toLowerCase() || '';

  let data = [...window.state.historial];
  if (hDesde) data = data.filter(h => h.fecha >= hDesde);
  if (hHasta) data = data.filter(h => h.fecha <= hHasta);
  if (hSearch) data = data.filter(h => h.placa.toLowerCase().includes(hSearch));

  data.sort((a, b) => {
    if (a.fecha !== b.fecha) return (b.fecha || '').localeCompare(a.fecha || '');
    return (b.hora_inicio || '').localeCompare(a.hora_inicio || '');
  });

  const countEl = document.getElementById('histCount');
  if (countEl) countEl.textContent = `${data.length} registros`;

  const bodyEl = document.getElementById('histBody');
  if (bodyEl) {
    bodyEl.innerHTML = data.map(l => {
      let badgeBg = 'var(--bg)', badgeColor = 'var(--text)', bBorder = 'var(--border)';
      const tl = l.tipo_lavado || 'General';
      if (tl === 'General') { badgeBg = '#E0F2FE'; badgeColor = '#0284C7'; bBorder = '#BAE6FD'; }
      if (tl === 'Sencillo') { badgeBg = '#D1FAE5'; badgeColor = '#059669'; bBorder = '#A7F3D0'; }
      if (tl === 'Enjuague') { badgeBg = '#FEF3C7'; badgeColor = '#D97706'; bBorder = '#FDE68A'; }

      let lavadoresInfo = '';
      if (l.lavadores && l.lavadores.length > 0) {
        lavadoresInfo = `<span style="font-size:11px;font-weight:600">${l.lavadores.join('<br>')}</span>`;
      } else {
        lavadoresInfo = `<span style="font-size:11px;color:var(--muted)">${l.lavador || '—'}</span>`;
      }

      return `
      <tr>
        <td><span class="placa">${l.placa}</span></td>
        <td><span class="badge" style="background:${badgeBg};color:${badgeColor};border:1px solid ${bBorder}">${tl}</span></td>
        <td>${lavadoresInfo}</td>
        <td style="font-family:var(--mono);font-size:12px">${l.fecha || '—'}</td>
        <td style="font-family:var(--mono);font-size:12px">${l.hora_llegada || '—'}</td>
        <td style="font-family:var(--mono);font-size:12px">${l.hora_inicio || '—'} → ${l.hora_fin || '—'}</td>
        <td style="font-family:var(--mono);font-size:12px;color:var(--muted)">${window._fmtMins(l.tiempo_espera)}</td>
        <td style="font-family:var(--mono);font-size:12px;font-weight:600">${window._fmtMins(l.tiempo_lavado)}</td>
        <td style="font-size:11px;color:var(--muted)">${l.origen === 'qr' ? '📱 QR' : '💻 Panel'}</td>
      </tr>`;
    }).join('');
  }
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
      placa = urlParts[urlParts.length - 1].toUpperCase();
    } catch {
      placa = decodedText.toUpperCase();
    }
    
    // Abrir modal de lavado con la placa pre-llenada
    if (placa && placa.length >= 5) {
      window.openModal('modalLavado');
      setTimeout(() => {
        const mlPlaca = document.getElementById('mlPlaca');
        if (mlPlaca) {
          mlPlaca.value = placa;
          // Disparar evento input para autocompletar municipio
          mlPlaca.dispatchEvent(new Event('input'));
        }
      }, 200);
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
