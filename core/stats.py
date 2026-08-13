"""
core/stats.py
=============
Lógica de negocio central:
  - Acceso a la base de datos completa
  - Recálculo de KPIs y estadísticas
  - Funciones helper de tiempo
"""
import database
from core.auth_helpers import load_config


# ─── Acceso a datos ───────────────────────────────────────────────────────────
def get_full_db_data() -> dict:
    """Retorna el estado completo de la base de datos."""
    return {
        'vehiculos':          database.get_all_vehiculos(),
        'historial_lavados':  database.get_all_lavados(),
        'stats':              database.get_data('stats') or {},
        'chartData':          database.get_data('chartData') or {},
        'programacion_manual': database.get_data('programacion_manual') or {},
        'last_qr_event':      database.get_data('last_qr_event'),
    }


def save_full_db_data(db_data: dict) -> None:
    """Persiste el estado completo en la base de datos."""
    database.upsert_vehiculos(db_data.get('vehiculos', []))
    database.save_data('stats',              db_data.get('stats', {}))
    database.save_data('chartData',          db_data.get('chartData', {}))
    database.save_data('programacion_manual', db_data.get('programacion_manual', {}))


# ─── Helper de tiempo ─────────────────────────────────────────────────────────
def calc_minutos(h_inicio, h_fin) -> int:
    """Calcula la diferencia en minutos entre dos horas HH:MM."""
    if not h_inicio or not h_fin:
        return 0
    try:
        hi_h, hi_m = map(int, str(h_inicio).strip().split(':'))
        hf_h, hf_m = map(int, str(h_fin).strip().split(':'))
        mi = hi_h * 60 + hi_m
        mf = hf_h * 60 + hf_m
        if mf < mi:
            mf += 24 * 60
        return mf - mi
    except Exception:
        return 0


