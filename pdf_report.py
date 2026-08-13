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
    # ─── 1. Filtrar por fechas y que tengan lavador ───────────────────────
    historial = [h for h in historial_raw if (
        (not desde or h.get('fecha', '') >= desde) and
        (not hasta or h.get('fecha', '') <= hasta) and
        h.get('lavador', '').strip()
    )]
    historial.sort(key=lambda x: x.get('fecha', ''))

    # ─── 2. Agrupar por lavador ──────────────────────────────────────────
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

    # ─── 3. Paleta premium ───────────────────────────────────────────────
    C_NAVY  = (8,  14, 44)       # Azul marino profundo
    C_AZURE = (37, 99, 235)      # Azul vivo
    C_TEAL  = (20, 184, 166)     # Verde-azul (Sencillo)
    C_AMBER = (217, 119, 6)      # Ámbar (Enjuague)
    C_SLATE = (248, 250, 252)    # Fondo filas pares
    C_EGR   = (22,  163, 74)     # Verde éxito (totales)

    # ─── 4. Datos globales ───────────────────────────────────────────────
    total_pago_empresa  = sum(float(tarifas.get(h.get('tipo_lavado', 'General'), 0)) for h in historial)
    total_lavados_per   = len(historial)

    if desde and hasta:
        periodo_str = _t(f'Del {desde} al {hasta}')
    elif desde:
        periodo_str = _t(f'Desde el {desde}')
    elif hasta:
        periodo_str = _t(f'Hasta el {hasta}')
    else:
        periodo_str = 'Historico Completo'

    # ─── 5. Inicializar PDF portrait A4 ─────────────────────────────────
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    page_num = 0

    # Helper: pie de página
    def _footer(pn):
        pdf.set_xy(0, 282)
        pdf.set_draw_color(*C_RULE)
        pdf.set_line_width(0.2)
        pdf.line(20, 282, 190, 282)
        pdf.set_font('Helvetica', '', 6.5)
        pdf.set_text_color(*C_MUTED)
        pdf.set_x(20)
        pdf.cell(170, 5,
            _t(f'FLOTA URABA  |  Liquidacion de Nomina  |  {periodo_str}  |  CONFIDENCIAL  |  Pag. {pn}'),
            align='C')

    # Helper: verificar espacio
    def _need_page(needed_h, limit=278):
        return pdf.get_y() + needed_h > limit

    # Helper: encabezado de tabla (servicios)
    def _svc_header(y, cols_w, hdrs_t):
        pdf.set_fill_color(*C_NAVY)
        pdf.rect(20, y, sum(cols_w), 7.5, 'F')
        x = 20
        for ht, cw in zip(hdrs_t, cols_w):
            pdf.set_font('Helvetica', 'B', 6.5)
            pdf.set_text_color(*C_WHITE)
            pdf.set_xy(x + 2, y + 1.8)
            pdf.cell(cw - 4, 4, _t(ht).upper(), align='L')
            x += cw
        pdf.set_y(y + 7.5)

    # ═══════════════════════════════════════════════════════════════════════
    # PORTADA
    # ═══════════════════════════════════════════════════════════════════════
    pdf.add_page()
    page_num += 1

    # Fondo completo blanco
    pdf.set_fill_color(*C_WHITE)
    pdf.rect(0, 0, 210, 297, 'F')

    # Banda navy superior
    pdf.set_fill_color(*C_NAVY)
    pdf.rect(0, 0, 210, 92, 'F')
    pdf.set_fill_color(*C_AZURE)
    pdf.rect(0, 90, 210, 2.5, 'F')

    # Logo cuadrado con iniciales "FU"
    pdf.set_fill_color(*C_AZURE)
    pdf.rect(20, 14, 26, 26, 'F')
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(*C_WHITE)
    pdf.set_xy(20, 19)
    pdf.cell(26, 14, 'FU', align='C')

    # Nombre empresa
    pdf.set_font('Helvetica', 'B', 26)
    pdf.set_text_color(*C_WHITE)
    pdf.set_xy(52, 16)
    pdf.cell(0, 13, 'FLOTA URABA', align='L')

    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(147, 197, 253)
    pdf.set_xy(53, 31)
    pdf.cell(0, 5, 'Gestion de Lavados Vehiculares  |  Zona Uraba, Colombia', align='L')

    # Separador interno
    pdf.set_draw_color(50, 70, 130)
    pdf.set_line_width(0.2)
    pdf.line(20, 43, 190, 43)

    # Título principal
    pdf.set_font('Helvetica', 'B', 30)
    pdf.set_text_color(*C_WHITE)
    pdf.set_xy(20, 49)
    pdf.cell(0, 16, 'LIQUIDACION DE NOMINA', align='L')

    # Período
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(147, 197, 253)
    pdf.set_xy(20, 67)
    pdf.cell(0, 6, periodo_str, align='L')

    # Fecha generación
    fecha_gen = _t(datetime.datetime.now().strftime('%d de %B de %Y  -  %H:%M'))
    pdf.set_font('Helvetica', '', 8.5)
    pdf.set_text_color(148, 163, 184)
    pdf.set_xy(20, 75)
    pdf.cell(0, 5, f'Generado: {fecha_gen}', align='L')

    # Badge CONFIDENCIAL
    pdf.set_fill_color(25, 40, 90)
    pdf.rect(20, 82, 44, 7, 'F')
    pdf.set_font('Helvetica', 'B', 6.5)
    pdf.set_text_color(*C_AZURE)
    pdf.set_xy(20, 83.5)
    pdf.cell(44, 4, 'DOCUMENTO CONFIDENCIAL', align='C')

    # ── KPI boxes bajo el header ──────────────────────────────────────────
    kbox_y = 102
    kbox_data = [
        ('Especialistas',          str(len(por_lavador)),         C_AZURE),
        ('Servicios Realizados',   str(total_lavados_per),        C_DARK),
        ('Total a Liquidar',       f'${total_pago_empresa:,.0f}', C_EGR),
    ]
    kbw = 55; kg = 8
    kbx0 = (210 - (kbw * 3 + kg * 2)) / 2
    for i, (lbl, val, col) in enumerate(kbox_data):
        kx = kbx0 + i * (kbw + kg)
        # Sombra suave
        pdf.set_fill_color(210, 220, 235)
        pdf.rect(kx + 1.5, kbox_y + 1.5, kbw, 32, 'F')
        # Caja principal
        pdf.set_fill_color(*C_WHITE)
        pdf.set_draw_color(*C_RULE)
        pdf.set_line_width(0.3)
        pdf.rect(kx, kbox_y, kbw, 32, 'FD')
        # Barra superior de color
        pdf.set_fill_color(*col)
        pdf.rect(kx, kbox_y, kbw, 3, 'F')
        # Valor
        pdf.set_font('Helvetica', 'B', 17)
        pdf.set_text_color(*col)
        pdf.set_xy(kx, kbox_y + 7)
        pdf.cell(kbw, 10, _t(val), align='C')
        # Etiqueta
        pdf.set_font('Helvetica', 'B', 5.8)
        pdf.set_text_color(*C_MUTED)
        pdf.set_xy(kx, kbox_y + 22)
        pdf.cell(kbw, 5, _t(lbl).upper(), align='C')

    # ── Línea divisora ────────────────────────────────────────────────────
    div_y = 146
    pdf.set_draw_color(*C_RULE)
    pdf.set_line_width(0.4)
    pdf.line(20, div_y, 190, div_y)

    # ── Índice de lavadores ───────────────────────────────────────────────
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_text_color(*C_MUTED)
    pdf.set_xy(20, div_y + 7)
    pdf.cell(0, 5, _t('CONTENIDO - ESPECIALISTAS EN ESTE REPORTE'), align='L')

    y_idx = div_y + 17
    for i, lav_name in enumerate(sorted(por_lavador.keys()), 1):
        if y_idx > 244:
            break
        lavs_i = por_lavador[lav_name]
        pago_i = sum(float(tarifas.get(l.get('tipo_lavado', 'General'), 0)) for l in lavs_i)
        if i % 2 == 0:
            pdf.set_fill_color(*C_SLATE)
            pdf.rect(20, y_idx - 1, 170, 8.5, 'F')
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(*C_BLACK)
        pdf.set_xy(20, y_idx)
        pdf.cell(8, 6, f'{i}.', align='R')
        pdf.set_xy(30, y_idx)
        pdf.cell(85, 6, _t(lav_name.title()), align='L')
        pdf.set_font('Helvetica', '', 7.5)
        pdf.set_text_color(*C_MUTED)
        pdf.set_xy(115, y_idx)
        pdf.cell(40, 6, f'{len(lavs_i)} servicio(s)', align='L')
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(*C_EGR)
        pdf.set_xy(155, y_idx)
        pdf.cell(35, 6, f'${pago_i:,.0f}', align='R')
        y_idx += 8.5

    # ── Firma de portada ──────────────────────────────────────────────────
    pdf.set_draw_color(*C_RULE)
    pdf.set_line_width(0.3)
    pdf.line(20, 262, 90, 262)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*C_BLACK)
    pdf.set_xy(20, 264)
    pdf.cell(70, 4, _t(responsable or 'Administrador'), align='C')
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(*C_MUTED)
    pdf.set_xy(20, 269)
    pdf.cell(70, 4, 'Firma del Responsable', align='C')

    _footer(page_num)

    # ═══════════════════════════════════════════════════════════════════════
    # PÁGINAS INDIVIDUALES POR LAVADOR
    # ═══════════════════════════════════════════════════════════════════════
    SVC_COLS = [26, 22, 24, 20, 20, 24, 27, 27]
    SVC_HDRS = ['Fecha', 'Placa', 'Tipo', 'H.Inicio', 'H.Fin', 'Duracion', 'Tarifa', 'Subtotal']

    for lav_name in sorted(por_lavador.keys()):
        lavados = sorted(por_lavador[lav_name], key=lambda x: x.get('fecha', ''))

        pdf.add_page()
        page_num += 1
        pdf.set_fill_color(*C_WHITE)
        pdf.rect(0, 0, 210, 297, 'F')

        # Header navy
        pdf.set_fill_color(*C_NAVY)
        pdf.rect(0, 0, 210, 50, 'F')
        pdf.set_fill_color(*C_AZURE)
        pdf.rect(0, 48.5, 210, 1.5, 'F')

        # Avatar cuadrado con iniciales
        words = lav_name.split()
        initials = ''.join(w[0] for w in words[:2])
        pdf.set_fill_color(*C_AZURE)
        pdf.rect(18, 10, 30, 30, 'F')
        pdf.set_font('Helvetica', 'B', 15)
        pdf.set_text_color(*C_WHITE)
        pdf.set_xy(18, 17)
        pdf.cell(30, 15, _t(initials), align='C')

        # Nombre y cargo
        pdf.set_font('Helvetica', 'B', 20)
        pdf.set_text_color(*C_WHITE)
        pdf.set_xy(54, 13)
        pdf.cell(100, 10, _t(lav_name.title()), align='L')
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(147, 197, 253)
        pdf.set_xy(55, 25)
        pdf.cell(100, 5, 'Especialista en Lavado de Vehiculos', align='L')

        # Info derecha del header
        pdf.set_font('Helvetica', '', 7.5)
        pdf.set_text_color(148, 163, 184)
        pdf.set_xy(110, 14)
        pdf.cell(80, 5, periodo_str, align='R')
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(*C_AZURE)
        pdf.set_xy(110, 21)
        total_lavados_frac = sum((1.0 / (len(l.get('lavadores', [])) or 1)) for l in lavados)
        display_lavados = f"{total_lavados_frac:g}"
        pdf.cell(80, 5, _t(f'{display_lavados} servicios  |  periodo activo'), align='R')

        # ── Mini KPIs del lavador ─────────────────────────────────────────
        tc = {'General': 0, 'Sencillo': 0, 'Enjuague': 0}
        t_mins = 0; t_pago = 0
        for l in lavados:
            tipo = l.get('tipo_lavado', 'General')
            n_lavadores = len(l.get('lavadores', []))
            if n_lavadores == 0:
                n_lavadores = 1
                
            tc[tipo] = tc.get(tipo, 0) + (1.0 / n_lavadores)
            t_pago += float(tarifas.get(tipo, 0)) / n_lavadores
            t_mins += _calc_mins(l.get('hora_inicio', ''), l.get('hora_fin', '')) / n_lavadores

        mkpi = [
            ('Generales',  f"{tc['General']:g}",  C_AZURE),
            ('Sencillos',  f"{tc['Sencillo']:g}", C_TEAL),
            ('Enjuagues',  f"{tc['Enjuague']:g}", C_AMBER),
            ('Hrs Trabajadas', f'{int(t_mins)//60}h {int(t_mins)%60:02d}m', C_MUTED),
        ]
        mk_w = 37; mk_h = 22; mk_gap = 5
        mk_y = 57
        for i, (lbl, val, col) in enumerate(mkpi):
            mx = 20 + i * (mk_w + mk_gap)
            pdf.set_fill_color(*C_LIGHT)
            pdf.set_draw_color(*C_RULE)
            pdf.set_line_width(0.2)
            pdf.rect(mx, mk_y, mk_w, mk_h, 'FD')
            pdf.set_fill_color(*col)
            pdf.rect(mx, mk_y, mk_w, 1.5, 'F')
            pdf.set_font('Helvetica', 'B', 14)
            pdf.set_text_color(*col)
            pdf.set_xy(mx, mk_y + 3)
            pdf.cell(mk_w, 9, _t(val), align='C')
            pdf.set_font('Helvetica', 'B', 5.5)
            pdf.set_text_color(*C_MUTED)
            pdf.set_xy(mx, mk_y + 14)
            pdf.cell(mk_w, 4, _t(lbl).upper(), align='C')

        pdf.set_y(mk_y + mk_h + 9)

        # ── Tabla de servicios ────────────────────────────────────────────
        pdf.set_font('Helvetica', 'B', 7)
        pdf.set_text_color(*C_MUTED)
        pdf.set_x(20)
        pdf.cell(0, 4, 'DETALLE DE SERVICIOS REALIZADOS EN EL PERIODO', align='L')
        pdf.ln(5)

        _svc_header(pdf.get_y(), SVC_COLS, SVC_HDRS)

        for idx, l in enumerate(lavados):
            if _need_page(8):
                _footer(page_num)
                pdf.add_page()
                page_num += 1
                pdf.set_fill_color(*C_WHITE)
                pdf.rect(0, 0, 210, 297, 'F')
                # Mini-header de continuación
                pdf.set_fill_color(*C_NAVY)
                pdf.rect(0, 0, 210, 16, 'F')
                pdf.set_font('Helvetica', 'B', 9)
                pdf.set_text_color(*C_WHITE)
                pdf.set_xy(20, 5)
                pdf.cell(0, 7, _t(f'{lav_name.title()}  —  Continuacion'), align='L')
                pdf.set_y(22)
                _svc_header(pdf.get_y(), SVC_COLS, SVC_HDRS)

            tipo = l.get('tipo_lavado', 'General')
            tarifa_u = float(tarifas.get(tipo, 0))
            mins_l = _calc_mins(l.get('hora_inicio', ''), l.get('hora_fin', ''))
            dur_str = f'{mins_l // 60}h {mins_l % 60:02d}m' if mins_l > 0 else '--'
            tipo_col = {'General': C_AZURE, 'Sencillo': C_TEAL, 'Enjuague': C_AMBER}.get(tipo, C_MUTED)

            bg = C_SLATE if idx % 2 else C_WHITE
            ry = pdf.get_y()
            pdf.set_fill_color(*bg)
            pdf.set_draw_color(*C_RULE)
            pdf.set_line_width(0.1)
            pdf.rect(20, ry, sum(SVC_COLS), 7, 'FD')

            n_lavadores = len(l.get('lavadores', []))
            if n_lavadores == 0:
                n_lavadores = 1
            
            cells = [
                l.get('fecha', '-'), l.get('placa', '-'), tipo,
                l.get('hora_inicio', '-'), l.get('hora_fin', '-'),
                dur_str, f'${tarifa_u:,.0f}', f'${tarifa_u / n_lavadores:,.0f}',
            ]
            x = 20
            for ci, (cell, cw) in enumerate(zip(cells, SVC_COLS)):
                is_last = ci == len(cells) - 1
                is_tipo = ci == 2
                fnt   = 'B' if (ci == 0 or is_last or is_tipo) else ''
                color = (C_EGR if is_last else (tipo_col if is_tipo else C_DARK))
                pdf.set_font('Helvetica', fnt, 7)
                pdf.set_text_color(*color)
                pdf.set_xy(x + 2, ry + 1.8)
                pdf.cell(cw - 4, 4, _t(str(cell)), align='L')
                x += cw
            pdf.set_y(ry + 7)

        # ── Caja de total ─────────────────────────────────────────────────
        if _need_page(44):
            _footer(page_num)
            pdf.add_page()
            page_num += 1
            pdf.set_fill_color(*C_WHITE)
            pdf.rect(0, 0, 210, 297, 'F')
            pdf.set_y(20)

        pdf.ln(9)
        tb_y = pdf.get_y(); tb_x = 100; tb_w = 90; tb_h = 38

        # Sombra
        pdf.set_fill_color(200, 230, 210)
        pdf.rect(tb_x + 1.5, tb_y + 1.5, tb_w, tb_h, 'F')
        # Caja
        pdf.set_fill_color(240, 253, 244)
        pdf.set_draw_color(*C_EGR)
        pdf.set_line_width(0.6)
        pdf.rect(tb_x, tb_y, tb_w, tb_h, 'FD')
        # Barra superior verde
        pdf.set_fill_color(*C_EGR)
        pdf.rect(tb_x, tb_y, tb_w, 2.5, 'F')
        # Etiqueta
        pdf.set_font('Helvetica', 'B', 6.5)
        pdf.set_text_color(*C_MUTED)
        pdf.set_xy(tb_x, tb_y + 7)
        pdf.cell(tb_w, 4, 'TOTAL A PAGAR EN EL PERIODO', align='C')
        # Valor
        pdf.set_font('Helvetica', 'B', 24)
        pdf.set_text_color(*C_EGR)
        pdf.set_xy(tb_x, tb_y + 13)
        pdf.cell(tb_w, 14, f'${t_pago:,.0f}', align='C')
        # Nota inferior
        pdf.set_font('Helvetica', '', 6.5)
        pdf.set_text_color(*C_MUTED)
        pdf.set_xy(tb_x, tb_y + 30)
        pdf.cell(tb_w, 4,
            _t(f'{display_lavados} servicio(s)  |  {int(t_mins)//60}h {int(t_mins)%60:02d}m trabajados'),
            align='C')

        _footer(page_num)

    # ═══════════════════════════════════════════════════════════════════════
    # PÁGINA FINAL: RESUMEN EJECUTIVO
    # ═══════════════════════════════════════════════════════════════════════
    pdf.add_page()
    page_num += 1
    pdf.set_fill_color(*C_WHITE)
    pdf.rect(0, 0, 210, 297, 'F')

    # Header
    pdf.set_fill_color(*C_NAVY)
    pdf.rect(0, 0, 210, 36, 'F')
    pdf.set_fill_color(*C_AZURE)
    pdf.rect(0, 34.5, 210, 1.5, 'F')

    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(*C_WHITE)
    pdf.set_xy(20, 10)
    pdf.cell(0, 9, 'RESUMEN EJECUTIVO DE NOMINA', align='L')

    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(147, 197, 253)
    pdf.set_xy(20, 22)
    fecha_gen2 = _t(datetime.datetime.now().strftime('%d/%m/%Y %H:%M'))
    pdf.cell(0, 5, _t(f'Flota Uraba  |  {periodo_str}  |  Generado: {fecha_gen2}'), align='L')

    pdf.set_y(43)

    # Tabla resumen
    SR_COLS = [55, 24, 24, 24, 29, 34]
    SR_HDRS = ['Especialista', 'Generales', 'Sencillos', 'Enjuagues', 'Hrs Trab.', 'Total ($)']

    sr_y = pdf.get_y()
    pdf.set_fill_color(*C_DARK)
    pdf.rect(20, sr_y, sum(SR_COLS), 8, 'F')
    x = 20
    for ht, hw in zip(SR_HDRS, SR_COLS):
        pdf.set_font('Helvetica', 'B', 7)
        pdf.set_text_color(*C_WHITE)
        pdf.set_xy(x + 2, sr_y + 2)
        pdf.cell(hw - 4, 4.5, _t(ht).upper(), align='L')
        x += hw
    pdf.set_y(sr_y + 8)

    grand_total = 0; grand_mins = 0
    for idx, lav_name in enumerate(sorted(por_lavador.keys())):
        lavs = por_lavador[lav_name]
        tc2 = {'General': 0, 'Sencillo': 0, 'Enjuague': 0}
        pl = 0; ml = 0
        for l in lavs:
            tipo = l.get('tipo_lavado', 'General')
            n_lavadores = len(l.get('lavadores', []))
            if n_lavadores == 0:
                n_lavadores = 1
                
            tc2[tipo] = tc2.get(tipo, 0) + (1.0 / n_lavadores)
            pl += float(tarifas.get(tipo, 0)) / n_lavadores
            ml += _calc_mins(l.get('hora_inicio', ''), l.get('hora_fin', '')) / n_lavadores
        grand_total += pl; grand_mins += ml

        bg = C_SLATE if idx % 2 else C_WHITE
        ry = pdf.get_y()
        pdf.set_fill_color(*bg)
        pdf.set_draw_color(*C_RULE)
        pdf.set_line_width(0.1)
        pdf.rect(20, ry, sum(SR_COLS), 8.5, 'FD')
        row = [
            lav_name.title(),
            f"{tc2['General']:g}", f"{tc2['Sencillo']:g}", f"{tc2['Enjuague']:g}",
            f'{int(ml)//60}h {int(ml)%60:02d}m', f'${pl:,.0f}',
        ]
        x = 20
        for ci, (cell, cw) in enumerate(zip(row, SR_COLS)):
            is_last = ci == len(row) - 1
            fnt   = 'B' if (ci == 0 or is_last) else ''
            color = C_EGR if is_last else (C_BLACK if ci == 0 else C_DARK)
            pdf.set_font('Helvetica', fnt, 8)
            pdf.set_text_color(*color)
            pdf.set_xy(x + 2, ry + 2.2)
            pdf.cell(cw - 4, 5, _t(str(cell)), align='L')
            x += cw
        pdf.set_y(ry + 8.5)

    # Fila de gran total
    gt_y = pdf.get_y()
    pdf.set_fill_color(*C_NAVY)
    pdf.rect(20, gt_y, sum(SR_COLS), 12, 'F')
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(*C_WHITE)
    pdf.set_xy(22, gt_y + 3)
    pdf.cell(sum(SR_COLS) - SR_COLS[-1] - 4, 7, 'TOTAL EMPRESA', align='L')
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(134, 239, 172)  # green-300
    pdf.set_xy(20 + sum(SR_COLS[:-1]), gt_y + 2)
    pdf.cell(SR_COLS[-1], 9, f'${grand_total:,.0f}', align='L')

    pdf.set_y(gt_y + 20)
    pdf.set_draw_color(*C_RULE)
    pdf.set_line_width(0.3)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(10)

    # Notas legales
    pdf.set_font('Helvetica', 'B', 7)
    pdf.set_text_color(*C_MUTED)
    pdf.set_x(20)
    pdf.cell(0, 4, 'NOTAS Y CONDICIONES', align='L')
    pdf.ln(7)
    notas = [
        '* Los valores corresponden a las tarifas configuradas en el sistema al momento de la generacion de este reporte.',
        '* Documento de caracter confidencial para uso exclusivo interno de Flota Uraba.',
        '* Los tiempos trabajados se calculan en base a las horas de inicio y fin registradas en cada servicio.',
        '* Cualquier discrepancia debe reportarse al administrador antes del cierre del periodo de pago.',
    ]
    for nota in notas:
        pdf.set_font('Helvetica', '', 7.5)
        pdf.set_text_color(*C_DARK)
        pdf.set_x(20)
        pdf.multi_cell(170, 5, _t(nota), align='L')
        pdf.ln(1)

    # Sección de firmas
    pdf.set_y(245)
    pdf.set_draw_color(*C_DARK)
    pdf.set_line_width(0.3)
    pdf.line(20, 258, 92, 258)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*C_BLACK)
    pdf.set_xy(20, 260)
    pdf.cell(72, 4, _t(responsable or 'Administrador del Sistema'), align='C')
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(*C_MUTED)
    pdf.set_xy(20, 265)
    pdf.cell(72, 4, 'Elaboro y Reviso', align='C')

    pdf.line(128, 258, 190, 258)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*C_BLACK)
    pdf.set_xy(128, 260)
    pdf.cell(62, 4, 'FLOTA URABA', align='C')
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(*C_MUTED)
    pdf.set_xy(128, 265)
    pdf.cell(62, 4, 'Empresa Autorizada', align='C')

    _footer(page_num)
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
