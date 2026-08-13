// ─── Constantes ───────────────────────────────────────────────────────────────
const DOW = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
const DOW_FULL = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];
const CUTOFF = 990;   // 16:30 en minutos
const NOMBRES_MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const INVALID_MUNS = new Set(['N/D', '0', '0.0', '0:00', '00:00', 'NAN', 'NONE', '']);

// ─── Helpers Matemáticos y Tiempo ─────────────────────────────────────────────
const m2s = m => `${Math.floor(m / 60).toString().padStart(2, "0")}:${(m % 60).toString().padStart(2, "0")}`;

const getBestDay = v => {
  let best = null, bestMin = Infinity;
  for (let d = 0; d <= 6; d++) {
    const e = v.horaDow && v.horaDow[d];
    if (e && e.m <= CUTOFF && e.m < bestMin) { bestMin = e.m; best = d; }
  }
  return best;
};

// ─── Helpers UI ───────────────────────────────────────────────────────────────
const cellCls = m => m <= 870 ? "ideal" : m <= 930 ? "good" : m <= 990 ? "ok" : m <= 1020 ? "late" : "bad";
const bCls = n => n === 0 ? "b-crit" : n === 1 ? "b-warn" : "b-ok";
const bTxt = n => n === 0 ? "Crítico" : n === 1 ? "Bajo" : "OK";

function showToast(msg, type = "good") {
  const toast = document.getElementById('toast');
  if (!toast) return;
  const msgEl = document.getElementById('toastMsg');
  if (msgEl) msgEl.textContent = msg; else toast.textContent = msg;
  toast.className = `toast open ${type}`;
  setTimeout(() => { toast.className = 'toast'; }, 3500);
}

function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.classList.add('open');
    setTimeout(() => {
      const firstInput = modal.querySelector('input:not([type="hidden"]), select, textarea');
      if (firstInput) firstInput.focus();
    }, 100);
  }
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.classList.remove('open');
    const form = modal.querySelector('form');
    if (form) form.reset();
  }
}

// ─── Exportar al window para uso global ─────────────────────────────────────────
window.DOW = DOW;
window.DOW_FULL = DOW_FULL;
window.CUTOFF = CUTOFF;
window.NOMBRES_MESES = NOMBRES_MESES;
window.INVALID_MUNS = INVALID_MUNS;
window.m2s = m2s;
window.getBestDay = getBestDay;
window.cellCls = cellCls;
window.bCls = bCls;
window.bTxt = bTxt;
window.showToast = showToast;
window.openModal = openModal;
window.closeModal = closeModal;
