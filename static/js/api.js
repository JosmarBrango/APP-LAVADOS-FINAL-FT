// ─── API Wrapper ──────────────────────────────────────────────────────────────
async function apiCall(url, method = 'GET', body = null) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' }
  };
  if (body) options.body = JSON.stringify(body);
  
  try {
    const res = await fetch(url, options);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || `HTTP error! status: ${res.status}`);
    }
    return data;
  } catch (e) {
    console.error(`API Error (${url}):`, e);
    window.showToast(e.message || "Error de red");
    throw e;
  }
}

window.apiCall = apiCall;
