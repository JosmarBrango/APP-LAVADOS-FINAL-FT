import re
import calendar
from datetime import date
import pandas as pd
import numpy as np

ALLOWED_EXTENSIONS = {'csv'}

MONTH_MAP = {
    'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,
    'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12
}
DAY_MAP = {
    'domingo':0,'lunes':1,'martes':2,'miércoles':3,'jueves':4,'viernes':5,'sábado':6
}

# ─── Constantes del negocio ───────────────────────────────────────────────────
CUTOFF_MIN   = 990    # 16:30 — hora máxima de llegada para poder lavar
WASH_HOURS   = 3      # horas mínimas para lavado general
MAX_POR_DIA  = 4      # máximo de vehículos por día en el lavadero

# ─── Helpers básicos ──────────────────────────────────────────────────────────
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_fecha(s):
    try:
        s = str(s).strip().lower()
        m = re.search(r'(\w+), (\d+) de (\w+) de (\d{4})', s)
        if m:
            dow = DAY_MAP.get(m.group(1), -1)
            d, mes_str, y = int(m.group(2)), m.group(3), int(m.group(4))
            mes = MONTH_MAP.get(mes_str)
            if mes:
                return pd.Timestamp(y, mes, d), dow
    except Exception:
        pass
    return pd.NaT, -1

def parse_time(t):
    try:
        parts = str(t).strip().split(':')
        if len(parts) >= 2:
            h, m = int(parts[0]), int(parts[1])
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h * 60 + m
    except Exception:
        pass
    return None

