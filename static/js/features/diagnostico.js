// ─── Vista Diagnóstico ────────────────────────────────────────────────────────
function renderDiagnostico() {
  const total = window.state.vehiculos.length;
  const elDiagTotalVeh = document.getElementById('diagTotalVeh');
  if (elDiagTotalVeh) elDiagTotalVeh.textContent = `${total} vehículos`;

  const isValidMun = m => {
    if (!m) return false;
    const u = m.toUpperCase().trim();
    if (window.INVALID_MUNS.has(u)) return false;
    if (/^\d+$/.test(u) || /^\d{1,2}:\d{2}$/.test(u)) return false;
    return true;
  };

  const mesClave = window.state.selectedMes;
  const isTotalMode = mesClave === 'TOTAL';
  const isMesActual = mesClave === 'mes_actual';
  let mesFiltroReal = mesClave;
  if (isMesActual) {
    const hoy = new Date();
    mesFiltroReal = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}`;
  }

  const muns = [...new Set(window.state.vehiculos.map(v => v.mun).filter(isValidMun))].sort();

  window.toggleMunRow = function (id, el) {
    const row = document.getElementById('munRow_' + id);
    if (row) {
      if (row.style.display === 'none') {
        row.style.display = 'table-row';
        el.querySelector('.arrow-icon').textContent = '▼';
      } else {
        row.style.display = 'none';
        el.querySelector('.arrow-icon').textContent = '▶';
      }
    }
  };

  const diagBody = document.getElementById('diagBody');
  if (diagBody) {
    diagBody.innerHTML = muns.map(mun => {
      const vv = window.state.vehiculos.filter(v => v.mun === mun);

      let lavHist;
      if (isTotalMode) {
        lavHist = window.state.historial.filter(
          h => vv.some(v => v.placa === h.placa) && h.tipo_lavado === 'General'
        );
      } else {
        lavHist = window.state.historial.filter(
          h => vv.some(v => v.placa === h.placa)
            && h.tipo_lavado === 'General'
            && (h.fecha || '').startsWith(mesFiltroReal)
        );
      }

      const lav = lavHist.length;
      const placasConLav = new Set(lavHist.map(h => h.placa));
      const sin = vv.filter(v => !placasConLav.has(v.placa)).length;
      const meta = vv.length;
      const pct = meta > 0 ? ((placasConLav.size / meta) * 100).toFixed(1) : 0;
      const barCls = parseFloat(pct) < 33 ? 'crit' : parseFloat(pct) < 66 ? 'warn' : 'ok';
      const badgeCls = sin > 0 ? 'b-crit' : 'b-ok';

      const vehiculosList = vv.map(v => {
        const lavado = placasConLav.has(v.placa);
        const cls = lavado ? 'badge b-ok' : 'badge b-crit';
        return `<span class="${cls}" style="margin:2px" title="${lavado ? 'Lavado en el periodo' : 'Sin lavado en el periodo'}">${v.placa}</span>`;
      }).join('');
      const idSaf = mun.replace(/[^a-zA-Z0-9]/g, '_');

      return `
        <tr onclick="toggleMunRow('${idSaf}', this)" style="cursor:pointer; transition: background 0.2s;" onmouseover="this.style.background='var(--bg)'" onmouseout="this.style.background='transparent'">
          <td style="font-weight:500"><span class="arrow-icon" style="font-size:10px; color:var(--muted); margin-right:4px;">▶</span> ${mun}</td>
          <td><span class="badge b-info">${vv.length}</span></td>
          <td><span style="font-family:var(--mono);font-size:13px">${lav}</span></td>
          <td><span class="badge ${badgeCls}">${sin}</span></td>
          <td>
            <div class="bar-wrap">
              <div class="bar-bg"><div class="bar-fill ${barCls}" style="width:${pct}%"></div></div>
              <span style="font-family:var(--mono);font-size:11px;color:var(--muted)">${pct}%</span>
            </div>
          </td>
        </tr>
        <tr id="munRow_${idSaf}" style="display:none; background:var(--bg);">
          <td colspan="5" style="padding:16px;">
            <div style="font-size:12px; font-weight:600; color:var(--muted); margin-bottom:8px;">Vehículos en ${mun} — <span style="color:var(--green)">${placasConLav.size} lavados</span> / <span style="color:var(--red)">${sin} pendientes</span>:</div>
            <div style="display:flex; flex-wrap:wrap; gap:4px;">${vehiculosList}</div>
          </td>
        </tr>`;
    }).join('');
  }
}

// ─── Vista Promedios (Heatmap) ────────────────────────────────────────────────
function renderPromedios() {
  window.state.filterMunProm = document.getElementById('promMun')?.value || '';
  window.state.filterEstProm = document.getElementById('promEst')?.value || '';
  window.state.searchProm = document.getElementById('promSearch')?.value.toLowerCase() || '';
  const n_meses = window.state.serverStats?.n_meses ?? 3;

  let data = [...window.state.vehiculos];
  if (window.state.filterMunProm) data = data.filter(v => v.mun === window.state.filterMunProm);
  if (window.state.filterEstProm === 'critico') data = data.filter(v => v.lavGen === 0);
  if (window.state.filterEstProm === 'con') data = data.filter(v => v.lavGen > 0);
  if (window.state.searchProm) data = data.filter(v => v.placa.toLowerCase().includes(window.state.searchProm));

  const countEl = document.getElementById('promCount');
  if (countEl) countEl.textContent = `${data.length} vehículos`;

  const bodyEl = document.getElementById('promBody');
  if (bodyEl) {
    bodyEl.innerHTML = data.map(v => {
      const best = window.getBestDay(v);
      const pct = Math.min((v.lavGen / n_meses) * 100, 100);
      const bc = v.lavGen === 0 ? "crit" : v.lavGen === 1 ? "warn" : "ok";

      let dowCells = '';
      for (let d = 0; d < 7; d++) {
        const e = v.horaDow && v.horaDow[d];
        if (e) {
          const cls = window.cellCls(e.m);
          const outline = d === best ? 'style="outline:2px solid var(--em);outline-offset:1px"' : '';
          const stdTip = e.std ? ` title="σ = ±${Math.round(e.std)} min"` : '';
          dowCells += `<td><div class="dc ${cls}" ${outline}${stdTip}><span class="t">${e.s}</span><span class="c">${e.n} reg.</span></div></td>`;
        } else {
          dowCells += `<td><div class="dc empty">—</div></td>`;
        }
      }

      return `
        <tr>
          <td><span class="placa">${v.placa}</span></td>
          <td style="font-size:11px;color:var(--muted)">${v.mun}</td>
          <td>
            <div style="font-family:var(--mono);font-size:14px;font-weight:700;color:var(--text);">
              ${v.lavGen}
            </div>
          </td>
          ${dowCells}
          <td>
            ${best !== null
          ? `<span style="font-size:10px;font-weight:700;color:var(--em);background:var(--em-dim);padding:2px 6px;border-radius:4px">${window.DOW_FULL[best]}</span>`
          : `<span style="font-size:10px;color:var(--muted2)">N/D</span>`}
          </td>
        </tr>`;
    }).join('');
  }
}

window.renderDiagnostico = renderDiagnostico;
window.renderPromedios = renderPromedios;