# ─── Recálculo de estadísticas ────────────────────────────────────────────────
def recalcular_stats(db_data: dict, mes_filtro: str = None) -> dict:
    """
    Recalcula KPIs orientados al MES seleccionado o al TOTAL acumulado.

    - mes_filtro=None o 'mes_actual'  => mes en curso (comportamiento original)
    - mes_filtro='TOTAL'              => métricas históricas acumuladas
    - mes_filtro='YYYY-MM'            => mes específico
    """
    from datetime import datetime as _dt

    vehiculos = db_data.get('vehiculos', [])
    historial = db_data.get('historial_lavados', [])
    total_veh = len(vehiculos)

    hoy = _dt.now()
    MESES_ES = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]

    # ── Determinar clave de mes ───────────────────────────────────────────────
    if mes_filtro == 'TOTAL':
        mes_clave = 'TOTAL'
        mes_actual_label = 'Total histórico'
    else:
        if mes_filtro and mes_filtro not in (None, 'mes_actual'):
            mes_clave = mes_filtro
            try:
                year, month = map(int, mes_filtro.split('-'))
                mes_actual_label = f"{MESES_ES[month - 1]} {year}"
            except Exception:
                mes_clave = hoy.strftime('%Y-%m')
                mes_actual_label = f"{MESES_ES[hoy.month - 1]} {hoy.year}"
        else:
            mes_clave = hoy.strftime('%Y-%m')
            mes_actual_label = f"{MESES_ES[hoy.month - 1]} {hoy.year}"

    # ── Recalcular lavGen y ultimo por vehículo ───────────────────────────────
    for v in vehiculos:
        v_hist = [
            h for h in historial
            if h.get('placa') == v.get('placa')
            and h.get('tipo_lavado', 'General') == 'General'
        ]

        if mes_filtro == 'TOTAL':
            v['lavGen'] = len(v_hist)
        else:
            v_hist_mes = [h for h in v_hist if (h.get('fecha', '') or '').startswith(mes_clave)]
            v['lavGen'] = len(v_hist_mes)

        if v_hist:
            fechas = [h.get('fecha', '') for h in v_hist if h.get('fecha')]
            if fechas:
                ultima_fecha = max(fechas)
                parts = ultima_fecha.split('-')
                v['ultimo'] = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else ultima_fecha
            else:
                v['ultimo'] = 'NUNCA'
        else:
            v['ultimo'] = 'NUNCA'

    # ── Calcular KPIs del período ─────────────────────────────────────────────
    if mes_filtro == 'TOTAL':
        lavados_generales = sum(
            1 for h in historial if h.get('tipo_lavado', 'General') == 'General'
        )
        meta_mes = total_veh
        pendientes = 0
        pct_cum_mes = round(lavados_generales / total_veh * 100, 1) if total_veh > 0 else 0
        placas_con_lavado = set(
            h.get('placa', '') for h in historial
            if h.get('tipo_lavado', 'General') == 'General'
        )
        veh_sin_lavado = total_veh - len(placas_con_lavado)
        meta_proximo_mes = total_veh
    else:
        lavados_generales = sum(
            1 for h in historial
            if h.get('tipo_lavado', 'General') == 'General'
            and (h.get('fecha', '') or '').startswith(mes_clave)
        )
        meta_mes = total_veh
        pendientes = max(0, meta_mes - lavados_generales)
        pct_cum_mes = round(lavados_generales / meta_mes * 100, 1) if meta_mes > 0 else 0
        placas_con_lavado = set(
            h.get('placa', '') for h in historial
            if h.get('tipo_lavado', 'General') == 'General'
            and (h.get('fecha', '') or '').startswith(mes_clave)
        )
        veh_sin_lavado = total_veh - len(placas_con_lavado)
        meta_proximo_mes = total_veh

    total_gen_historico = sum(v.get('lavGen', 0) for v in vehiculos)
    sin_gen_historico   = sum(1 for v in vehiculos if v.get('lavGen', 0) == 0)

    db_data.setdefault('stats', {}).update({
        'total_veh':             total_veh,
        'lavados_mes_actual':    lavados_generales,
        'meta_mes':              meta_mes,
        'pendientes_mes_actual': pendientes if mes_filtro != 'TOTAL' else 0,
        'pct_cum_mes':           pct_cum_mes,
        'veh_sin_lavado_mes':    veh_sin_lavado,
        'mes_actual_label':      mes_actual_label,
        'mes_clave':             mes_clave if mes_filtro != 'TOTAL' else 'TOTAL',
        'meta_proximo_mes':      meta_proximo_mes,
        'total_gen':             total_gen_historico,
        'sin_gen':               sin_gen_historico,
        'meta':                  meta_mes,
        'deficit':               pendientes if mes_filtro != 'TOTAL' else 0,
        'pct_cum':               pct_cum_mes,
    })

    # ── Stats de lavadores ────────────────────────────────────────────────────
    config  = load_config()
    tarifas = config.get('tarifas', {"General": 0, "Sencillo": 0, "Enjuague": 0})
    lavadores_stats = {}

    for h in historial:
        tipo_lavado = h.get('tipo_lavado', 'General')
        minutos     = calc_minutos(h.get('hora_inicio'), h.get('hora_fin'))
        lavadores   = h.get('lavadores', [])
        if not lavadores:
            lav_str = h.get('lavador', '').strip()
            lavadores = [lav_str] if lav_str else []

        n_lavadores = len(lavadores)
        if n_lavadores == 0:
            continue

        tarifa_total        = float(tarifas.get(tipo_lavado, 0))
        pago_por_lavador    = round(tarifa_total / n_lavadores, 0) if n_lavadores > 0 else 0
        minutos_por_lavador = round(minutos / n_lavadores) if n_lavadores > 0 else minutos

        for lavador in lavadores:
            lavador = lavador.strip().upper()
            if not lavador:
                continue
            l_stat = lavadores_stats.setdefault(lavador, {
                'total_lavados':        0,
                'tiempo_total_minutos': 0,
                'pago_estimado':        0,
                'tipos':                {'General': 0, 'Sencillo': 0, 'Enjuague': 0},
            })
            fraccion = 1.0 / n_lavadores
            l_stat['total_lavados']        += fraccion
            l_stat['tiempo_total_minutos'] += minutos_por_lavador
            l_stat['pago_estimado']        += pago_por_lavador
            l_stat['tipos'][tipo_lavado]    = l_stat['tipos'].get(tipo_lavado, 0) + fraccion

    # ── Promedios de tiempo ───────────────────────────────────────────────────
    total_espera, lavados_con_espera = 0, 0
    tiempo_por_tipo = {
        'General':  {'t': 0, 'c': 0},
        'Sencillo': {'t': 0, 'c': 0},
        'Enjuague': {'t': 0, 'c': 0},
    }

    for h in historial:
        t_espera = h.get('tiempo_espera')
        if t_espera is not None and isinstance(t_espera, (int, float)):
            total_espera += t_espera
            lavados_con_espera += 1
        t_lavado = h.get('tiempo_lavado')
        t_tipo   = h.get('tipo_lavado', 'General')
        if t_lavado is not None and isinstance(t_lavado, (int, float)) and t_tipo in tiempo_por_tipo:
            tiempo_por_tipo[t_tipo]['t'] += t_lavado
            tiempo_por_tipo[t_tipo]['c'] += 1

    avg_espera        = round(total_espera / lavados_con_espera) if lavados_con_espera > 0 else 0
    avg_lavado_por_tipo = {
        k: (round(v['t'] / v['c']) if v['c'] > 0 else 0)
        for k, v in tiempo_por_tipo.items()
    }

    db_data['stats']['avg_espera']         = avg_espera
    db_data['stats']['avg_lavado_por_tipo'] = avg_lavado_por_tipo
    db_data['lavadores_stats']             = lavadores_stats
    return db_data
