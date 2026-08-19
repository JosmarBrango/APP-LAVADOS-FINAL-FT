// ─── Vista Gestión de Vehículos ───────────────────────────────────────────────
function renderVehiculos() {
  window.state.filterMunVeh = document.getElementById('vehMun')?.value || '';
  window.state.searchVeh = document.getElementById('vehSearch')?.value.toLowerCase() || '';

  let data = [...window.state.vehiculos];
  if (window.state.filterMunVeh) data = data.filter(v => v.mun === window.state.filterMunVeh);
  if (window.state.searchVeh) data = data.filter(v => (v.placa || '').toLowerCase().includes(window.state.searchVeh));

  const countEl = document.getElementById('vehCount');
  if (countEl) countEl.textContent = `${data.length} vehículo${data.length === 1 ? '' : 's'}`;

  const bodyEl = document.getElementById('vehBody');
  if (!bodyEl) return;

  const isAdmin = window.USER_ROLE === 'admin';

  if (data.length === 0) {
    bodyEl.innerHTML = `
      <tr class="veh-empty-row">
        <td colspan="6" style="text-align:center;padding:40px 16px;color:var(--muted)">
          <div style="font-size:36px;margin-bottom:10px;">🔍</div>
          <div style="font-size:15px;font-weight:700;color:var(--text);">No se encontraron vehículos</div>
          <div style="font-size:13px;margin-top:4px;">Prueba cambiando el filtro de municipio o el término de búsqueda.</div>
        </td>
      </tr>
    `;
    return;
  }

  bodyEl.innerHTML = data.map(v => {
    const munFormatted = window.formatVal(v.mun);
    const tipoFormatted = window.isInvalidVal(v.tipo) 
      ? window.formatVal(v.tipo) 
      : `<span class="badge veh-tipo-badge">${v.tipo}</span>`;
    const rutaFormatted = window.isInvalidVal(v.ruta)
      ? window.formatVal(v.ruta)
      : `<span class="veh-ruta-tag">${v.ruta}</span>`;
    const supFormatted = window.isInvalidVal(v.sup)
      ? window.formatVal(v.sup)
      : `<span class="veh-sup-text">${v.sup}</span>`;

    return `
    <tr class="veh-row">
      <td class="td-placa" data-label="Placa"><span class="placa">${v.placa}</span></td>
      <td class="td-mun" data-label="Municipio">
        <span class="veh-label-mob">Municipio</span>
        <span class="veh-val-mob">${munFormatted}</span>
      </td>
      <td class="td-tipo" data-label="Tipo">
        <span class="veh-label-mob">Tipo</span>
        <span class="veh-val-mob">${tipoFormatted}</span>
      </td>
      <td class="td-ruta" data-label="Ruta">
        <span class="veh-label-mob">Ruta</span>
        <span class="veh-val-mob">${rutaFormatted}</span>
      </td>
      <td class="td-sup" data-label="Supervisor">
        <span class="veh-label-mob">Supervisor</span>
        <span class="veh-val-mob">${supFormatted}</span>
      </td>
      <td class="td-actions" data-label="Acciones">
        <button class="btn btn-primary btn-veh-action" onclick="showQRModal('${v.placa}')" title="Ver QR">
          <span class="material-symbols-outlined" style="font-size:17px;">qr_code_2</span> <span>QR</span>
        </button>
        ${isAdmin ? `
          <button class="btn btn-veh-action btn-veh-edit" onclick="editVehicle('${v.placa}')" title="Editar">
            <span class="material-symbols-outlined" style="font-size:17px;">edit</span> <span>Editar</span>
          </button>
          <button class="btn btn-veh-action btn-veh-delete" onclick="deleteVehicle('${v.placa}')" title="Borrar">
            <span class="material-symbols-outlined" style="font-size:17px;">delete</span> <span>Borrar</span>
          </button>
        ` : ''}
      </td>
    </tr>
  `;
  }).join('');
}

function editVehicle(placa) {
  const v = window.state.vehiculos.find(x => (x.placa || '').toUpperCase() === (placa || '').toUpperCase());
  if (!v) return;
  window.state.editTarget = v.placa;
  document.getElementById('mvTitle').textContent = 'Editar vehículo';
  document.getElementById('mvSub').textContent = 'Modifica los datos del vehículo.';
  
  const placaEl = document.getElementById('mvPlaca');
  placaEl.value = v.placa;
  placaEl.disabled = true;
  
  document.getElementById('mvMun').value = window.isInvalidVal(v.mun) ? '' : v.mun;
  
  const tipoEl = document.getElementById('mvTipo');
  const vTipo = window.isInvalidVal(v.tipo) ? '' : (v.tipo || '').trim();
  
  if (vTipo) {
    let found = false;
    for (let i = 0; i < tipoEl.options.length; i++) {
      if (tipoEl.options[i].value.toUpperCase() === vTipo.toUpperCase() || 
          tipoEl.options[i].text.toUpperCase() === vTipo.toUpperCase()) {
        tipoEl.selectedIndex = i;
        found = true;
        break;
      }
    }
    if (!found) {
      const opt = document.createElement('option');
      opt.value = vTipo;
      opt.textContent = vTipo;
      tipoEl.appendChild(opt);
      tipoEl.value = vTipo;
    }
  } else {
    tipoEl.value = '';
  }
  
  document.getElementById('mvRuta').value = window.isInvalidVal(v.ruta) ? '' : v.ruta;
  document.getElementById('mvSup').value = window.isInvalidVal(v.sup) ? '' : v.sup;
  window.openModal('modalVehicle');
}

async function saveVehicle(e) {
  e.preventDefault();
  const placa = (window.state.editTarget || document.getElementById('mvPlaca').value).trim().toUpperCase();
  const mun = document.getElementById('mvMun').value.trim();
  const tipo = document.getElementById('mvTipo').value.trim();
  const ruta = document.getElementById('mvRuta').value.trim();
  const sup = document.getElementById('mvSup').value.trim();

  if (!placa) {
    window.showToast("La placa es obligatoria");
    return;
  }
  if (!tipo) {
    window.showToast("Por favor selecciona un tipo de vehículo");
    return;
  }

  const v = {
    placa,
    mun,
    tipo,
    ruta,
    sup
  };

  try {
    await window.apiCall('/api/vehiculo', window.state.editTarget ? 'PUT' : 'POST', v);
    window.showToast(`Vehículo ${window.state.editTarget ? 'actualizado' : 'agregado'} con éxito`);
    window.closeModal('modalVehicle');
    await window.refreshAllData();
  } catch (err) {
    // apiCall maneja el toast y el log en consola
  }
}

async function deleteVehicle(placa) {
  document.getElementById('mcMsg').textContent = `¿Eliminar el vehículo ${placa}? Esta acción no se puede deshacer.`;
  document.getElementById('mcBtn').onclick = async () => {
    try {
      await window.apiCall('/api/vehiculo', 'DELETE', { placa });
      window.showToast("Vehículo eliminado correctamente");
      window.closeModal('modalConfirm');
      await window.refreshAllData();
    } catch (e) {}
  };
  window.openModal('modalConfirm');
}

function openVehicleModal() {
  window.state.editTarget = null;
  document.getElementById('mvTitle').textContent = 'Agregar vehículo';
  document.getElementById('mvSub').textContent = 'Ingresa los datos del nuevo vehículo.';
  document.getElementById('formVehicle').reset();
  const placaEl = document.getElementById('mvPlaca');
  placaEl.readOnly = false;
  placaEl.disabled = false;
  document.getElementById('mvTipo').value = '';
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
