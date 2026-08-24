// ─── Configuración y Gestión de Usuarios ──────────────────────────────────────
function switchConfigTab(tabId, btnEl) {
  document.querySelectorAll('.config-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.config-tab').forEach(b => {
    b.classList.remove('active');
    b.style.color = 'var(--muted)';
    b.style.borderBottomColor = 'transparent';
    b.style.fontWeight = '500';
  });

  document.getElementById('tab-' + tabId).style.display = 'block';
  btnEl.classList.add('active');
  btnEl.style.color = 'var(--accent)';
  btnEl.style.borderBottomColor = 'var(--accent)';
  btnEl.style.fontWeight = '600';

  if (tabId === 'cuentas') {
    loadUsers();
  } else if (tabId === 'nomina') {
    loadTarifas();
  }
}

async function loadTarifas() {
  try {
    const data = await window.apiCall('/api/config/tarifas');
    document.getElementById('tarifaGeneral').value = '$ ' + (data['General'] || 0).toLocaleString('es-CO');
    document.getElementById('tarifaSencillo').value = '$ ' + (data['Sencillo'] || 0).toLocaleString('es-CO');
    document.getElementById('tarifaEnjuague').value = '$ ' + (data['Enjuague'] || 0).toLocaleString('es-CO');
  } catch (e) {
    // API Wrapper maneja error
  }
}

document.addEventListener('input', e => {
  if (e.target && e.target.classList.contains('money-input')) {
    let val = e.target.value.replace(/\D/g, '');
    if (!val) { e.target.value = ''; return; }
    e.target.value = '$ ' + parseInt(val, 10).toLocaleString('es-CO');
  }
});

async function saveTarifas(e) {
  e.preventDefault();
  const getVal = (id) => parseFloat(document.getElementById(id).value.replace(/\D/g, '')) || 0;

  const data = {
    'General': getVal('tarifaGeneral'),
    'Sencillo': getVal('tarifaSencillo'),
    'Enjuague': getVal('tarifaEnjuague'),
  };

  const btn = e.target.querySelector('button');
  btn.disabled = true;
  btn.textContent = 'Guardando...';

  try {
    await window.apiCall('/api/config/tarifas', 'POST', data);
    window.showToast('Tarifas actualizadas ✓');
    window.state._tarifas = data;
    await window.refreshAllData();
  } catch (err) {
  } finally {
    btn.disabled = false;
    btn.textContent = 'Guardar Tarifas';
  }
}

async function loadUsers() {
  try {
    const users = await window.apiCall('/api/users');
    const bodyEl = document.getElementById('usersBody');
    if (bodyEl) {
      bodyEl.innerHTML = users.map(u => `
        <tr>
          <td style="font-weight:600">${u.username}</td>
          <td>${u.name}</td>
          <td><span class="badge ${u.role === 'admin' ? 'b-ok' : 'b-warn'}">${u.role}</span></td>
          <td><span class="badge ${u.active ? 'b-ok' : 'b-crit'}">${u.active ? 'Activo' : 'Inactivo'}</span></td>
          <td style="text-align:right">
            <button class="act-btn edit" onclick="editUser('${u.username}')">Editar</button>
            <button class="act-btn del" onclick="deleteUser('${u.username}')">Eliminar</button>
          </td>
        </tr>
      `).join('');
    }
    window._usersCache = users;
  } catch (e) {
  }
}

function toggleUserFields() {
  const role = document.getElementById('muRole').value;
  const credRow = document.getElementById('muCredencialesRow');
  const userIn = document.getElementById('muUsername');
  const passIn = document.getElementById('muPassword');

  if (role === 'lavador') {
    credRow.style.display = 'none';
    userIn.removeAttribute('required');
    passIn.removeAttribute('required');
  } else {
    credRow.style.display = 'flex';
    userIn.setAttribute('required', 'true');
    passIn.setAttribute('required', 'true');
  }
}

function openUserModal() {
  document.getElementById('muTitle').textContent = 'Nuevo Usuario/Lavador';
  document.getElementById('muSub').textContent = 'Crea una nueva cuenta o registra un lavador en el sistema.';
  document.getElementById('formUser').reset();
  document.getElementById('muRole').value = 'lavador';
  document.getElementById('muUsername').readOnly = false;
  toggleUserFields();
  window.openModal('modalUser');
}

function editUser(username) {
  const users = window._usersCache || [];
  const u = users.find(x => x.username === username);
  if (!u) return;

  document.getElementById('muTitle').textContent = 'Editar Usuario/Lavador';
  document.getElementById('muSub').textContent = `Modificando datos de ${u.name}`;
  document.getElementById('muUsername').value = u.username;
  document.getElementById('muUsername').readOnly = true;
  document.getElementById('muPassword').value = u.password || ''; 
  document.getElementById('muName').value = u.name;
  document.getElementById('muRole').value = u.role;
  document.getElementById('muActive').checked = u.active;
  toggleUserFields();

  window.openModal('modalUser');
}

