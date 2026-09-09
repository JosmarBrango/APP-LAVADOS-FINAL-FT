/**
 * offline_db.js — Flota Uraba PWA Offline
 */

const OFFLINE_DB_NAME = 'FlotaLavadosOfflineDB';
const OFFLINE_DB_VERSION = 1;
const STORE_PENDING = 'pending_lavados';
const STORE_CATALOG = 'catalog_cache';

let _db = null;

function initOfflineDB() {
  return new Promise((resolve, reject) => {
    if (_db) { resolve(_db); return; }
    const req = indexedDB.open(OFFLINE_DB_NAME, OFFLINE_DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_PENDING)) {
        const store = db.createObjectStore(STORE_PENDING, { keyPath: 'id', autoIncrement: true });
        store.createIndex('status', 'status', { unique: false });
        store.createIndex('created_at', 'created_at', { unique: false });
      }
      if (!db.objectStoreNames.contains(STORE_CATALOG)) {
        db.createObjectStore(STORE_CATALOG, { keyPath: 'key' });
      }
    };
    req.onsuccess = (e) => { _db = e.target.result; resolve(_db); };
    req.onerror = (e) => { console.error('[OfflineDB] Error:', e.target.error); reject(e.target.error); };
  });
}

async function savePendingLavado(data) {
  const db = await initOfflineDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_PENDING, 'readwrite');
    const store = tx.objectStore(STORE_PENDING);
    const record = {
      placa: data.placa || '', tipo_lavado: data.tipo_lavado || 'General',
      municipio: data.municipio || '', fecha: data.fecha || '',
      hora_llegada: data.hora_llegada || '', hora_inicio: data.hora_inicio || '',
      hora_fin: data.hora_fin || '',
      lavadores: Array.isArray(data.lavadores) ? data.lavadores : [],
      checklist: data.checklist || {}, fotos: Array.isArray(data.fotos) ? data.fotos : [],
      origen: data.origen || 'qr',
      created_at: new Date().toISOString(), status: 'pending', retry_count: 0,
    };
    const req = store.add(record);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function getPendingLavados() {
  const db = await initOfflineDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_PENDING, 'readonly');
    const req = tx.objectStore(STORE_PENDING).index('status').getAll('pending');
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

async function getPendingCount() {
  const p = await getPendingLavados();
  return p.length;
}

async function removePendingLavado(id) {
  const db = await initOfflineDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_PENDING, 'readwrite');
    const req = tx.objectStore(STORE_PENDING).delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

async function cacheCatalog(catalogData) {
  const db = await initOfflineDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CATALOG, 'readwrite');
    tx.objectStore(STORE_CATALOG).put({ key: 'main', data: catalogData, cached_at: new Date().toISOString() });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function getCachedCatalog() {
  const db = await initOfflineDB();
  return new Promise((resolve) => {
    const tx = db.transaction(STORE_CATALOG, 'readonly');
    const req = tx.objectStore(STORE_CATALOG).get('main');
    req.onsuccess = () => resolve(req.result ? req.result.data : null);
    req.onerror = () => resolve(null);
  });
}

function compressImage(file, maxDimension = 1600, quality = 0.82) {
  return new Promise((resolve) => {
    if (!file || !file.type.startsWith('image/')) { resolve(file); return; }
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        let { width, height } = img;
        const ratio = Math.min(maxDimension / width, maxDimension / height, 1);
        width = Math.round(width * ratio); height = Math.round(height * ratio);
        const canvas = document.createElement('canvas');
        canvas.width = width; canvas.height = height;
        canvas.getContext('2d').drawImage(img, 0, 0, width, height);
        canvas.toBlob((blob) => {
          if (blob && blob.size < file.size) resolve(new File([blob], file.name, { type: 'image/jpeg', lastModified: Date.now() }));
          else resolve(file);
        }, 'image/jpeg', quality);
      };
      img.onerror = () => resolve(file);
      img.src = e.target.result;
    };
    reader.onerror = () => resolve(file);
    reader.readAsDataURL(file);
  });
}

async function syncPendingLavados(onProgress) {
  if (!navigator.onLine) return { synced: 0, failed: 0 };
  let pending; try { pending = await getPendingLavados(); } catch (e) { return { synced: 0, failed: 0 }; }
  if (pending.length === 0) return { synced: 0, failed: 0 };
  let synced = 0, failed = 0;
  for (const record of pending) {
    try {
      const fd = new FormData();
      fd.append('placa', record.placa); fd.append('tipo_lavado', record.tipo_lavado);
      fd.append('municipio', record.municipio); fd.append('fecha', record.fecha);
      fd.append('hora_llegada', record.hora_llegada); fd.append('hora_inicio', record.hora_inicio);
      fd.append('hora_fin', record.hora_fin); fd.append('origen', record.origen || 'qr');
      fd.append('lavadores_json', JSON.stringify(record.lavadores));
      fd.append('checklist_json', JSON.stringify(record.checklist));
      fd.append('offline_created_at', record.created_at);
      if (Array.isArray(record.fotos)) {
        for (let i = 0; i < record.fotos.length; i++) {
          const foto = record.fotos[i];
          if (foto instanceof Blob || foto instanceof File) fd.append('fotos', foto, foto.name || ('foto_' + i + '.jpg'));
        }
      }
      const res = await fetch('/api/lavado/sync_offline', { method: 'POST', body: fd, credentials: 'same-origin' });
      if (res.ok) {
        await removePendingLavado(record.id); synced++;
        if (typeof onProgress === 'function') onProgress({ synced, failed, total: pending.length });
      } else {
        if (res.status >= 400 && res.status < 500) await removePendingLavado(record.id);
        failed++;
      }
    } catch (err) { failed++; }
  }
  return { synced, failed };
}

async function updateConnectionBadge() {
  const count = await getPendingCount();
  const badge = document.getElementById('offlineStatusBadge');
  if (!badge) return;
  if (!navigator.onLine) {
    badge.innerHTML = '<span class=osb-dot osb-amber></span>Modo Patio Offline' + (count > 0 ? ' <strong>&middot; ' + count + ' pend.</strong>' : '');
    badge.className = 'offline-status-badge osb-offline';
  } else if (count > 0) {
    badge.innerHTML = '<span class=osb-dot osb-amber osb-pulse></span>Sincronizando <strong>' + count + '</strong> registro' + (count > 1 ? 's' : '') + '&hellip;';
    badge.className = 'offline-status-badge osb-syncing';
  } else {
    badge.innerHTML = '<span class=osb-dot osb-green></span>En l&iacute;nea';
    badge.className = 'offline-status-badge osb-online';
  }
}

function _showOfflineToast(msg) {
  let t = document.getElementById('offlineToast');
  if (!t) return;
  t.textContent = msg; t.style.opacity = '1'; t.style.transform = 'translateY(0)';
  setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateY(20px)'; }, 4000);
}

window.addEventListener('online', async () => {
  await updateConnectionBadge();
  const result = await syncPendingLavados();
  await updateConnectionBadge();
  if (result.synced > 0) {
    _showOfflineToast('synced:' + result.synced);
    if (typeof window.refreshAllData === 'function') await window.refreshAllData();
  }
});
window.addEventListener('offline', updateConnectionBadge);
window.addEventListener('DOMContentLoaded', async () => { await initOfflineDB(); await updateConnectionBadge(); });

window.OfflineDB = {
  init: initOfflineDB, savePending: savePendingLavado, getPending: getPendingLavados,
  getPendingCount, removePending: removePendingLavado, cacheCatalog, getCachedCatalog,
  compressImage, sync: syncPendingLavados, updateBadge: updateConnectionBadge,
};

