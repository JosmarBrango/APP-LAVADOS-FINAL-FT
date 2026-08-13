// ─── Vista Gestión de Vehículos ───────────────────────────────────────────────
function renderVehiculos() {
  window.state.filterMunVeh = document.getElementById('vehMun')?.value || '';
  window.state.searchVeh = document.getElementById('vehSearch')?.value.toLowerCase() || '';

  let data = [...window.state.vehiculos];
  if (window.state.filterMunVeh) data = data.filter(v => v.mun === window.state.filterMunVeh);
  if (window.state.searchVeh) data = data.filter(v => v.placa.toLowerCase().includes(window.state.searchVeh));

  const countEl = document.getElementById('vehCount');
  if (countEl) countEl.textContent = `${data.length} vehículos`;

  const bodyEl = document.getElementById('vehBody');
  if (!bodyEl) return;

  const isAdmin = window.USER_ROLE === 'admin';

  bodyEl.innerHTML = data.map(v => `
    <tr>
      <td><span class="placa">${v.placa}</span></td>
      <td>${v.mun}</td>
      <td><span class="badge" style="background:var(--s2);color:var(--text);border:1px solid var(--border)">${v.tipo}</span></td>
      <td style="font-family:var(--mono);font-size:13px">${v.ruta || '—'}</td>
      <td style="color:var(--muted);font-size:13px">${v.sup || '—'}</td>
      <td style="text-align:right">
        <button class="btn btn-primary" onclick="showQRModal('${v.placa}')" style="padding:6px 12px;font-size:12px;margin-right:6px;display:inline-flex;align-items:center;gap:4px;" title="Ver QR">
          <span class="material-symbols-outlined" style="font-size:16px;">qr_code_2</span> QR
        </button>
        ${isAdmin ? `
          <button class="btn" onclick="editVehicle('${v.placa}')" style="background:#DBEAFE;color:#1D4ED8;border:1px solid #BFDBFE;padding:6px 12px;font-size:12px;margin-right:6px;display:inline-flex;align-items:center;gap:4px;" title="Editar">
            <span class="material-symbols-outlined" style="font-size:16px;">edit</span> Editar
          </button>
          <button class="btn" onclick="deleteVehicle('${v.placa}')" style="background:#FEE2E2;color:#B91C1C;border:1px solid #FECACA;padding:6px 12px;font-size:12px;display:inline-flex;align-items:center;gap:4px;" title="Borrar">
            <span class="material-symbols-outlined" style="font-size:16px;">delete</span> Borrar
          </button>
        ` : ''}
      </td>
    </tr>
  `).join('');
}

function editVehicle(placa) {
  const v = window.state.vehiculos.find(x => x.placa === placa);
  if (!v) return;
  window.state.editTarget = placa;
  document.getElementById('mvTitle').textContent = 'Editar vehículo';
  document.getElementById('mvSub').textContent = 'Modifica los datos del vehículo.';
  document.getElementById('mvPlaca').value = v.placa;
  document.getElementById('mvPlaca').disabled = true;
  document.getElementById('mvMun').value = v.mun;
  document.getElementById('mvTipo').value = v.tipo;
  document.getElementById('mvRuta').value = v.ruta || '';
  document.getElementById('mvSup').value = v.sup || '';
  window.openModal('modalVehicle');
}

async function saveVehicle(e) {
  e.preventDefault();
  const v = {
    placa: document.getElementById('mvPlaca').value.toUpperCase(),
    mun: document.getElementById('mvMun').value,
    tipo: document.getElementById('mvTipo').value,
    ruta: document.getElementById('mvRuta').value,
    sup: document.getElementById('mvSup').value
  };
  try {
    const res = await window.apiCall('/api/vehiculo', window.state.editTarget ? 'PUT' : 'POST', v);
    window.showToast(`Vehículo ${window.state.editTarget ? 'actualizado' : 'agregado'}`);
    window.closeModal('modalVehicle');
    await refreshAllData();
  } catch (err) {
  }
}

async function deleteVehicle(placa) {
  document.getElementById('mcMsg').textContent = `¿Eliminar el vehículo ${placa}? Esta acción no se puede deshacer.`;
  document.getElementById('mcBtn').onclick = async () => {
    try {
      await window.apiCall('/api/vehiculo', 'DELETE', { placa });
      window.showToast("Vehículo eliminado");
      window.closeModal('modalConfirm');
      await refreshAllData();
    } catch (e) {}
  };
  window.openModal('modalConfirm');
}

function openVehicleModal() {
  window.state.editTarget = null;
  document.getElementById('mvTitle').textContent = 'Agregar vehículo';
  document.getElementById('mvSub').textContent = 'Ingresa los datos del nuevo vehículo.';
  document.getElementById('formVehicle').reset();
  document.getElementById('mvPlaca').readOnly = false;
  document.getElementById('mvPlaca').disabled = false;
  window.openModal('modalVehicle');
}

// ─── Generación de Códigos QR ──────────────────────────────────────────────────
let currentQR = null;

function showQRModal(placa) {
  document.getElementById('qrTitleText').textContent = `QR - ${placa}`;
  const url = `${window.location.origin}/registro/${placa}`;
  const urlTextEl = document.getElementById('qrUrlText');
  if (urlTextEl) urlTextEl.textContent = url;
  
  const qrWrap = document.getElementById('qrCanvas');
  qrWrap.innerHTML = '';
  
  currentQR = new QRCode(qrWrap, {
    text: url,
    width: 200,
    height: 200,
    colorDark : "#0F172A",
    colorLight : "#ffffff",
    correctLevel : QRCode.CorrectLevel.H
  });
  
  window.openModal('modalQR');
}

function printCurrentQR() {
  const qrCanvas = document.getElementById('qrCanvas').querySelector('canvas');
  if (!qrCanvas) return;
  const imgData = qrCanvas.toDataURL("image/png");
  const placa = document.getElementById('qrTitleText').textContent.replace('QR - ', '');
  
  const printWindow = window.open('', '_blank');
  printWindow.document.write(`
    <html>
      <head>
        <title>QR ${placa}</title>
        <style>
          body { display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; margin:0; font-family:sans-serif; }
          img { width: 300px; height: 300px; }
          h1 { margin-top: 20px; font-size: 42px; font-family: monospace; }
        </style>
      </head>
      <body>
        <img src="${imgData}" />
        <h1>${placa}</h1>
        <script>
          window.onload = function() { window.print(); window.setTimeout(function(){ window.close(); }, 500); }
        </script>
      </body>
    </html>
  `);
  printWindow.document.close();
}

function downloadCurrentQR() {
  const qrCanvas = document.getElementById('qrCanvas').querySelector('canvas');
  if (!qrCanvas) return;
  const placa = document.getElementById('qrTitleText').textContent.replace('QR - ', '');
  const link = document.createElement('a');
  link.download = `QR_${placa}.png`;
  link.href = qrCanvas.toDataURL("image/png");
  link.click();
}

window.renderVehiculos = renderVehiculos;
window.editVehicle = editVehicle;
window.saveVehicle = saveVehicle;
window.deleteVehicle = deleteVehicle;
window.openVehicleModal = openVehicleModal;
window.showQRModal = showQRModal;
window.printCurrentQR = printCurrentQR;
window.downloadCurrentQR = downloadCurrentQR;