def mins_to_str(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"

# ─── Filtro de outliers IQR ───────────────────────────────────────────────────
def promediar_con_iqr(group: pd.Series) -> float:
    """
    Calcula la media excluyendo outliers con método IQR.
    Evita que un registro con hora '02:30' (posible error de tipeo)
    contamine el promedio del día para ese vehículo.
    """
    if len(group) < 4:
        # Con pocos datos el IQR no es confiable; usar media simple
        return group.mean()
    q1 = group.quantile(0.25)
    q3 = group.quantile(0.75)
    iqr = q3 - q1
    fence_lo = q1 - 1.5 * iqr
    fence_hi = q3 + 1.5 * iqr
    filtrado = group[(group >= fence_lo) & (group <= fence_hi)]
    return filtrado.mean() if not filtrado.empty else group.mean()

def std_sin_outliers(group: pd.Series) -> float:
    """Desviación estándar sobre la muestra sin outliers (para tooltip en el heatmap)."""
    if len(group) < 4:
        return group.std() if len(group) > 1 else 0.0
    q1 = group.quantile(0.25)
    q3 = group.quantile(0.75)
    iqr = q3 - q1
    filtrado = group[(group >= q1 - 1.5 * iqr) & (group <= q3 + 1.5 * iqr)]
    return filtrado.std() if len(filtrado) > 1 else 0.0

# ─── Procesamiento del CSV ────────────────────────────────────────────────────
def process_csv(filepath):
    """
    Lee el CSV de programación de Urabá y devuelve un dict con:
      - vehiculos: lista de objetos por placa
      - stats: métricas KPI
      - chartData: datos para los gráficos
    """
    df = None
    for sep in [';', ',']:
        for enc in ['utf-8-sig', 'latin1', 'utf-8']:
            try:
                df = pd.read_csv(filepath, sep=sep, encoding=enc, skiprows=2, header=0)
                if df.shape[1] > 3:
                    break
            except Exception:
                continue
        else:
            continue
        break

    if df is None or df.empty:
        return {'error': 'No se pudo leer el archivo CSV.'}

    # Filtrar filas de vehículos con ITEM numérico
    df = df[pd.to_numeric(df['ITEM'], errors='coerce').notna()].copy()
    if 'PLACA' not in df.columns:
        return {'error': 'El archivo no contiene la columna PLACA.'}

    # ─── MEJORA #5: Validación de placa más robusta ───────────────────────────
    # Acepta ABC123 y formatos alternativos colombianos
    PLACA_PATTERN = r'^[A-Z]{3}\d{2,3}[A-Z]?$'
    df['PLACA'] = df['PLACA'].str.strip().str.upper()
    df = df[df['PLACA'].str.match(PLACA_PATTERN, na=False)].copy()

    if df.empty:
        return {'error': 'No se encontraron datos de vehículos válidos en el archivo.'}

    # Parsear fechas y día de semana
    results = df.apply(lambda r: parse_fecha(r.get('FECHA', '')), axis=1)
    df['FECHA_P'] = results.apply(lambda x: x[0])
    df['DOW']     = results.apply(lambda x: x[1])
    df['HORA_LAV_MIN'] = df.get('HORA LLEGADA A LAVADERO', pd.Series(dtype=str)).apply(parse_time)

    df_lav = df[(df['HORA_LAV_MIN'].notna()) & (df['HORA_LAV_MIN'] > 0)].copy()

    # Metadatos por placa (valor más frecuente)
    def mode_val(series):
        m = series.mode()
        return str(m.iloc[0]) if len(m) > 0 else 'N/D'

    # Valores de municipio que no son válidos (números, vacíos, horas mal leídas)
    _INVALID_MUNS = {'', '0', '0.0', '0:00', '00:00', 'nan', 'none', 'n/d'}

    def clean_mun(val) -> str:
        """Devuelve 'N/D' si el valor de municipio es inválido o no reconocible."""
        s = str(val).strip()
        if s.lower() in _INVALID_MUNS or s.replace(':', '').replace('.', '').isdigit():
            return 'N/D'
        return s.upper()

    sup_map  = df.groupby('PLACA')['SUPERVISOR'].agg(mode_val)        if 'SUPERVISOR'      in df.columns else pd.Series(dtype=str)
    mun_map  = df.groupby('PLACA')['MUNICIPIO'].agg(mode_val)         if 'MUNICIPIO'       in df.columns else pd.Series(dtype=str)
    tipo_map = df.groupby('PLACA')['TIPO DE VEHICULO'].agg(mode_val)  if 'TIPO DE VEHICULO' in df.columns else pd.Series(dtype=str)

    ruta_df  = df[df.get('RUTA', '0') != '0']
    ruta_map = ruta_df.groupby('PLACA')['RUTA'].agg(mode_val) if not ruta_df.empty else pd.Series(dtype=str)

    # % Rural
    rural_prefixes = ['AR', 'MU', 'BA', 'SP', 'SJ', 'NE']
    df_lav = df_lav.copy()
    df_lav['PREFIJO']  = df_lav.get('RUTA', pd.Series(dtype=str)).str[:2]
    df_lav['ES_RURAL'] = df_lav['PREFIJO'].isin(rural_prefixes)
    pct_rural = (df_lav.groupby('PLACA')['ES_RURAL'].mean() * 100).round(0) if not df_lav.empty else pd.Series(dtype=float)

    # Lavados generales
    df_gen   = df[df.get('General ', '0') == '1']
    n_gen    = df_gen.groupby('PLACA').size()
    last_gen = df_gen.groupby('PLACA')['FECHA_P'].max()

    # ─── MEJORA #4: Promedios con filtro IQR de outliers ─────────────────────
    if not df_lav.empty:
        avg_dow = (
            df_lav.groupby(['PLACA', 'DOW'])['HORA_LAV_MIN']
            .agg(
                mean_min=promediar_con_iqr,
                count='count',
                std_min=std_sin_outliers
            )
            .round(1)
            .reset_index()
        )
    else:
        avg_dow = pd.DataFrame(columns=['PLACA', 'DOW', 'mean_min', 'count', 'std_min'])

    # Promedio general (con IQR también)
    if not df_lav.empty:
        hora_gral = int(promediar_con_iqr(df_lav['HORA_LAV_MIN']))
    else:
        hora_gral = 0

    # Período (meses)
    df['MES_AÑO']  = df['FECHA_P'].dt.to_period('M')
    meses_unicos   = sorted(df['MES_AÑO'].dropna().unique())

    # Lavados generales por mes
    gen_por_mes = df_gen.groupby(df_gen['FECHA_P'].dt.to_period('M')).size() if not df_gen.empty else pd.Series(dtype=int)

    # Promedio llegada por municipio (excluir municipios inválidos o N/D)
    df_lav['MUN'] = df_lav['PLACA'].map(mun_map).apply(
        lambda x: clean_mun(x) if pd.notna(x) else 'N/D'
    )
    df_lav_mun_valido = df_lav[df_lav['MUN'] != 'N/D']
    mun_avg = (
        df_lav_mun_valido.groupby('MUN')['HORA_LAV_MIN']
        .mean()
        .round(2)
        .apply(lambda x: round(x / 60, 4))
        .sort_values()
        .to_dict()
    ) if not df_lav_mun_valido.empty else {}

    # Tipos de lavado
    tipo_lavado = {
        'Enjuague': int((df.get('Enjuague', '0') == '1').sum()),
        'Sencillo': int((df.get('Sencillo ', '0') == '1').sum()),
        'General':  int((df.get('General ', '0') == '1').sum()),
    }

    # Construir lista de vehículos
    placas = sorted(df['PLACA'].unique())
    vehiculos = []
    for placa in placas:
        veh = {
            'placa':    placa,
            'mun':      clean_mun(mun_map.get(placa, 'N/D')),
            'tipo':     tipo_map.get(placa, 'N/D'),
            'ruta':     str(ruta_map.get(placa, 'N/D')),
            'pctRural': int(pct_rural.get(placa, 0)),
            'sup':      sup_map.get(placa, 'N/D'),
            'lavGen':   int(n_gen.get(placa, 0)),
            'ultimo':   last_gen[placa].strftime('%d/%m/%Y') if placa in last_gen and pd.notna(last_gen[placa]) else 'NUNCA',
            'horaDow':  {}
        }
        veh_dow = avg_dow[avg_dow['PLACA'] == placa]
        for _, row in veh_dow.iterrows():
            d  = int(row['DOW'])
            mm = int(row['mean_min'])
            veh['horaDow'][d] = {
                's':   mins_to_str(mm),
                'm':   mm,
                'n':   int(row['count']),
                'std': round(float(row['std_min']), 1) if not pd.isna(row['std_min']) else 0
            }
        vehiculos.append(veh)

    total_veh = len(placas)
    total_gen = int(df_gen.shape[0])
    sin_gen   = sum(1 for v in vehiculos if v['lavGen'] == 0)
    n_meses   = len(meses_unicos) if len(meses_unicos) > 0 else 1
    meta      = total_veh * n_meses
    deficit   = meta - total_gen
    pct_cum   = round(total_gen / meta * 100, 1) if meta > 0 else 0

    mes_labels = [str(m) for m in meses_unicos]
    mes_data   = [int(gen_por_mes.get(m, 0)) for m in meses_unicos]
    periodo    = f"{mes_labels[0]} — {mes_labels[-1]}" if mes_labels else "Sin datos"

    return {
        'vehiculos': vehiculos,
        'stats': {
            'total_veh':   total_veh,
            'total_gen':   total_gen,
            'sin_gen':     sin_gen,
            'meta':        meta,
            'deficit':     deficit,
            'pct_cum':     pct_cum,
            'n_meses':     n_meses,
            'hora_gral':   mins_to_str(hora_gral),
            'periodo':     periodo,
            'dias_reg':    int(df['FECHA_P'].nunique()),
        },
        'chartData': {
            'lavadosPorMes': {'labels': mes_labels, 'data': mes_data, 'meta': total_veh},
            'munAvg':        mun_avg,
            'tiposLavado':   tipo_lavado,
        }
    }


# ─── MEJORA #1: Algoritmo de Programación en Python ──────────────────────────
def generar_programacion(vehiculos: list, start_date_str: str, end_date_str: str, max_por_dia: int = MAX_POR_DIA, manual_overrides: dict = None) -> list:
    """
    Algoritmo greedy mejorado para asignar fechas de lavado general en un rango específico.
    """
    import datetime as dt
    
    try:
        start_date = dt.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = dt.datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except Exception:
        today = dt.date.today()
        start_date = today
        end_date = today + dt.timedelta(days=7)

    # Rango de fechas
    fechas = []
    fechas_por_dow = {d: [] for d in range(7)}
    curr = start_date
    while curr <= end_date:
        f_str = curr.strftime('%Y-%m-%d')
        fechas.append(f_str)
        # Python weekday: 0=Lun ... 6=Dom -> convert to 0=Dom ... 6=Sab
        dow = (curr.weekday() + 1) % 7
        fechas_por_dow[dow].append(f_str)
        curr += dt.timedelta(days=1)

    def turno_info(mins: int) -> dict:
        if mins <= 870:
            return {'label': 'Turno ideal',            'color': '#3FB950', 'cls': 'ideal'}
        if mins <= 930:
            return {'label': 'Turno bueno',            'color': '#8ACC68', 'cls': 'good'}
        if mins <= 990:
            return {'label': 'Turno posible',          'color': '#F0B429', 'cls': 'ok'}
        return     {'label': 'Requiere coordinación', 'color': '#E3B341', 'cls': 'late'}

    # Enriquecer con bestDow y bestMin
    enriched = []
    for v in vehiculos:
        best_dow, best_min = None, 99999
        hora_dow = v.get('horaDow', {})
        for d_key, entry in hora_dow.items():
            d = int(d_key)
            m = entry.get('m', 99999)
            if m <= CUTOFF_MIN and m < best_min:
                best_min = m
                best_dow = d
        enriched.append({**v, 'bestDow': best_dow, 'bestMin': best_min})

    # Ordenar: prioridad a los que llegan más temprano
    enriched.sort(key=lambda x: x['bestMin'])

    manual_overrides = manual_overrides or {}
    ocupacion: dict[str, int] = {}
    result = []
    
    # 1. Registrar asignaciones manuales en ocupacion
    for v in enriched:
        if v['placa'] in manual_overrides:
            dia_manual = manual_overrides[v['placa']]
            # Only count if the manual override is within the selected range (optional, but good for tracking)
            ocupacion[dia_manual] = ocupacion.get(dia_manual, 0) + 1

    for v in enriched:
        hora_dow = v.get('horaDow', {})

        is_manual = v['placa'] in manual_overrides
        assigned = None
        if is_manual:
            assigned = manual_overrides[v['placa']]

        if not is_manual and (v['bestDow'] is None or not hora_dow):
            result.append({
                **v,
                'diaAsignado':   None,
                'razon':         'Sin registros de llegada válidos',
                'horaMejorDia':  'N/D',
                'finEstimado3h': 'N/D',
                'finEstimado4h': 'N/D',
                'turno':         None,
            })
            continue

        if not assigned:
            # Buscar fechas que coincidan con el mejor día de la semana dentro del rango
            candidatos = fechas_por_dow.get(v['bestDow'], [])
            
            # Intentar asignar en un candidato con cupo
            for dia in candidatos:
                if ocupacion.get(dia, 0) < max_por_dia:
                    assigned = dia
                    break

            # Desbordamiento: buscar cualquier día libre en el rango seleccionado
            if not assigned:
                for dia in fechas:
                    if ocupacion.get(dia, 0) < max_por_dia:
                        assigned = dia
                        break

            if assigned:
                ocupacion[assigned] = ocupacion.get(assigned, 0) + 1

        best_entry = hora_dow.get(str(v['bestDow'])) or hora_dow.get(v['bestDow']) or {}
        best_mins  = best_entry.get('m', 0)
        fin3h      = best_mins + WASH_HOURS * 60
        fin4h      = best_mins + (WASH_HOURS + 1) * 60

        result.append({
            **v,
            'diaAsignado':   assigned,
            'razon':         None,
            'horaMejorDia':  best_entry.get('s', 'N/D'),
            'finEstimado3h': mins_to_str(fin3h) if best_mins else 'N/D',
            'finEstimado4h': mins_to_str(fin4h) if best_mins else 'N/D',
            'turno':         turno_info(best_mins) if best_mins else None,
        })

    return result
