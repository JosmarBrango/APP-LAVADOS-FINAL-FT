"""
pdf_report.py — Generador de reportes PDF para Flota Urabá.
Usa fpdf2. Diseño limpio, minimalista y legible para presentación a gerencia.

Tipos de reporte:
  - diagnostico   : KPIs + resumen por municipio + vehículos sin lavado
  - programacion  : Tabla de vehículos programados en el rango de fechas
  - lavadores     : Detalle de lavados por cada especialista
  - flota         : Inventario completo de vehículos
"""

import datetime
from collections import defaultdict
from fpdf import FPDF, XPos, YPos

# ── Paleta de colores (monocromática, estilo planilla) ────────────────────────
C_BLACK  = (15,  23,  42)   # Título, texto fuerte
C_DARK   = (51,  65,  85)   # Texto secundario
C_MUTED  = (100, 116, 139)  # Texto apagado, notas
C_LIGHT  = (241, 245, 249)  # Fondo alternado zebra
C_WHITE  = (255, 255, 255)
C_RULE   = (180, 180, 180)  # Líneas de tabla (gris, como en planilla)
C_ACCENT = (14,  165, 233)  # Solo para encabezados de sección (pequeño)
C_RED    = (220, 38,  38)   # Solo para alertas críticas
C_GREEN  = (22,  163, 74)   # Solo para cumplimiento OK
C_HEADER_BG = (220, 220, 220)  # Fondo encabezado tabla (igual que DiarioReport)

# ── Sanitizacion de texto para Helvetica (latin-1) ────────────────────────────
_CHAR_MAP = str.maketrans({
    '\u00e1': 'a', '\u00e9': 'e', '\u00ed': 'i', '\u00f3': 'o', '\u00fa': 'u',
    '\u00c1': 'A', '\u00c9': 'E', '\u00cd': 'I', '\u00d3': 'O', '\u00da': 'U',
    '\u00f1': 'n', '\u00d1': 'N',
    '\u00fc': 'u', '\u00dc': 'U',
    '\u2014': '-', '\u2013': '-',
    '\u00b7': '.', '\u00ba': 'o', '\u00aa': 'a',
    '\u00bf': '?', '\u00a1': '!',
    '\u2019': "'", '\u201c': '"', '\u201d': '"',
})

def _t(text) -> str:
    if text is None: return ''
    try:
        t = str(text).translate(_CHAR_MAP)
        return t.encode('latin-1', errors='replace').decode('latin-1')
    except Exception:
        return str(text).encode('ascii', errors='replace').decode('ascii')


class CleanReport(FPDF):
    """Reporte limpio con cabecera estilo planilla FT-OP-15."""

    def __init__(self, titulo: str, subtitulo: str, responsable: str = ''):
        super().__init__(orientation='L', unit='mm', format='A4')
        self.titulo      = _t(titulo)
        self.subtitulo   = _t(subtitulo)
        self.responsable = _t(responsable)
        self.set_margins(8, 8, 8)
        self.set_auto_page_break(auto=True, margin=14)

    def header(self):
        self.set_draw_color(*C_BLACK)
        self.set_line_width(0.4)
        y0 = 8

        # Logo box
        self.rect(8, y0, 38, 16)
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(*C_BLACK)
        self.set_xy(8, y0 + 4)
        self.cell(38, 8, 'futuraseo', align='C')

        # Caja del titulo principal
        self.rect(46, y0, 243, 16)
        self.set_font('Helvetica', 'B', 12)
        self.set_xy(46, y0 + 2)
        self.cell(243, 7, self.titulo, align='C')
        self.set_font('Helvetica', '', 8)
        self.set_text_color(*C_DARK)
        self.set_xy(46, y0 + 9)
        self.cell(243, 5, self.subtitulo, align='C')

        # Fila 2: fecha + pagina
        y1 = y0 + 16
        self.rect(8, y1, 281, 7)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(*C_BLACK)
        self.set_xy(10, y1 + 1.5)
        fecha_str = datetime.datetime.now().strftime('%d/%m/%Y  %H:%M')
        self.cell(180, 4, f'GENERADO: {fecha_str}', align='L')
        self.set_xy(240, y1 + 1.5)
        self.cell(47, 4, f'Pag. {self.page_no()}', align='C')

        self.set_y(y0 + 16 + 7 + 3)

    def footer(self):
        self.set_y(-10)
        self.set_font('Helvetica', '', 6.5)
        self.set_text_color(*C_MUTED)
        resp = f'{self.responsable}   |   ' if self.responsable else ''
        footer_text = f'{resp}Flota Uraba  -  Sistema de Gestion de Lavados   |   Pag. {self.page_no()}'
        self.cell(0, 5, _t(footer_text), align='C')


# ── Función principal ──────────────────────────────────────────────────────────
def generar_pdf(db_data: dict, programacion: list, start_date: str, end_date: str,
                responsable: str = '', tipo_reporte: str = 'diagnostico') -> bytes:
    stats     = db_data.get('stats', {})
    vehiculos = db_data.get('vehiculos', [])
    historial = db_data.get('historial_lavados', [])

    if tipo_reporte == 'diagnostico':
        return _reporte_diagnostico(stats, vehiculos, historial, start_date, responsable)
    elif tipo_reporte == 'programacion':
        return _reporte_programacion(programacion, vehiculos, start_date, end_date, responsable)
    elif tipo_reporte == 'lavadores':
        return _reporte_lavadores(historial, vehiculos, responsable, db_data.get('lavadores_stats', {}))
    elif tipo_reporte == 'flota':
        return _reporte_flota(vehiculos, stats, responsable)
    elif tipo_reporte == 'diarios':
        return _reporte_lavados_diarios(historial, vehiculos, start_date, end_date, responsable)
    else:
        return _reporte_diagnostico(stats, vehiculos, historial, start_date, responsable)


