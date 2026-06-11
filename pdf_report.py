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

# ── Paleta de colores (monocromática + un acento) ──────────────────────────────
C_BLACK  = (15,  23,  42)   # Título, texto fuerte
C_DARK   = (51,  65,  85)   # Texto secundario
C_MUTED  = (100, 116, 139)  # Texto apagado, notas
C_LIGHT  = (241, 245, 249)  # Fondo alternado zebra
C_WHITE  = (255, 255, 255)
C_RULE   = (203, 213, 225)  # Líneas divisoras
C_ACCENT = (14,  165, 233)  # Acento azul (solo para valores importantes)
C_RED    = (220, 38,  38)   # Solo para alertas críticas
C_GREEN  = (22,  163, 74)   # Solo para cumplimiento OK

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
    """Reporte limpio con cabecera simple y pie de página discreto."""

    def __init__(self, titulo: str, subtitulo: str, responsable: str = ''):
        super().__init__(orientation='L', unit='mm', format='A4')
        self.titulo      = _t(titulo)
        self.subtitulo   = _t(subtitulo)
        self.responsable = _t(responsable)
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(auto=True, margin=16)

    def header(self):
        # Línea superior de acento
        self.set_fill_color(*C_ACCENT)
        self.rect(0, 0, 297, 3, 'F')

        self.set_xy(18, 8)
        self.set_font('Helvetica', 'B', 15)
        self.set_text_color(*C_BLACK)
        self.cell(0, 7, self.titulo, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_xy(18, 16)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(*C_MUTED)
        fecha_str = datetime.datetime.now().strftime('%d/%m/%Y  %H:%M')
        self.cell(0, 5, f'{self.subtitulo}   |   Generado: {fecha_str}', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Línea divisora
        self.set_draw_color(*C_RULE)
        self.set_line_width(0.3)
        self.line(18, 23, 279, 23)
        self.set_y(28)

    def footer(self):
        self.set_y(-12)
        self.set_draw_color(*C_RULE)
        self.set_line_width(0.3)
        self.line(18, self.get_y(), 279, self.get_y())
        self.set_font('Helvetica', '', 7)
        self.set_text_color(*C_MUTED)
        resp = f'{self.responsable}   |   ' if self.responsable else ''
        self.set_x(18)
        footer_text = f'{resp}Flota Uraba  -  Sistema de Gestion de Lavados   |   Pag. {self.page_no()}'
        self.cell(0, 6, _t(footer_text), align='C')


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
    else:
        return _reporte_diagnostico(stats, vehiculos, historial, start_date, responsable)


# ─────────────────────────────────────────────────────────────────────────────
# REPORTE 1: DIAGNÓSTICO GENERAL
# ─────────────────────────────────────────────────────────────────────────────
def _reporte_diagnostico(stats, vehiculos, historial, fecha_corte, responsable):
    pdf = CleanReport(
        titulo='Diagnostico General de Flota',
        subtitulo=f'Corte al {fecha_corte}',
        responsable=responsable
    )
    pdf.set_compression(True)
    pdf.add_page()

    # KPIs en una fila compacta
    kpis = [
        ('Vehiculos totales',    str(stats.get('total_veh', 0)),     C_ACCENT),
        ('Lavados realizados',   str(stats.get('total_gen', 0)),     C_GREEN),
        ('Meta esperada',        str(stats.get('meta', 0)),          C_DARK),
        ('Deficit acumulado',    str(stats.get('deficit', 0)),       C_RED),
        ('Sin ningun lavado',    str(stats.get('sin_gen', 0)),       C_RED),
        ('Cumplimiento',         f"{stats.get('pct_cum', 0)}%",      C_GREEN if float(stats.get('pct_cum', 0)) >= 80 else C_RED),
    ]
    _draw_kpi_strip(pdf, kpis)
    pdf.ln(6)

    # Tabla por municipio
    _section(pdf, 'Cumplimiento por Municipio')
    n_meses = stats.get('n_meses', 3)
    grupos = defaultdict(lambda: {'veh': 0, 'lav': 0})
    for v in vehiculos:
        mun = v.get('mun', 'N/D')
        if mun and mun.upper() not in ('N/D', '0', ''):
            grupos[mun]['veh'] += 1
            grupos[mun]['lav'] += v.get('lavGen', 0)

    cols = [80, 30, 30, 30, 50]
    hdrs = ['Municipio', 'Vehiculos', 'Lavados', 'Meta', 'Cumplimiento']
    _table_header(pdf, hdrs, cols)
    for idx, (mun, g) in enumerate(sorted(grupos.items())):
        meta = g['veh'] * n_meses
        pct  = (g['lav'] / meta * 100) if meta > 0 else 0
        color_pct = C_GREEN if pct >= 80 else C_RED
        bg = C_LIGHT if idx % 2 else C_WHITE
        _table_row(pdf, [_t(mun), str(g['veh']), str(g['lav']), str(meta), f'{pct:.1f}%'],
                   cols, bg=bg, last_color=color_pct)
    pdf.ln(8)

    # Vehículos sin lavado
    pendientes = sorted([v for v in vehiculos if v.get('lavGen', 0) == 0],
                        key=lambda x: (x.get('mun', ''), x.get('placa', '')))
    _section(pdf, f'Vehiculos sin Lavado General ({len(pendientes)} unidades)')
    if not pendientes:
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(*C_GREEN)
        pdf.cell(0, 6, 'Todos los vehiculos tienen al menos un lavado registrado.', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        cols2 = [35, 55, 55, 40, 35]
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
            ], cols2, bg=bg, first_color=C_RED)

    return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────────────────
# REPORTE 2: PROGRAMACIÓN
# ─────────────────────────────────────────────────────────────────────────────
def _reporte_programacion(programacion, vehiculos, start_date, end_date, responsable):
    pdf = CleanReport(
        titulo='Propuesta de Programacion de Lavados',
        subtitulo=f'Del {start_date} al {end_date}',
        responsable=responsable
    )
    pdf.set_compression(True)
    pdf.add_page()

    asignados   = [v for v in programacion if v.get('diaAsignado')]
    sin_asignar = [v for v in programacion if not v.get('diaAsignado')]

    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(*C_MUTED)
    pdf.cell(0, 5, f'Total programados: {len(asignados)}   |   Sin asignar: {len(sin_asignar)}',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    _section(pdf, 'Vehiculos Programados')
    cols = [28, 50, 50, 28, 25, 25, 55]
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
        ], cols, bg=bg, first_color=C_ACCENT)

    if sin_asignar:
        pdf.ln(8)
        _section(pdf, f'Sin Asignar ({len(sin_asignar)} vehiculos — sin historial de llegada)')
        cols2 = [35, 65, 65, 96]
        hdrs2 = ['Placa', 'Municipio', 'Supervisor', 'Motivo']
        _table_header(pdf, hdrs2, cols2)
        for idx, v in enumerate(sin_asignar):
            bg = C_LIGHT if idx % 2 else C_WHITE
            _table_row(pdf, [
                _t(v.get('placa', '')),
                _t(v.get('mun', 'N/D')),
                _t(v.get('sup', 'N/D')),
                _t(v.get('razon', 'Sin registros de llegada'))
            ], cols2, bg=bg, first_color=C_MUTED)

    return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────────────────
