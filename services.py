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
MAX_POR_DIA  = 3      # máximo de vehículos por día en el lavadero

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
    try:
        df = None
        separators = [';', ',', '\t', '|']
        encodings  = ['utf-8-sig', 'latin1', 'utf-8', 'cp1252', 'iso-8859-1']

        # Detección inteligente de fila de encabezado (busca 'PLACA')
        header_row = 0
        for enc in encodings:
            try:
                with open(filepath, 'r', encoding=enc, errors='ignore') as f:
                    for line_idx, line in enumerate(f):
                        if line_idx > 25:
                            break
                        if 'PLACA' in line.upper():
                            header_row = line_idx
                            break
                if header_row is not None:
                    break
            except Exception:
                continue

        # Intentar lectura con los separadores y codificaciones posibles
        for sep in separators:
            for enc in encodings:
                try:
                    temp_df = pd.read_csv(filepath, sep=sep, encoding=enc, skiprows=header_row, header=0, low_memory=False)
                    if temp_df.shape[1] >= 2:
                        cols_upper = [str(c).strip().upper() for c in temp_df.columns]
                        if any('PLACA' in c for c in cols_upper):
                            df = temp_df
                            break
                except Exception:
                    continue
            if df is not None:
                break

        # Fallback sin skiprows si no se detectó
        if df is None:
            for sep in separators:
                for enc in encodings:
                    try:
                        temp_df = pd.read_csv(filepath, sep=sep, encoding=enc, header=0, low_memory=False)
                        if temp_df.shape[1] >= 2:
                            df = temp_df
                            break
                    except Exception:
                        continue
                if df is not None:
                    break

        if df is None or df.empty:
            return {'error': 'No se pudo leer el archivo CSV. Verifica el formato.'}

        # Normalizar nombres de columnas
        df.columns = [str(c).strip().upper() for c in df.columns]

        # Encontrar la columna PLACA exacta o aproximada
        placa_col = None
        for c in df.columns:
            if c == 'PLACA':
                placa_col = c
                break
            if 'PLACA' in c:
                placa_col = c

        if not placa_col:
            return {'error': 'El archivo no contiene ninguna columna con el nombre PLACA.'}

        if placa_col != 'PLACA':
            df.rename(columns={placa_col: 'PLACA'}, inplace=True)

        # Si existe columna ITEM, filtrar numéricos; si no, continuar directamente
        if 'ITEM' in df.columns:
            item_numeric = pd.to_numeric(df['ITEM'], errors='coerce')
            if item_numeric.notna().sum() > 0:
                df = df[item_numeric.notna()].copy()

        # Validación y limpieza de placa
        PLACA_PATTERN = r'^[A-Z]{3}\d{2,3}[A-Z]?$'
        df['PLACA'] = df['PLACA'].astype(str).str.strip().str.upper()
        df = df[df['PLACA'].str.match(PLACA_PATTERN, na=False)].copy()

        if df.empty:
            return {'error': 'No se encontraron registros de placas válidas en el archivo.'}

        # Parsear fechas y día de semana
        fecha_col = next((c for c in df.columns if 'FECHA' in c), None)
        if fecha_col:
            results = df.apply(lambda r: parse_fecha(r.get(fecha_col, '')), axis=1)
            df['FECHA_P'] = results.apply(lambda x: x[0])
            df['DOW']     = results.apply(lambda x: x[1])
        else:
            df['FECHA_P'] = pd.NaT
            df['DOW']     = -1

        # Identificar columna de hora de llegada a lavadero
        hora_lav_col = None
        for c in df.columns:
            if 'LLEGADA' in c and 'LAVADERO' in c:
                hora_lav_col = c
                break
        if not hora_lav_col:
            for c in df.columns:
                if 'LLEGADA' in c or 'HORA LLEG' in c:
                    hora_lav_col = c
                    break

        if hora_lav_col:
            df['HORA_LAV_MIN'] = df[hora_lav_col].astype(str).apply(parse_time)
        else:
            df['HORA_LAV_MIN'] = None

        df_lav = df[(df['HORA_LAV_MIN'].notna()) & (df['HORA_LAV_MIN'] > 0)].copy()

        # Helper para extraer valor más frecuente
        def mode_val(series):
            m = series.dropna().mode()
            return str(m.iloc[0]).strip() if len(m) > 0 else ''

        _INVALID_STRS = {'', '0', '0.0', '0:00', '00:00', 'nan', 'none', 'n/d', 'null', 'undefined'}

        def clean_str(val) -> str:
            if pd.isna(val):
                return ''
            s = str(val).strip()
            if s.lower() in _INVALID_STRS:
                return ''
            return s.upper()

        def clean_mun(val) -> str:
            if pd.isna(val):
                return ''
            s = str(val).strip()
            if s.lower() in _INVALID_STRS or s.replace(':', '').replace('.', '').isdigit():
                return ''
            return s.upper()

        # Columnas de metadatos aproximadas
        sup_col = next((c for c in df.columns if 'SUPERVISOR' in c or 'SUP' in c), None)
        mun_col = next((c for c in df.columns if 'MUNICIPIO' in c or 'MUN' in c or 'CIUDAD' in c), None)
        tipo_col = next((c for c in df.columns if 'TIPO DE VEHICULO' in c or 'TIPO' in c or 'CLASE' in c), None)
        ruta_col = next((c for c in df.columns if 'RUTA' in c and 'NOMBRE' not in c), None)

        sup_map  = df.groupby('PLACA')[sup_col].agg(mode_val)  if sup_col  else pd.Series(dtype=str)
        mun_map  = df.groupby('PLACA')[mun_col].agg(mode_val)  if mun_col  else pd.Series(dtype=str)
        tipo_map = df.groupby('PLACA')[tipo_col].agg(mode_val) if tipo_col else pd.Series(dtype=str)

        if ruta_col:
            ruta_df  = df[df[ruta_col].astype(str).str.strip().isin(['0', '']) == False]
            ruta_map = ruta_df.groupby('PLACA')[ruta_col].agg(mode_val) if not ruta_df.empty else pd.Series(dtype=str)
        else:
            ruta_map = pd.Series(dtype=str)

        # % Rural
        rural_prefixes = ['AR', 'MU', 'BA', 'SP', 'SJ', 'NE']
        if not df_lav.empty and ruta_col:
            df_lav = df_lav.copy()
            df_lav['PREFIJO']  = df_lav[ruta_col].astype(str).str[:2].str.upper()
            df_lav['ES_RURAL'] = df_lav['PREFIJO'].isin(rural_prefixes)
            pct_rural = (df_lav.groupby('PLACA')['ES_RURAL'].mean() * 100).round(0)
        else:
            pct_rural = pd.Series(dtype=float)

        # Promedios con filtro IQR
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
            hora_gral = int(promediar_con_iqr(df_lav['HORA_LAV_MIN']))
        else:
            avg_dow = pd.DataFrame(columns=['PLACA', 'DOW', 'mean_min', 'count', 'std_min'])
            hora_gral = 0

        # Promedio llegada por municipio
        if not df_lav.empty:
            df_lav['MUN'] = df_lav['PLACA'].map(mun_map).apply(clean_mun)
            df_lav_mun_valido = df_lav[df_lav['MUN'] != '']
            mun_avg = (
                df_lav_mun_valido.groupby('MUN')['HORA_LAV_MIN']
                .mean()
                .round(2)
                .apply(lambda x: round(x / 60, 4))
                .sort_values()
                .to_dict()
            ) if not df_lav_mun_valido.empty else {}
        else:
            mun_avg = {}

        # Construir lista consolidada de vehículos
        placas = sorted(df['PLACA'].unique())
        vehiculos = []
        for placa in placas:
            veh = {
                'placa':    placa,
                'mun':      clean_mun(mun_map.get(placa, '')),
                'tipo':     clean_str(tipo_map.get(placa, '')),
                'ruta':     clean_str(ruta_map.get(placa, '')),
                'pctRural': int(pct_rural.get(placa, 0)) if pd.notna(pct_rural.get(placa, 0)) else 0,
                'sup':      clean_str(sup_map.get(placa, '')),
                'lavGen':   0,
                'ultimo':   'NUNCA',
                'horaDow':  {}
            }
            veh_dow = avg_dow[avg_dow['PLACA'] == placa]
            for _, row in veh_dow.iterrows():
                try:
                    d  = int(row['DOW'])
                    mm = int(row['mean_min'])
                    veh['horaDow'][d] = {
                        's':   mins_to_str(mm),
                        'm':   mm,
                        'n':   int(row['count']),
                        'std': round(float(row['std_min']), 1) if not pd.isna(row['std_min']) else 0
                    }
                except Exception:
                    pass
            vehiculos.append(veh)

        total_veh = len(placas)
        total_gen = 0
        sin_gen   = total_veh
        n_meses   = 1
        meta      = total_veh * n_meses
        deficit   = meta - total_gen
        pct_cum   = 0

        dias_reg = int(df['FECHA_P'].dropna().nunique()) if 'FECHA_P' in df.columns else 0

        return {
            'vehiculos': vehiculos,
            'historial_lavados': [],
            'stats': {
                'total_veh':   total_veh,
                'total_gen':   total_gen,
                'sin_gen':     sin_gen,
                'meta':        meta,
                'deficit':     deficit,
                'pct_cum':     pct_cum,
                'n_meses':     n_meses,
                'hora_gral':   mins_to_str(hora_gral),
                'periodo':     'Sin datos',
                'dias_reg':    dias_reg,
            },
            'chartData': {
                'lavadosPorMes': {'labels': [], 'data': [], 'meta': total_veh},
                'munAvg':        mun_avg,
                'tiposLavado':   {'Enjuague': 0, 'Sencillo': 0, 'General': 0},
            }
        }
    except Exception as e:
        return {'error': f'Error al procesar el archivo CSV: {str(e)}'}