# ─────────────────────────────────────────────────────────────────────────────
# REPORTE 1: DIAGNÓSTICO GENERAL
# ─────────────────────────────────────────────────────────────────────────────
def _reporte_diagnostico(stats, vehiculos, historial, fecha_corte, responsable):
    pdf = CleanReport(
        titulo='DIAGNOSTICO GENERAL DE FLOTA',
        subtitulo=f'Corte al {fecha_corte}',
        responsable=responsable
    )
    pdf.set_compression(True)
    pdf.add_page()

    # Resumen compacto en texto (sin tarjetas de colores)
    pdf.set_draw_color(*C_BLACK)
    pdf.set_line_width(0.4)
    y_res = pdf.get_y()
    pdf.rect(8, y_res, 281, 10)
    resumen_items = [
        f"Vehiculos: {stats.get('total_veh', 0)}",
        f"Lavados realizados: {stats.get('total_gen', 0)}",
        f"Meta: {stats.get('meta', 0)}",
        f"Deficit: {stats.get('deficit', 0)}",
        f"Sin lavado: {stats.get('sin_gen', 0)}",
        f"Cumplimiento: {stats.get('pct_cum', 0)}%",
    ]
    col_w = 281 / len(resumen_items)
    x = 8
    for item in resumen_items:
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(*C_BLACK)
        pdf.set_xy(x + 1, y_res + 3)
        pdf.cell(col_w - 2, 5, _t(item), align='C')
        x += col_w
    pdf.set_y(y_res + 10 + 4)

    # Tabla por municipio
    _section(pdf, 'Cumplimiento por Municipio')
    n_meses = stats.get('n_meses', 3)
    grupos = defaultdict(lambda: {'veh': 0, 'lav': 0})
    for v in vehiculos:
        mun = v.get('mun', 'N/D')
        if mun and mun.upper() not in ('N/D', '0', ''):
            grupos[mun]['veh'] += 1
            grupos[mun]['lav'] += v.get('lavGen', 0)

    cols = [100, 45, 45, 45, 46]
    hdrs = ['Municipio', 'Vehiculos', 'Lavados', 'Meta', 'Cumplimiento']
    _table_header(pdf, hdrs, cols)
    for idx, (mun, g) in enumerate(sorted(grupos.items())):
        meta = g['veh'] * n_meses
        pct  = (g['lav'] / meta * 100) if meta > 0 else 0
        bg = C_LIGHT if idx % 2 else C_WHITE
        _table_row(pdf, [_t(mun), str(g['veh']), str(g['lav']), str(meta), f'{pct:.1f}%'],
                   cols, bg=bg)
    pdf.ln(5)

    # Vehiculos sin lavado
    pendientes = sorted([v for v in vehiculos if v.get('lavGen', 0) == 0],
                        key=lambda x: (x.get('mun', ''), x.get('placa', '')))
    _section(pdf, f'Vehiculos sin Lavado General ({len(pendientes)} unidades)')
    if not pendientes:
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(*C_DARK)
        pdf.cell(0, 6, 'Todos los vehiculos tienen al menos un lavado registrado.', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        cols2 = [45, 65, 72, 50, 49]
        hdrs2 = ['Placa', 'Municipio', 'Supervisor', 'Ruta', 'Ultimo Lavado']
        _table_header(pdf, hdrs2, cols2)
        for idx, v in enumerate(pendientes):
            bg = C_LIGHT if idx % 2 else C_WHITE
            _table_row(pdf, [
                _t(v.get('placa', '')),
                _t(v.get('mun', 'N/D')),
                _t(v.get('sup', 'N/D')),
                _t(v.get('ruta', 'N/D')),
                _t(v.get('ultimo', 'NUNCA'))
            ], cols2, bg=bg)

    _firma_coordinador(pdf)
    return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────────────────
# REPORTE 2: PROGRAMACIÓN
# ─────────────────────────────────────────────────────────────────────────────
def _reporte_programacion(programacion, vehiculos, start_date, end_date, responsable):
    pdf = CleanReport(
        titulo='PROPUESTA DE PROGRAMACION DE LAVADOS',
        subtitulo=f'Del {start_date} al {end_date}',
        responsable=responsable
    )
    pdf.set_compression(True)
    pdf.add_page()

    asignados   = [v for v in programacion if v.get('diaAsignado')]
    sin_asignar = [v for v in programacion if not v.get('diaAsignado')]

    # Resumen compacto en una sola fila con borde
    pdf.set_draw_color(*C_BLACK)
    pdf.set_line_width(0.4)
    y_res = pdf.get_y()
    pdf.rect(8, y_res, 281, 8)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(*C_BLACK)
    pdf.set_xy(10, y_res + 2)
    pdf.cell(0, 4, f'Total programados: {len(asignados)}   |   Sin asignar: {len(sin_asignar)}', align='L')
    pdf.set_y(y_res + 8 + 4)

    _section(pdf, 'Vehiculos Programados')
    cols = [30, 58, 55, 25, 25, 28, 60]
    hdrs = ['Placa', 'Municipio', 'Supervisor', 'Dia', 'Llegada', 'Fin Est.', 'Estado']
    _table_header(pdf, hdrs, cols)

    prog_sorted = sorted(asignados, key=lambda v: (v.get('diaAsignado') or '', v.get('placa', '')))
    for idx, v in enumerate(prog_sorted):
        turno = v.get('turno') or {}
        bg = C_LIGHT if idx % 2 else C_WHITE
        _table_row(pdf, [
            _t(v.get('placa', '')),
            _t(v.get('mun', 'N/D')),
            _t(v.get('sup', 'N/D')),
            str(v.get('diaAsignado', '-')),
            _t(v.get('horaMejorDia', '-')),
            _t(v.get('finEstimado3h', '-')),
            _t(turno.get('label', '-'))
        ], cols, bg=bg)

    if sin_asignar:
        pdf.ln(5)
        _section(pdf, f'Sin Asignar ({len(sin_asignar)} vehiculos - sin historial de llegada)')
        cols2 = [40, 75, 75, 91]
        hdrs2 = ['Placa', 'Municipio', 'Supervisor', 'Motivo']
        _table_header(pdf, hdrs2, cols2)
        for idx, v in enumerate(sin_asignar):
            bg = C_LIGHT if idx % 2 else C_WHITE
            _table_row(pdf, [
                _t(v.get('placa', '')),
                _t(v.get('mun', 'N/D')),
                _t(v.get('sup', 'N/D')),
                _t(v.get('razon', 'Sin registros de llegada'))
            ], cols2, bg=bg)

    _firma_coordinador(pdf)
    return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────────────────
# REPORTE 3: FT-OP-15 (Antes Lavadores)
# ─────────────────────────────────────────────────────────────────────────────
def _reporte_lavadores(historial, vehiculos, responsable, lavadores_stats=None):
    if lavadores_stats is None: lavadores_stats = {}
    placa_to_mun = {v['placa']: v.get('mun', 'N/D') for v in vehiculos}
    placa_to_tipo = {v['placa']: v.get('tipo', 'N/D') for v in vehiculos}

    pdf = CleanReport(
        titulo='CONTROL DE LAVADOS - DETALLE POR ESPECIALISTA',
        subtitulo=f'Generado el {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}',
        responsable=responsable
    )
    pdf.set_compression(True)
    pdf.add_page()

    if not historial:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.set_text_color(*C_DARK)
        pdf.cell(0, 8, 'No hay registros de lavados en el historial.', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return bytes(pdf.output())

    _section(pdf, 'Registro General de Lavados')
    cols = [20, 28, 22, 17, 17, 17, 14, 16, 25, 25, 80]
    hdrs = ['Placa', 'Municipio', 'Fecha', 'Llegada', 'Inicio', 'Fin', 'Esp.', 'Dur.', 'Tipo Veh.', 'Tipo Lav.', 'Lavadores']

    _table_header(pdf, hdrs, cols)

    totales_tipo_vehiculo = defaultdict(int)

    for idx, h in enumerate(historial):
        bg = C_LIGHT if idx % 2 else C_WHITE
        mun = placa_to_mun.get(h.get('placa', ''), 'N/D')
        t_veh = placa_to_tipo.get(h.get('placa', ''), 'N/D')
        totales_tipo_vehiculo[t_veh] += 1
        lavs = h.get('lavadores')
        if not lavs:
            lavs = [h.get('lavador', 'Sin asignar').strip() or 'Sin asignar']
        lavs_str = ', '.join([_t(l).strip() for l in lavs])
        _table_row(pdf, [
            _t(h.get('placa', '')),
            _t(h.get('municipio', mun)),
            _t(h.get('fecha', '')),
            _t(h.get('hora_llegada', '-')),
            _t(h.get('hora_inicio', h.get('hora', '-'))),
            _t(h.get('hora_fin', '-')),
            f"{h.get('tiempo_espera', '-')}m",
            f"{h.get('tiempo_lavado', '-')}m",
            _t(t_veh),
            _t(h.get('tipo_lavado', 'General')),
            lavs_str
        ], cols, bg=bg)

    pdf.ln(5)

    # Totales por tipo de vehiculo
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(*C_BLACK)
    pdf.cell(0, 6, 'Totales por Tipo de Vehiculo:', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font('Helvetica', '', 9)
    for t_veh, qty in sorted(totales_tipo_vehiculo.items()):
        pdf.cell(10, 6, '', new_x=XPos.RIGHT)
        pdf.cell(60, 6, f'{t_veh}: {qty}', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(3)

    # Totales por Lavador
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(*C_BLACK)
    pdf.cell(0, 6, 'Totales por Lavador (Generales / Sencillos / Enjuagues):', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font('Helvetica', '', 9)
    for lavador, data in sorted(lavadores_stats.items()):
        tipos = data.get('tipos', {})
        t_gen = f"{tipos.get('General', 0):g}"
        t_sen = f"{tipos.get('Sencillo', 0):g}"
        t_enj = f"{tipos.get('Enjuague', 0):g}"
        pdf.cell(10, 6, '', new_x=XPos.RIGHT)
        pdf.cell(0, 6, f'{_t(lavador)}: {t_gen} Generales, {t_sen} Sencillos, {t_enj} Enjuagues', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    _firma_coordinador(pdf)
    return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────────────────
# REPORTE 4: INVENTARIO DE FLOTA
# ─────────────────────────────────────────────────────────────────────────────
def _reporte_flota(vehiculos, stats, responsable):
    pdf = CleanReport(
        titulo='INVENTARIO DE FLOTA',
        subtitulo=f'Corte al {datetime.datetime.now().strftime("%d/%m/%Y")}   |   {len(vehiculos)} vehiculos registrados',
        responsable=responsable
    )
    pdf.set_compression(True)
    pdf.add_page()

    # Resumen compacto en una fila con borde
    pdf.set_draw_color(*C_BLACK)
    pdf.set_line_width(0.4)
    y_res = pdf.get_y()
    pdf.rect(8, y_res, 281, 10)
    resumen_items = [
        f"Total vehiculos: {stats.get('total_veh', len(vehiculos))}",
        f"Lavados generales: {stats.get('total_gen', 0)}",
        f"Sin lavado: {stats.get('sin_gen', 0)}",
        f"Cumplimiento: {stats.get('pct_cum', 0)}%",
    ]
    col_w = 281 / len(resumen_items)
    x = 8
    for item in resumen_items:
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(*C_BLACK)
        pdf.set_xy(x + 1, y_res + 3)
        pdf.cell(col_w - 2, 5, _t(item), align='C')
        x += col_w
    pdf.set_y(y_res + 10 + 4)

    _section(pdf, 'Listado Completo de Vehiculos')
    cols = [30, 62, 32, 35, 72, 35, 15]
    hdrs = ['Placa', 'Municipio', 'Tipo', 'Ruta', 'Supervisor', 'Ultimo Lavado', 'Lav.']
    _table_header(pdf, hdrs, cols)

    sorted_veh = sorted(vehiculos, key=lambda v: (v.get('mun', ''), v.get('placa', '')))
    for idx, v in enumerate(sorted_veh):
        bg = C_LIGHT if idx % 2 else C_WHITE
        lav = v.get('lavGen', 0)
        _table_row(pdf, [
            _t(v.get('placa', '')),
            _t(v.get('mun', 'N/D')),
            _t(v.get('tipo', 'N/D')),
            _t(v.get('ruta', 'N/D')),
            _t(v.get('sup', 'N/D')),
            _t(v.get('ultimo', 'NUNCA')),
            str(lav)
        ], cols, bg=bg)

    _firma_coordinador(pdf)
    return bytes(pdf.output())



# ── Helpers de dibujo ─────────────────────────────────────────────────────────
def _section(pdf: CleanReport, title: str):
    """Encabezado de seccion limpio, estilo planilla."""
    pdf.ln(2)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(*C_BLACK)
    pdf.set_x(8)
    pdf.cell(0, 6, _t(title).upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)


def _firma_coordinador(pdf: CleanReport):
    """Fila de firma al final, igual que en la planilla FT-OP-15."""
    if pdf.get_y() + 12 > 197:
        pdf.add_page()
    y_obs = pdf.get_y() + 2
    pdf.set_draw_color(*C_BLACK)
    pdf.set_line_width(0.4)
    pdf.rect(8, y_obs, 281, 10)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_xy(10, y_obs + 3)
    pdf.cell(80, 4, 'OBSERVACIONES:', align='L')
    pdf.set_xy(160, y_obs + 3)
    pdf.cell(120, 4, 'FIRMA COORDINADOR DE ZONA: ___________________________', align='L')


def _table_header(pdf: CleanReport, headers: list, col_widths: list):
    """Encabezado de tabla con fondo gris claro, estilo planilla."""
    y = pdf.get_y()
    pdf.set_fill_color(*C_HEADER_BG)
    pdf.set_draw_color(*C_BLACK)
    pdf.set_line_width(0.4)
    x = 8
    for hdr, w in zip(headers, col_widths):
        pdf.rect(x, y, w, 9, 'FD')
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(*C_BLACK)
        pdf.set_xy(x + 1, y + 2.5)
        pdf.cell(w - 2, 4.5, _t(hdr).upper(), align='C')
        x += w
    pdf.set_y(y + 9)


def _table_row(pdf: CleanReport, cells: list, col_widths: list,
               bg=C_WHITE, first_color=None, last_color=None):
    """Fila de tabla estilo planilla, sin colores de acento."""
    ROW_H = 7.5
    if pdf.get_y() + ROW_H > 195:
        pdf.add_page()

    y = pdf.get_y()
    pdf.set_draw_color(*C_BLACK)
    pdf.set_line_width(0.25)
    x = 8
    for i, (cell, w) in enumerate(zip(cells, col_widths)):
        pdf.set_fill_color(*bg)
        pdf.rect(x, y, w, ROW_H, 'FD')
        pdf.set_font('Helvetica', 'B' if i == 0 else '', 8)
        pdf.set_text_color(*C_BLACK)
        pdf.set_xy(x + 1.5, y + (ROW_H - 4.5) / 2)
        pdf.cell(w - 3, 4.5, str(cell)[:45], align='L')
        x += w
    pdf.set_y(y + ROW_H)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER INTERNO: duración en minutos
# ─────────────────────────────────────────────────────────────────────────────
def _calc_mins(h_inicio, h_fin) -> int:
    """Calcula la duración en minutos entre dos horas HH:MM."""
    if not h_inicio or not h_fin:
        return 0
    try:
        hi_h, hi_m = map(int, str(h_inicio).split(':'))
        hf_h, hf_m = map(int, str(h_fin).split(':'))
        mi = hi_h * 60 + hi_m
        mf = hf_h * 60 + hf_m
        if mf < mi:
            mf += 24 * 60
        return max(0, mf - mi)
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# REPORTE 5: NÓMINA POR PERÍODO — Ultra-profesional / Corporativo
# ─────────────────────────────────────────────────────────────────────────────
def generar_nomina_pdf(historial: list, tarifas: dict,
                       responsable: str = '',
                       desde: str = '', hasta: str = '') -> bytes:
    """
    Genera el PDF de Liquidación de Nómina con:
      - Portada corporativa con KPIs e índice de lavadores
      - Una sección por especialista: mini-KPIs + tabla de servicios + total
      - Página final de resumen ejecutivo con firma
    """
    return _reporte_nomina(historial, tarifas, responsable, desde, hasta)


def _reporte_nomina(historial_raw, tarifas, responsable, desde, hasta):
    # ─── 1. Filtrar registros válidos ────────────────────────────────────
    historial = [h for h in historial_raw if (
        (not desde or h.get('fecha', '') >= desde) and
        (not hasta or h.get('fecha', '') <= hasta) and
        (h.get('lavador', '').strip() or (h.get('lavadores') and len(h.get('lavadores')) > 0))
    )]
    historial.sort(key=lambda x: x.get('fecha', ''))

    # ─── 2. Agrupar por lavador y calcular métricas ──────────────────────
    por_lavador = defaultdict(list)
    for h in historial:
        lavs = h.get('lavadores', [])
        if not lavs:
            lav = (h.get('lavador') or '').strip().upper()
            lavs = [lav] if lav else []
            
        for lav in lavs:
            lav = lav.strip().upper()
            if lav:
                por_lavador[lav].append(h)

    # Paleta corporativa sobria
    C_HEADER_BG = (15, 23, 42)      # Slate 900
    C_SUB_BG    = (30, 41, 59)      # Slate 800
    C_ZEBRA     = (248, 250, 252)   # Slate 50
    C_BORDER    = (226, 232, 240)   # Slate 200
    C_TEXT      = (15, 23, 42)      # Slate 900
    C_MUTED_TXT = (100, 116, 139)   # Slate 500
    C_LINE      = (203, 213, 225)   # Slate 300

    # ─── 3. Cálculos de Especialistas ────────────────────────────────────
    workers = []
    total_empresa_pago = 0
    total_servicios_empresa = 0
    total_minutos_empresa = 0
    sum_gen = 0
    sum_sen = 0
    sum_enj = 0

    for lav_name in sorted(por_lavador.keys()):
        lavs = por_lavador[lav_name]
        tc = {'General': 0.0, 'Sencillo': 0.0, 'Enjuague': 0.0}
        pago_w = 0.0
        mins_w = 0.0

        for l in lavs:
            tipo = l.get('tipo_lavado', 'General')
            n_lav = len(l.get('lavadores', [])) or 1
            fracc = 1.0 / n_lav

            t_low = tipo.lower()
            if 'sencillo' in t_low:
                tc['Sencillo'] += fracc
            elif 'enjuague' in t_low:
                tc['Enjuague'] += fracc
            else:
                tc['General'] += fracc

            tarifa = float(tarifas.get(tipo, 0))
            pago_w += tarifa / n_lav
            mins_w += _calc_mins(l.get('hora_inicio', ''), l.get('hora_fin', '')) / n_lav

        pago_w_round = round(pago_w)
        total_serv_w = tc['General'] + tc['Sencillo'] + tc['Enjuague']

        total_empresa_pago += pago_w_round
        total_servicios_empresa += total_serv_w
        total_minutos_empresa += mins_w
        sum_gen += tc['General']
        sum_sen += tc['Sencillo']
        sum_enj += tc['Enjuague']

        hrs_str = f'{int(mins_w)//60}h {int(mins_w)%60:02d}m' if mins_w > 0 else '—'

        workers.append({
            'name': lav_name.title(),
            'gen': tc['General'],
            'sen': tc['Sencillo'],
            'enj': tc['Enjuague'],
            'total_serv': total_serv_w,
            'hrs_str': hrs_str,
            'pago': pago_w_round
        })

    especialistas_count = len(workers)
    promedio_por_lavador = round(total_empresa_pago / especialistas_count) if especialistas_count > 0 else 0

    if desde and hasta:
        periodo_str = f'Del {desde} al {hasta}'
    elif desde:
        periodo_str = f'Desde {desde}'
    elif hasta:
        periodo_str = f'Hasta {hasta}'
    else:
        periodo_str = 'Historico Completo'

    fecha_gen = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')

    # ─── 4. Inicializar Documento A4 Portrait ────────────────────────────
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(12, 10, 12)
    page_num = 0

    PAGE_W = 186  # 210 - 24

    def _draw_footer(pn):
        pdf.set_xy(12, 284)
        pdf.set_draw_color(*C_BORDER)
        pdf.set_line_width(0.3)
        pdf.line(12, 284, 198, 284)
        pdf.set_font('Helvetica', '', 6.5)
        pdf.set_text_color(*C_MUTED_TXT)
        pdf.set_xy(12, 285.5)
        pdf.cell(PAGE_W, 4, _t(f'FLOTA URABA S.A.  |  Liquidacion de Nomina  |  Periodo: {periodo_str}  |  Doc. Oficial  |  Pag. {pn}'), align='C')

    def _add_page():
        nonlocal page_num
        pdf.add_page()
        page_num += 1
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(0, 0, 210, 297, 'F')
        return page_num

    # Helper formato decimal limpio
    def _fmt_dec(n):
        return f'{n:.1f}'.rstrip('0').rstrip('.') if n > 0 else '0'

    # ─── PÁGINA 1: Encabezado, KPIs y Tablas ──────────────────────────────
    _add_page()

    # Encabezado Institucional Compacto
    y_hdr = 10
    pdf.set_draw_color(*C_LINE)
    pdf.set_line_width(0.4)
    pdf.rect(12, y_hdr, PAGE_W, 18)

    # Sub-bloque izquierdo: Empresa
    pdf.set_xy(14, y_hdr + 2.5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(*C_TEXT)
    pdf.cell(46, 6, 'FLOTA URABA S.A.', align='L')
    pdf.set_xy(14, y_hdr + 8.5)
    pdf.set_font('Helvetica', '', 7.5)
    pdf.set_text_color(*C_MUTED_TXT)
    pdf.cell(46, 5, 'Control de Lavados Vehiculares', align='L')

    # Línea vertical 1
    pdf.line(60, y_hdr, 60, y_hdr + 18)

    # Sub-bloque central: Título y Período
    pdf.set_xy(62, y_hdr + 2)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(*C_TEXT)
    pdf.cell(78, 6, 'LIQUIDACION DE NOMINA', align='C')
    pdf.set_xy(62, y_hdr + 8.5)
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(*C_MUTED_TXT)
    pdf.cell(78, 5, _t(f'Periodo: {periodo_str}'), align='C')

    # Línea vertical 2
    pdf.line(142, y_hdr, 142, y_hdr + 18)

    # Sub-bloque derecho: Metadatos
    pdf.set_xy(144, y_hdr + 2.5)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(*C_MUTED_TXT)
    pdf.cell(52, 4, f'Emision: {fecha_gen}', align='L')
    pdf.set_xy(144, y_hdr + 7)
    pdf.cell(52, 4, f'Responsable: {_t(responsable or "Administrador")[:18]}', align='L')
    pdf.set_xy(144, y_hdr + 11.5)
    pdf.set_font('Helvetica', 'B', 6.5)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(52, 4, 'DOCUMENTO OFICIAL', align='L')

    # ─── Cinta de Resumen Ejecutivo (KPIs) ──────────────────────────────
    y_kpi = y_hdr + 22
    kpi_w = PAGE_W / 4.0
    kpis = [
        ('TOTAL A LIQUIDAR', f'${total_empresa_pago:,.0f}', True),
        ('SERVICIOS LIQUIDADOS', f'{_fmt_dec(total_servicios_empresa)} serv.', False),
        ('PERSONAL ACTIVO', f'{especialistas_count} especialistas', False),
        ('PROMEDIO / LAVADOR', f'${promedio_por_lavador:,.0f}', False),
    ]

    for i, (lbl, val, is_hi) in enumerate(kpis):
        kx = 12 + i * kpi_w
        pdf.set_fill_color(*C_ZEBRA)
        pdf.set_draw_color(*C_BORDER)
        pdf.set_line_width(0.3)
        pdf.rect(kx, y_kpi, kpi_w, 12, 'FD')

        # Línea superior navy
        pdf.set_fill_color(*C_HEADER_BG)
        pdf.rect(kx, y_kpi, kpi_w, 1.2, 'F')

        # Label
        pdf.set_font('Helvetica', 'B', 5.5)
        pdf.set_text_color(*C_MUTED_TXT)
        pdf.set_xy(kx + 2, y_kpi + 2.5)
        pdf.cell(kpi_w - 4, 3.5, lbl, align='C')

        # Valor
        pdf.set_font('Helvetica', 'B', 9.5)
        pdf.set_text_color(*C_TEXT)
        pdf.set_xy(kx + 2, y_kpi + 6)
        pdf.cell(kpi_w - 4, 5, _t(val), align='C')

    # ─── Sección 1: Tabla Maestra de Especialistas ───────────────────────
    y_sec1 = y_kpi + 16
    pdf.set_fill_color(*C_HEADER_BG)
    pdf.rect(12, y_sec1, PAGE_W, 5.5, 'F')
    pdf.set_font('Helvetica', 'B', 7)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(15, y_sec1 + 1)
    pdf.cell(PAGE_W - 6, 3.5, '1. RESUMEN CONSOLIDADO POR ESPECIALISTA', align='L')

    # Columnas de tabla de especialistas
    COLS_W = [8, 52, 18, 18, 18, 20, 20, 32]
    HDRS_W = ['#', 'ESPECIALISTA', 'GENERALES', 'SENCILLOS', 'ENJUAGUES', 'TOTAL SERV.', 'HRS TRAB.', 'TOTAL LIQUIDADO']

    y_th = y_sec1 + 5.5
    pdf.set_fill_color(*C_SUB_BG)
    pdf.rect(12, y_th, PAGE_W, 5.5, 'F')
    x_c = 12
    for cw, ch in zip(COLS_W, HDRS_W):
        pdf.set_font('Helvetica', 'B', 6)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x_c, y_th + 1)
        align_c = 'L' if ch in ('ESPECIALISTA') else ('R' if ch == 'TOTAL LIQUIDADO' else 'C')
        pdf.cell(cw, 3.5, ch, align=align_c)
        x_c += cw

    y_row = y_th + 5.5
    for idx, w in enumerate(workers, 1):
        bg = C_ZEBRA if idx % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*bg)
        pdf.set_draw_color(*C_BORDER)
        pdf.set_line_width(0.2)
        pdf.rect(12, y_row, PAGE_W, 6, 'FD')

        row_vals = [
            (str(idx), 'C', False),
            (w['name'], 'L', True),
            (_fmt_dec(w['gen']), 'C', False),
            (_fmt_dec(w['sen']), 'C', False),
            (_fmt_dec(w['enj']), 'C', False),
            (_fmt_dec(w['total_serv']), 'C', True),
            (w['hrs_str'], 'C', False),
            (f"${w['pago']:,.0f}", 'R', True),
        ]

        x_c = 12
        for (val, al, is_b), cw in zip(row_vals, COLS_W):
            pdf.set_font('Helvetica', 'B' if is_b else '', 7)
            pdf.set_text_color(*C_TEXT)
            pdf.set_xy(x_c + (1.5 if al == 'L' else (-1.5 if al == 'R' else 0)), y_row + 1.2)
            pdf.cell(cw - (3 if al in ('L', 'R') else 0), 3.5, _t(val), align=al)
            x_c += cw
        y_row += 6

    # Fila de Totales de la Sección 1
    pdf.set_fill_color(*C_HEADER_BG)
    pdf.rect(12, y_row, PAGE_W, 6.5, 'F')
    pdf.set_font('Helvetica', 'B', 7)
    pdf.set_text_color(255, 255, 255)

    pdf.set_xy(14, y_row + 1.5)
    pdf.cell(COLS_W[0] + COLS_W[1] - 2, 3.5, 'TOTALES GENERALES', align='L')

    # Sumas intermedias
    sum_x = 12 + COLS_W[0] + COLS_W[1]
    pdf.set_xy(sum_x, y_row + 1.5); pdf.cell(COLS_W[2], 3.5, _fmt_dec(sum_gen), align='C')
    sum_x += COLS_W[2]
    pdf.set_xy(sum_x, y_row + 1.5); pdf.cell(COLS_W[3], 3.5, _fmt_dec(sum_sen), align='C')
    sum_x += COLS_W[3]
    pdf.set_xy(sum_x, y_row + 1.5); pdf.cell(COLS_W[4], 3.5, _fmt_dec(sum_enj), align='C')
    sum_x += COLS_W[4]
    pdf.set_xy(sum_x, y_row + 1.5); pdf.cell(COLS_W[5], 3.5, _fmt_dec(total_servicios_empresa), align='C')
    sum_x += COLS_W[5]
    hrs_total_str = f'{int(total_minutos_empresa)//60}h {int(total_minutos_empresa)%60:02d}m'
    pdf.set_xy(sum_x, y_row + 1.5); pdf.cell(COLS_W[6], 3.5, hrs_total_str, align='C')
    sum_x += COLS_W[6]
    pdf.set_xy(sum_x - 2, y_row + 1.5); pdf.cell(COLS_W[7], 3.5, f"${total_empresa_pago:,.0f}", align='R')

    y_next = y_row + 10.5

    # ─── Sección 2: Detalle Cronológico de Servicios ─────────────────────
    COLS_D = [18, 16, 22, 22, 22, 14, 42, 15, 15]
    HDRS_D = ['FECHA', 'PLACA', 'MUNICIPIO', 'TIPO', 'HORARIO', 'DUR.', 'ESPECIALISTA(S)', 'TARIFA', 'LIQUIDADO']

    def _draw_sec2_header(y):
        pdf.set_fill_color(*C_HEADER_BG)
        pdf.rect(12, y, PAGE_W, 5.5, 'F')
        pdf.set_font('Helvetica', 'B', 7)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(15, y + 1)
        pdf.cell(PAGE_W - 6, 3.5, '2. REGISTRO DETALLADO DE SERVICIOS REALIZADOS', align='L')

        y_th2 = y + 5.5
        pdf.set_fill_color(*C_SUB_BG)
        pdf.rect(12, y_th2, PAGE_W, 5.5, 'F')
        x_d = 12
        for cw, ch in zip(COLS_D, HDRS_D):
            pdf.set_font('Helvetica', 'B', 6)
            pdf.set_text_color(255, 255, 255)
            pdf.set_xy(x_d, y_th2 + 1)
            align_d = 'L' if ch in ('MUNICIPIO', 'TIPO', 'ESPECIALISTA(S)') else ('R' if ch in ('TARIFA', 'LIQUIDADO') else 'C')
            pdf.cell(cw, 3.5, ch, align=align_d)
            x_d += cw
        return y_th2 + 5.5

    # Si no cabe el inicio de la sección 2 con al menos 3 filas, pasamos a página 2
    if y_next + 28 > 270:
        _draw_footer(page_num)
        _add_page()
        y_next = 12

    y_d_row = _draw_sec2_header(y_next)

    if len(historial) == 0:
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(12, y_d_row, PAGE_W, 8, 'FD')
        pdf.set_font('Helvetica', 'I', 7.5)
        pdf.set_text_color(*C_MUTED_TXT)
        pdf.set_xy(12, y_d_row + 2)
        pdf.cell(PAGE_W, 4, 'No se registraron lavados en el periodo seleccionado.', align='C')
        y_d_row += 8
    else:
        for idx_d, l in enumerate(historial, 1):
            # Salto de página automático si se acerca al final
            if y_d_row + 6 > 272:
                _draw_footer(page_num)
                _add_page()
                y_d_row = _draw_sec2_header(12)

            bg = C_ZEBRA if idx_d % 2 == 0 else (255, 255, 255)
            pdf.set_fill_color(*bg)
            pdf.set_draw_color(*C_BORDER)
            pdf.set_line_width(0.2)
            pdf.rect(12, y_d_row, PAGE_W, 5.5, 'FD')

            tipo = l.get('tipo_lavado', 'General')
            tarifa_u = float(tarifas.get(tipo, 0))
            lavs_list = l.get('lavadores', []) or ([l.get('lavador')] if l.get('lavador') else [])
            n_lav = len(lavs_list) or 1
            liq_val = tarifa_u / n_lav

            mins_l = _calc_mins(l.get('hora_inicio', ''), l.get('hora_fin', ''))
            dur_str = f'{mins_l//60}h {mins_l%60:02d}m' if mins_l > 0 else '—'
            horario_str = f"{l.get('hora_inicio','—')} → {l.get('hora_fin','—')}" if (l.get('hora_inicio') and l.get('hora_fin')) else (l.get('hora_inicio') or l.get('hora_llegada') or '—')
            esp_str = ', '.join(lavs_list).title()

            vals_d = [
                (l.get('fecha', '—'), 'C', False),
                (l.get('placa', '—'), 'C', True),
                (l.get('municipio', '—')[:12], 'L', False),
                (tipo[:12], 'L', False),
                (horario_str, 'C', False),
                (dur_str, 'C', False),
                (esp_str[:25], 'L', False),
                (f"${tarifa_u:,.0f}", 'R', False),
                (f"${liq_val:,.0f}", 'R', True),
            ]

            x_d = 12
            for (val, al, is_b), cw in zip(vals_d, COLS_D):
                pdf.set_font('Helvetica', 'B' if is_b else '', 6.5)
                pdf.set_text_color(*C_TEXT)
                pdf.set_xy(x_d + (1.2 if al == 'L' else (-1.2 if al == 'R' else 0)), y_d_row + 1)
                pdf.cell(cw - (2.4 if al in ('L', 'R') else 0), 3.5, _t(str(val)), align=al)
                x_d += cw
            y_d_row += 5.5

    # ─── Sección 3: Firmas y Validación ──────────────────────────────────
    y_sign = y_d_row + 8
    if y_sign + 26 > 275:
        _draw_footer(page_num)
        _add_page()
        y_sign = 16

    pdf.set_draw_color(*C_LINE)
    pdf.set_line_width(0.3)

    # Firma 1: Administrador / Responsable
    pdf.line(20, y_sign + 14, 86, y_sign + 14)
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*C_TEXT)
    pdf.set_xy(20, y_sign + 15)
    pdf.cell(66, 4, _t(responsable or 'Administrador de Operaciones'), align='C')
    pdf.set_font('Helvetica', '', 6.5)
    pdf.set_text_color(*C_MUTED_TXT)
    pdf.set_xy(20, y_sign + 19)
    pdf.cell(66, 4, 'Elaboro y Reviso', align='C')

    # Firma 2: Aprobación
    pdf.line(124, y_sign + 14, 190, y_sign + 14)
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*C_TEXT)
    pdf.set_xy(124, y_sign + 15)
    pdf.cell(66, 4, 'FLOTA URABA S.A.', align='C')
    pdf.set_font('Helvetica', '', 6.5)
    pdf.set_text_color(*C_MUTED_TXT)
    pdf.set_xy(124, y_sign + 19)
    pdf.cell(66, 4, 'Aprobacion y Liquidacion', align='C')

    _draw_footer(page_num)
    return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────────────────
# REPORTE 6: LAVADOS DIARIOS — Planilla FT-OP-15
# ─────────────────────────────────────────────────────────────────────────────

class DiarioReport(FPDF):
    """Reporte diario con encabezado exacto de la Planilla de Lavado FT-OP-15."""

    # Anchos de columna (orientación Landscape A4 = 297mm, márgenes 8mm c/u → 281mm útiles)
    COL_W = [22, 17, 26, 20, 20, 17, 20, 17, 11, 11, 11, 50, 30]
    COL_H = [
        'TIPO DE\nVEHICULO', 'PLACA', 'MUNICIPIO',
        'HORA\nLLEGADA\nLAVADERO', 'HORA\nINGRESO\nLAVADO',
        'TIEMPO\nESPERA', 'HORA\nSALIDA\nLAVADO',
        'TIEMPO\nLAVADO', 'ENJUA\nGUE', 'SENCI\nLLO',
        'GENE\nRAL', 'NOMBRE LAVADOR', 'FIRMA CONDUCTOR'
    ]

    def __init__(self, fecha_reporte: str):
        super().__init__(orientation='L', unit='mm', format='A4')
        self.fecha_rep = _t(fecha_reporte)
        self.set_margins(8, 8, 8)
        self.set_auto_page_break(auto=True, margin=14)

    def header(self):
        self.set_draw_color(*C_BLACK)
        self.set_line_width(0.4)
        y0 = 8

        # ── Fila 1: Logo | Título | Código/Versión ──────────────────────────
        # Logo box
        self.rect(8, y0, 38, 18)
        self.set_font('Helvetica', 'B', 13)
        self.set_text_color(*C_BLACK)
        self.set_xy(8, y0 + 4)
        self.cell(38, 10, 'futuraseo', align='C')

        # Title box (expanded to fill the remaining width: 281 - 38 = 243)
        self.rect(46, y0, 243, 18)
        self.set_font('Helvetica', 'B', 10)
        self.set_xy(46, y0 + 2)
        self.cell(243, 7, 'CONTROL TIEMPO LAVADO VEHICULAR', align='C')
        self.set_font('Helvetica', 'B', 8)
        self.set_xy(46, y0 + 9)
        self.cell(243, 6, 'OPERACIONES', align='C')

        # ── Fila 2: Fecha | Zona ────────────────────────────────────────────
        y1 = y0 + 18
        self.rect(8, y1, 281, 7)
        self.set_font('Helvetica', 'B', 8)
        self.set_xy(10, y1 + 1.5)
        self.cell(90, 4, f'FECHA: {self.fecha_rep}', align='L')
        self.set_xy(100, y1 + 1.5)
        self.cell(130, 4, 'ZONA: URABA', align='L')
        self.set_xy(230, y1 + 1.5)
        self.cell(57, 4, f'Pag. {self.page_no()}', align='C')

        # ── Fila 3: Encabezados de columnas ────────────────────────────────
        y2 = y1 + 7
        self.set_font('Helvetica', 'B', 6.5)
        self.set_fill_color(220, 220, 220)
        x = 8
        for w, txt in zip(self.COL_W, self.COL_H):
            self.rect(x, y2, w, 12, 'FD')
            lines = txt.split('\n')
            line_h = 3.5
            total_h = len(lines) * line_h
            start_y = y2 + (12 - total_h) / 2
            for li, line in enumerate(lines):
                self.set_xy(x, start_y + li * line_h)
                self.cell(w, line_h, _t(line), align='C')
            x += w

        self.set_y(y2 + 12)

    def footer(self):
        self.set_y(-10)
        self.set_font('Helvetica', '', 6.5)
        self.set_text_color(*C_MUTED)
        self.cell(0, 5, _t(f'Flota Uraba  -  Sistema de Gestion de Lavados  |  Planilla Diaria FT-OP-15  |  Pag. {self.page_no()}'), align='C')


def _reporte_lavados_diarios(historial: list, vehiculos: list, start_date: str, end_date: str, responsable: str) -> bytes:
    """Genera la planilla diaria FT-OP-15 para la fecha o rango indicado."""

    # Formatear fecha para mostrar: YYYY-MM-DD → DD-MM-YYYY
    def format_fecha(f):
        try:
            parts = str(f).split('-')
            return f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else f
        except Exception:
            return f
            
    if start_date == end_date:
        fecha_str = format_fecha(start_date)
    else:
        fecha_str = f"{format_fecha(start_date)} al {format_fecha(end_date)}"

    pdf = DiarioReport(fecha_reporte=fecha_str)
    pdf.add_page()

    # Filtrar lavados del rango y ordenarlos por fecha y hora
    records = [h for h in historial if start_date <= h.get('fecha', '') <= end_date]
    records.sort(key=lambda x: (x.get('fecha', ''), x.get('hora_llegada', '')))

    # Mapa placa → tipo de vehículo
    placa_to_tipo = {v['placa']: v.get('tipo', 'N/D') for v in vehiculos}

    pdf.set_draw_color(*C_BLACK)
    pdf.set_line_width(0.25)
    pdf.set_text_color(*C_DARK)

    ROW_H = 7.0

    for r in records:
        if pdf.get_y() + ROW_H > 195:
            pdf.add_page()

        placa    = _t(r.get('placa', ''))
        tipo_veh = _t(placa_to_tipo.get(placa, 'N/D'))
        mun      = _t(r.get('municipio', r.get('mun', '')))
        llegada  = _t(r.get('hora_llegada', ''))
        inicio   = _t(r.get('hora_inicio', r.get('hora', '')))
        fin      = _t(r.get('hora_fin', ''))

        # Tiempos (minutos → "Xh YYm" o solo minutos)
        def fmt_min(val):
            if val is None or val == '': return ''
            try:
                m = int(val)
                return f'{m}m' if m < 60 else f'{m//60}h {m%60:02d}m'
            except Exception:
                return _t(str(val))

        t_espera = fmt_min(r.get('tiempo_espera'))
        t_lavado = fmt_min(r.get('tiempo_lavado'))

        tipo_lav = (r.get('tipo_lavado') or 'General').upper()
        enj = 'X' if 'ENJUAGUE' in tipo_lav else ''
        sen = 'X' if 'SENCILLO' in tipo_lav else ''
        gen = 'X' if 'GENERAL'  in tipo_lav else ''

        lavs = r.get('lavadores') or []
        if not lavs:
            lav_raw = r.get('lavador', '')
            if lav_raw: lavs = [lav_raw]
        lav_n = _t(', '.join(lavs))

        row_data = [tipo_veh, placa, mun, llegada, inicio, t_espera, fin, t_lavado, enj, sen, gen, lav_n, '']

        y = pdf.get_y()
        x = 8
        for i, (cell_text, w) in enumerate(zip(row_data, DiarioReport.COL_W)):
            pdf.rect(x, y, w, ROW_H)
            pdf.set_font('Helvetica', 'B' if i in (0, 1) else '', 7.5)
            pdf.set_xy(x + 1, y + (ROW_H - 4) / 2)
            pdf.cell(w - 2, 4, str(cell_text)[:30], align='C' if i not in (2, 11) else 'L')
            x += w
        pdf.set_y(y + ROW_H)

    # Rellenar filas vacías hasta completar la página (mínimo 5 filas vacías)
    filled = len(records)
    min_rows = max(5, filled + 3)
    while filled < min_rows and pdf.get_y() + ROW_H < 193:
        y = pdf.get_y()
        x = 8
        for w in DiarioReport.COL_W:
            pdf.rect(x, y, w, ROW_H)
            x += w
        pdf.set_y(y + ROW_H)
        filled += 1

    # ── Fila de Observaciones + Firma ──────────────────────────────────────
    y_obs = pdf.get_y()
    if y_obs + 10 > 197:
        pdf.add_page()
        y_obs = pdf.get_y()

    pdf.set_draw_color(*C_BLACK)
    pdf.set_line_width(0.4)
    pdf.rect(8, y_obs, 281, 10)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_xy(10, y_obs + 3)
    pdf.cell(80, 4, 'OBSERVACIONES:', align='L')
    pdf.set_xy(160, y_obs + 3)
    pdf.cell(120, 4, f'FIRMA COORDINADOR DE ZONA: ___________________________', align='L')

    return bytes(pdf.output())
