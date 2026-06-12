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
        lav = (h.get('lavador') or '').strip().upper()
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
        pdf.cell(80, 5, _t(f'{len(lavados)} servicios  |  periodo activo'), align='R')

        # ── Mini KPIs del lavador ─────────────────────────────────────────
        tc = {'General': 0, 'Sencillo': 0, 'Enjuague': 0}
        t_mins = 0; t_pago = 0
        for l in lavados:
            tipo = l.get('tipo_lavado', 'General')
            tc[tipo] = tc.get(tipo, 0) + 1
            t_pago += float(tarifas.get(tipo, 0))
            t_mins += _calc_mins(l.get('hora_inicio', ''), l.get('hora_fin', ''))

        mkpi = [
            ('Generales',  str(tc['General']),  C_AZURE),
            ('Sencillos',  str(tc['Sencillo']), C_TEAL),
            ('Enjuagues',  str(tc['Enjuague']), C_AMBER),
            ('Hrs Trabajadas', f'{t_mins//60}h {t_mins%60:02d}m', C_MUTED),
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

            cells = [
                l.get('fecha', '-'), l.get('placa', '-'), tipo,
                l.get('hora_inicio', '-'), l.get('hora_fin', '-'),
                dur_str, f'${tarifa_u:,.0f}', f'${tarifa_u:,.0f}',
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
            _t(f'{len(lavados)} servicio(s)  |  {t_mins//60}h {t_mins%60:02d}m trabajados'),
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
            tc2[tipo] = tc2.get(tipo, 0) + 1
            pl += float(tarifas.get(tipo, 0))
            ml += _calc_mins(l.get('hora_inicio', ''), l.get('hora_fin', ''))
        grand_total += pl; grand_mins += ml

        bg = C_SLATE if idx % 2 else C_WHITE
        ry = pdf.get_y()
        pdf.set_fill_color(*bg)
        pdf.set_draw_color(*C_RULE)
        pdf.set_line_width(0.1)
        pdf.rect(20, ry, sum(SR_COLS), 8.5, 'FD')
        row = [
            lav_name.title(),
            str(tc2['General']), str(tc2['Sencillo']), str(tc2['Enjuague']),
            f'{ml//60}h {ml%60:02d}m', f'${pl:,.0f}',
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