# REPORTE 3: LAVADORES
# ─────────────────────────────────────────────────────────────────────────────
def _reporte_lavadores(historial, vehiculos, responsable, lavadores_stats=None):
    if lavadores_stats is None: lavadores_stats = {}
    placa_to_mun = {v['placa']: v.get('mun', 'N/D') for v in vehiculos}

    pdf = CleanReport(
        titulo='Reporte de Lavadores — Detalle de Servicios',
        subtitulo=f'Corte al {datetime.datetime.now().strftime("%d/%m/%Y")}',
        responsable=responsable
    )
    pdf.set_compression(True)
    pdf.add_page()

    # Agrupar por lavador
    por_lavador = defaultdict(list)
    for h in historial:
        lav = _t(h.get('lavador', 'Sin asignar')).strip() or 'Sin asignar'
        por_lavador[lav].append(h)

    if not por_lavador:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.set_text_color(*C_MUTED)
        pdf.cell(0, 8, 'No hay registros de lavados en el historial.', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return bytes(pdf.output())

    cols = [30, 45, 28, 22, 22, 35, 79]
    hdrs = ['Placa', 'Municipio', 'Fecha', 'Inicio', 'Fin', 'Tipo', 'Origen']

    for lavador, lavados in sorted(por_lavador.items()):
        _section(pdf, f'{lavador}   ({len(lavados)} servicio(s))')
        _table_header(pdf, hdrs, cols)
        for idx, h in enumerate(lavados):
            bg = C_LIGHT if idx % 2 else C_WHITE
            mun = placa_to_mun.get(h.get('placa', ''), 'N/D')
            origen_map = {
                'qr_registro':     'QR (campo)',
                'dashboard_manual':'Manual (app)',
                'dashboard_sumar': 'Botón +'
            }
            _table_row(pdf, [
                _t(h.get('placa', '')),
                _t(mun),
                _t(h.get('fecha', '')),
                _t(h.get('hora_inicio', h.get('hora', '-'))),
                _t(h.get('hora_fin', '-')),
                _t(h.get('tipo_lavado', 'General')),
                _t(origen_map.get(h.get('origen', ''), h.get('origen', '-')))
            ], cols, bg=bg, first_color=C_ACCENT)
        pdf.ln(6)

    # Agregar resumen de nómina si hay datos
    if lavadores_stats:
        pdf.add_page()
        _section(pdf, 'Resumen Estimado de Nómina')
        cols_nomina = [60, 40, 40, 40, 60]
        hdrs_nomina = ['Lavador', 'Generales', 'Sencillos', 'Enjuagues', 'Total Estimado']
        _table_header(pdf, hdrs_nomina, cols_nomina)
        
        total_empresa = 0
        for idx, (lavador, data) in enumerate(sorted(lavadores_stats.items())):
            tipos = data.get('tipos', {})
            pago = data.get('pago_estimado', 0)
            total_empresa += pago
            
            bg = C_LIGHT if idx % 2 else C_WHITE
            _table_row(pdf, [
                _t(lavador),
                str(tipos.get('General', 0)),
                str(tipos.get('Sencillo', 0)),
                str(tipos.get('Enjuague', 0)),
                f"${pago:,.0f}"
            ], cols_nomina, bg=bg, first_color=C_DARK, last_color=C_GREEN)
            
        pdf.ln(6)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(*C_GREEN)
        pdf.cell(0, 8, f'Total de Nomina Estimada: ${total_empresa:,.0f}', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────────────────
# REPORTE 4: INVENTARIO DE FLOTA
# ─────────────────────────────────────────────────────────────────────────────
def _reporte_flota(vehiculos, stats, responsable):
    pdf = CleanReport(
        titulo='Inventario de Flota',
        subtitulo=f'Corte al {datetime.datetime.now().strftime("%d/%m/%Y")}   |   {len(vehiculos)} vehiculos registrados',
        responsable=responsable
    )
    pdf.set_compression(True)
    pdf.add_page()

    # Resumen rápido
    kpis = [
        ('Total vehiculos',   str(stats.get('total_veh', len(vehiculos))), C_ACCENT),
        ('Lavados generales', str(stats.get('total_gen', 0)),              C_GREEN),
        ('Sin ningun lavado', str(stats.get('sin_gen', 0)),                C_RED),
        ('Cumplimiento',      f"{stats.get('pct_cum', 0)}%",               C_GREEN if float(stats.get('pct_cum', 0)) >= 80 else C_RED),
    ]
    _draw_kpi_strip(pdf, kpis)
    pdf.ln(6)

    _section(pdf, 'Listado Completo de Vehiculos')
    cols = [28, 50, 30, 30, 60, 35, 20, 8]
    hdrs = ['Placa', 'Municipio', 'Tipo', 'Ruta', 'Supervisor', 'Ultimo Lavado', 'Lav.', '']
    _table_header(pdf, hdrs[:-1], cols[:-1])

    sorted_veh = sorted(vehiculos, key=lambda v: (v.get('mun', ''), v.get('placa', '')))
    for idx, v in enumerate(sorted_veh):
        bg = C_LIGHT if idx % 2 else C_WHITE
        lav = v.get('lavGen', 0)
        first_color = C_GREEN if lav > 0 else C_RED
        _table_row(pdf, [
            _t(v.get('placa', '')),
            _t(v.get('mun', 'N/D')),
            _t(v.get('tipo', 'N/D')),
            _t(v.get('ruta', 'N/D')),
            _t(v.get('sup', 'N/D')),
            _t(v.get('ultimo', 'NUNCA')),
            str(lav)
        ], cols[:-1], bg=bg, first_color=first_color)

    return bytes(pdf.output())


# ── Helpers de dibujo ─────────────────────────────────────────────────────────
def _section(pdf: CleanReport, title: str):
    """Encabezado de sección limpio."""
    y = pdf.get_y() + 1
    pdf.set_draw_color(*C_ACCENT)
    pdf.set_line_width(0.6)
    pdf.line(18, y, 23, y)
    pdf.set_line_width(0.2)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(*C_DARK)
    pdf.set_xy(25, y - 3)
    pdf.cell(0, 6, _t(title).upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)


def _draw_kpi_strip(pdf: CleanReport, kpis: list):
    """Fila de tarjetas KPI compactas."""
    n    = len(kpis)
    x0   = 18
    gap  = 4
    total_w = 261  # 297 - 18*2
    w_c  = (total_w - gap * (n - 1)) / n
    h    = 20
    y    = pdf.get_y()

    for i, (label, value, color) in enumerate(kpis):
        x = x0 + i * (w_c + gap)
        # Fondo y borde
        pdf.set_fill_color(*C_LIGHT)
        pdf.set_draw_color(*C_RULE)
        pdf.set_line_width(0.25)
        pdf.rect(x, y, w_c, h, 'FD')
        # Línea de color izquierda
        pdf.set_fill_color(*color)
        pdf.rect(x, y, 2, h, 'F')
        # Valor
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(*color)
        pdf.set_xy(x + 4, y + 2)
        pdf.cell(w_c - 6, 8, _t(value), align='C')
        # Etiqueta
        pdf.set_font('Helvetica', 'B', 5.5)
        pdf.set_text_color(*C_MUTED)
        pdf.set_xy(x + 4, y + 11)
        pdf.cell(w_c - 6, 5, _t(label).upper(), align='C')

    pdf.set_y(y + h + 4)


def _table_header(pdf: CleanReport, headers: list, col_widths: list):
    """Encabezado de tabla con fondo oscuro."""
    y = pdf.get_y()
    total_w = sum(col_widths)
    pdf.set_fill_color(*C_BLACK)
    pdf.set_draw_color(*C_BLACK)
    pdf.set_line_width(0)
    pdf.rect(18, y, total_w, 7, 'F')

    x = 18
    for hdr, w in zip(headers, col_widths):
        pdf.set_font('Helvetica', 'B', 7)
        pdf.set_text_color(*C_WHITE)
        pdf.set_xy(x + 2, y + 1.5)
        pdf.cell(w - 4, 4, _t(hdr).upper(), align='L')
        x += w
    pdf.set_y(y + 7)


def _table_row(pdf: CleanReport, cells: list, col_widths: list,
               bg=C_WHITE, first_color=None, last_color=None):
    """Fila de tabla. first_color aplica al primer campo (placa), last_color al último."""
    if pdf.get_y() + 6.5 > 188:
        pdf.add_page()
        pdf.set_y(28)

    y = pdf.get_y()
    total_w = sum(col_widths)
    pdf.set_fill_color(*bg)
    pdf.set_draw_color(*C_RULE)
    pdf.set_line_width(0.15)
    pdf.rect(18, y, total_w, 6.5, 'FD')

    x = 18
    for i, (cell, w) in enumerate(zip(cells, col_widths)):
        if i == 0 and first_color:
            color = first_color
            style = 'B'
        elif i == len(cells) - 1 and last_color:
            color = last_color
            style = 'B'
        else:
            color = C_DARK
            style = ''
        pdf.set_font('Helvetica', style, 7.5)
        pdf.set_text_color(*color)
        pdf.set_xy(x + 2, y + 1.5)
        pdf.cell(w - 4, 4, str(cell)[:40], align='L')
        x += w
    pdf.set_y(y + 6.5)