async function saveUser(e) {
  e.preventDefault();
  const username = document.getElementById('muUsername').value.trim();
  const password = document.getElementById('muPassword').value.trim();
  const name = document.getElementById('muName').value.trim();
  const role = document.getElementById('muRole').value;
  const active = document.getElementById('muActive').checked;

  try {
    await window.apiCall('/api/users/save', 'POST', { username, password, name, role, active });
    window.showToast('Usuario guardado');
    window.closeModal('modalUser');
    loadUsers();
  } catch (e) {
  }
}

async function deleteUser(username) {
  if (!confirm(`¿Estás seguro de eliminar el usuario ${username}?`)) return;

  try {
    await window.apiCall('/api/users/delete', 'POST', { username });
    window.showToast('Usuario eliminado', 'err');
    loadUsers();
  } catch (e) {
  }
}

// ─── Edición de Lavados ────────────────────────────────────────────────────────
function buscarLavadosEdicion() {
  const placa = document.getElementById('edLavSearch').value.trim().toUpperCase();
  const tbody = document.getElementById('edLavBody');
  
  if (!placa) {
    window.showToast('Ingresa una placa para buscar', 'warn');
    return;
  }
  
  const filtrados = window.state.historial.filter(l => (l.placa || '').toUpperCase().includes(placa));
  
  if (filtrados.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:20px;">No se encontraron lavados para esta placa.</td></tr>';
    return;
  }
  
  tbody.innerHTML = filtrados.map(l => `
    <tr>
      <td style="font-weight:600;color:var(--muted)">#${l.id}</td>
      <td style="font-weight:700">${l.placa}</td>
      <td>${l.fecha}</td>
      <td><span class="badge ${l.tipo_lavado === 'General' ? 'b-ok' : 'b-warn'}">${l.tipo_lavado}</span></td>
      <td>
        <input type="date" id="edFecha-${l.id}" value="${l.fecha}" style="padding:6px 10px;border:1px solid var(--border);border-radius:6px;font-family:var(--sans);font-size:13px;outline:none;">
      </td>
      <td>
        <button class="act-btn edit" onclick="guardarEdicionLavado(${l.id})">Guardar</button>
      </td>
    </tr>
  `).join('');
}

async function guardarEdicionLavado(id) {
  const inputEl = document.getElementById(`edFecha-${id}`);
  if (!inputEl) return;
  const nuevaFecha = inputEl.value;
  
  if (!nuevaFecha) {
    window.showToast('Selecciona una fecha válida', 'warn');
    return;
  }
  
  if (!confirm(`¿Estás seguro de cambiar la fecha a ${nuevaFecha}?`)) return;
  
  try {
    await window.apiCall('/api/lavado/edit_fecha', 'POST', { id: id, fecha: nuevaFecha });
    window.showToast('Fecha actualizada correctamente', 'ok');
    await window.refreshAllData();
    buscarLavadosEdicion(); // refrescar la tabla actual
  } catch (e) {
  }
}

async function importCSV(e) {
  e.preventDefault();
  const fileInput = document.getElementById('miFile');
  if (!fileInput.files.length) {
    window.showToast('Por favor selecciona un archivo CSV.', 'err');
    return;
  }

  const btn = document.getElementById('miBtn');
  btn.disabled = true;
  btn.textContent = 'Procesando…';

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  try {
    const res = await fetch('/upload', { method: 'POST', body: formData });
    let data;
    try {
      data = await res.json();
    } catch {
      window.showToast(`Error en el servidor al procesar el archivo (código ${res.status})`, 'err');
      return;
    }

    if (!res.ok || data.error) { 
      window.showToast(data.error || 'No se pudo procesar el archivo CSV.', 'err'); 
    } else { 
      const total = data.total_vehiculos || (data.vehiculos ? data.vehiculos.length : '');
      const msg = total ? `Se importaron ${total} vehículos correctamente ✓` : 'Datos importados correctamente ✓';
      window.showToast(msg); 
      await window.refreshAllData(); 
      window.closeModal('modalImport'); 
    }
  } catch (netErr) { 
    window.showToast('Error de red o conexión con el servidor', 'err'); 
  } finally {
    btn.disabled = false;
    btn.textContent = 'Procesar e Importar';
    document.getElementById('formImport').reset();
  }
}


window.switchConfigTab = switchConfigTab;
window.loadTarifas = loadTarifas;
window.saveTarifas = saveTarifas;
window.loadUsers = loadUsers;
window.toggleUserFields = toggleUserFields;
window.openUserModal = openUserModal;
window.editUser = editUser;
window.saveUser = saveUser;
window.deleteUser = deleteUser;
window.buscarLavadosEdicion = buscarLavadosEdicion;
window.guardarEdicionLavado = guardarEdicionLavado;
window.importCSV = importCSV;