# ─── Algoritmo de Programación Equitativa ────────────────────────────────────
def generar_programacion(vehiculos: list, start_date_str: str, end_date_str: str,
                         max_por_dia: int = MAX_POR_DIA,
                         manual_overrides: dict = None) -> list:
    """
    Distribuye los vehículos EQUITATIVAMENTE en el rango de fechas:
      - Ningún día tendrá significativamente más lavados que otro.
      - Se respeta el mejor día de la semana de cada vehículo (horaDow).
      - Los overrides manuales tienen prioridad absoluta.
      - IMPORTANTE: Se excluyen los vehículos sin ningún registro de lavado.
    """
    # Filtrar vehículos que no tienen ningún registro (horaDow vacío)
    vehiculos = [v for v in vehiculos if len(v.get('horaDow', {})) > 0]
    import datetime as dt
    import math

    try:
        start_date = dt.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date   = dt.datetime.strptime(end_date_str,   '%Y-%m-%d').date()
    except Exception:
        today      = dt.date.today()
        start_date = today
        end_date   = today + dt.timedelta(days=30)

    # ─── Construir lista y agrupación de fechas ───────────────────────────
    fechas = []
    curr = start_date
    while curr <= end_date:
        fechas.append(curr.strftime('%Y-%m-%d'))
        curr += dt.timedelta(days=1)

    if not fechas:
        return []

    fechas_por_dow: dict[int, list[str]] = {d: [] for d in range(7)}
    for f in fechas:
        d_obj = dt.datetime.strptime(f, '%Y-%m-%d').date()
        dow   = (d_obj.weekday() + 1) % 7   # 0=Dom … 6=Sáb
        fechas_por_dow[dow].append(f)

    # ─── Helpers ──────────────────────────────────────────────────────────
    def turno_info(mins: int) -> dict:
        if mins <= 870: return {'label': 'Turno ideal',            'color': '#3FB950', 'cls': 'ideal'}
        if mins <= 930: return {'label': 'Turno bueno',            'color': '#8ACC68', 'cls': 'good'}
        if mins <= 990: return {'label': 'Turno posible',          'color': '#F0B429', 'cls': 'ok'}
        return             {'label': 'Requiere coordinación',     'color': '#E3B341', 'cls': 'late'}

    def get_best_dow(v: dict) -> tuple[int | None, int]:
        hora_dow  = v.get('horaDow', {})
        best_dow, best_min = None, 99999
        for d_key, entry in hora_dow.items():
            d = int(d_key)
            m = entry.get('m', 99999)
            if m <= CUTOFF_MIN and m < best_min:
                best_min = m
                best_dow = d
        return best_dow, best_min

    def build_result_entry(v: dict, assigned: str | None, best_dow: int | None,
                           best_min: int, razon: str | None = None) -> dict:
        hora_dow  = v.get('horaDow', {})
        best_entry = hora_dow.get(str(best_dow)) if best_dow is not None else {}
        best_entry = best_entry or hora_dow.get(best_dow) or {}
        best_mins  = best_entry.get('m', 0)
        fin3h      = best_mins + WASH_HOURS * 60
        fin4h      = best_mins + (WASH_HOURS + 1) * 60
        return {
            **v,
            'bestDow':       best_dow,
            'bestMin':       best_min,
            'diaAsignado':   assigned,
            'razon':         razon,
            'horaMejorDia':  best_entry.get('s', 'N/D'),
            'finEstimado3h': mins_to_str(fin3h) if best_mins else 'N/D',
            'finEstimado4h': mins_to_str(fin4h) if best_mins else 'N/D',
            'turno':         turno_info(best_mins) if best_mins else None,
        }

    # ─── Separar manuales de automáticos ─────────────────────────────────
    manual_overrides = manual_overrides or {}
    vehs_manuales = [v for v in vehiculos if v['placa'] in manual_overrides]
    vehs_auto     = [v for v in vehiculos if v['placa'] not in manual_overrides]

    total_auto = len(vehs_auto)
    total_dias = len(fechas)

    # ─── Presupuesto equitativo ────────────────────────────────────────────
    # base: cuántos van en cada día; los primeros `resto` días llevan 1 extra
    if total_auto > 0 and total_dias > 0:
        base  = total_auto // total_dias
        resto = total_auto % total_dias
        budget: dict[str, int] = {}
        for i, f in enumerate(fechas):
            b = base + (1 if i < resto else 0)
            budget[f] = min(b, max_por_dia)
    else:
        budget = {f: 0 for f in fechas}

    # Descontar asignaciones manuales del presupuesto
    for v in vehs_manuales:
        dia = manual_overrides[v['placa']]
        if dia in budget:
            budget[dia] = max(0, budget[dia] - 1)

    # ─── Enriquecer vehículos automáticos ────────────────────────────────
    enriched = []
    for v in vehs_auto:
        best_dow, best_min = get_best_dow(v)
        n_registros = sum(
            e.get('n', 0) for e in v.get('horaDow', {}).values()
        )
        enriched.append({
            **v,
            'bestDow':    best_dow,
            'bestMin':    best_min,
            'nRegistros': n_registros,
        })

    # Ordenar: primero los que tienen más registros (más confianza en su bestDow),
    # luego por cuántos días del rango coinciden con su bestDow (menos opciones → asignar antes)
    def sort_key(v):
        has_data    = 1 if v['bestDow'] is not None else 0
        n_opciones  = len(fechas_por_dow.get(v['bestDow'], [])) if v['bestDow'] is not None else 999
        return (-has_data, n_opciones, v['bestMin'])

    enriched.sort(key=sort_key)

    # ─── Función de asignación ─────────────────────────────────────────────
    ocupacion: dict[str, int] = {}
    # Inicializar ocupacion con los días manuales
    for v in vehs_manuales:
        dia = manual_overrides[v['placa']]
        ocupacion[dia] = ocupacion.get(dia, 0) + 1

    def asignar(best_dow: int | None) -> str | None:
        """
        Busca el mejor día disponible:
        1. Fechas del bestDow con presupuesto libre (ordenadas por cuota restante desc)
        2. Cualquier fecha con presupuesto libre (ordenadas por cuota restante desc)
        3. Si el presupuesto está agotado, la fecha menos cargada (overflow mínimo)
        """
        def cuota_restante(f: str) -> int:
            return budget.get(f, 0) - ocupacion.get(f, 0)

        # 1. Candidatos del mejor día de la semana con cupo
        if best_dow is not None:
            candidatos = [
                (cuota_restante(f), f)
                for f in fechas_por_dow.get(best_dow, [])
                if cuota_restante(f) > 0
            ]
            if candidatos:
                candidatos.sort(key=lambda x: -x[0])
                return candidatos[0][1]

        # 2. Cualquier fecha con cupo
        todos = [(cuota_restante(f), f) for f in fechas if cuota_restante(f) > 0]
        if todos:
            todos.sort(key=lambda x: -x[0])
            return todos[0][1]

        # 3. Overflow: menos cargado (solo si no excede max_por_dia)
        overflow = [(ocupacion.get(f, 0), f) for f in fechas if ocupacion.get(f, 0) < max_por_dia]
        if overflow:
            overflow.sort(key=lambda x: x[0])
            return overflow[0][1]
        
        return None

    # ─── Asignar vehículos automáticos ───────────────────────────────────
    result_auto = []
    for v in enriched:
        assigned = asignar(v['bestDow'])
        if assigned:
            ocupacion[assigned] = ocupacion.get(assigned, 0) + 1
        razon = None if assigned else 'Sin disponibilidad en el rango'
        result_auto.append(
            build_result_entry(v, assigned, v['bestDow'], v['bestMin'], razon)
        )

    # ─── Agregar vehículos con override manual ────────────────────────────
    result_manuales = []
    for v in vehs_manuales:
        best_dow, best_min = get_best_dow(v)
        assigned = manual_overrides[v['placa']]
        result_manuales.append(
            build_result_entry(v, assigned, best_dow, best_min)
        )

    return result_auto + result_manuales
