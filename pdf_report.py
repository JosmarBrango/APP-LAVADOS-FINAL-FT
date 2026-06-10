"""
pdf_report.py — Generador de reporte PDF ejecutivo para Flota Urabá.
Usa fpdf2 (ya instalado). Genera un informe profesional con KPIs,
grafico de cumplimiento por municipio y tabla de programacion mensual.
"""

import calendar
import datetime
from fpdf import FPDF, XPos, YPos

# ── Colores corporativos ──────────────────────────────────────────────────────
C_BG       = (255, 255, 255)
C_CARD     = (248, 250, 252)
C_BORDER   = (226, 232, 240)
C_TEXT     = (15,  23,  42)
C_MUTED    = (100, 116, 139)
C_GREEN    = (16,  185, 129)
C_GOLD     = (245, 158, 11)
C_BLUE     = (14,  165, 233)
C_RED      = (239, 68,  68)

NOMBRES_MESES = [
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
]

# ── Sanitizacion de texto (Helvetica solo soporta latin-1) ───────────────────
_CHAR_MAP = str.maketrans({
    '\u00e1': 'a', '\u00e9': 'e', '\u00ed': 'i', '\u00f3': 'o', '\u00fa': 'u',
    '\u00c1': 'A', '\u00c9': 'E', '\u00cd': 'I', '\u00d3': 'O', '\u00da': 'U',
    '\u00f1': 'n', '\u00d1': 'N',
    '\u00fc': 'u', '\u00dc': 'U',
    '\u2014': '-', '\u2013': '-',   # em-dash, en-dash
    '\u00b7': '.',                  # middle dot
    '\u00ba': 'o',                  # grado masculino
    '\u00aa': 'a',                  # grado femenino
    '\u00bf': '?',
    '\u00a1': '!',
    '\u00e9': 'e',
    '\u2019': "'",
    '\u201c': '"', '\u201d': '"',
})

def _t(text: str) -> str:
    """Convierte texto con caracteres especiales a latin-1 seguro."""
    try:
        t = str(text).translate(_CHAR_MAP)
        # Segundo pase: quitar cualquier caracter aun fuera de latin-1
        return t.encode('latin-1', errors='replace').decode('latin-1')
    except Exception:
        return str(text).encode('ascii', errors='replace').decode('ascii')


class FlotaReport(FPDF):
    """PDF con tema oscuro para presentacion ejecutiva."""

    def __init__(self, mes_label: str, responsable: str = ''):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.mes_label   = _t(mes_label)
        self.responsable = _t(responsable)
        self.set_margins(14, 14, 14)
        self.set_auto_page_break(auto=True, margin=16)

    def _sf(self, rgb): self.set_fill_color(*rgb)
    def _st(self, rgb): self.set_text_color(*rgb)
    def _sd(self, rgb): self.set_draw_color(*rgb)

    def header(self):
        self._sf(C_BG)
        self.rect(0, 0, 210, 22, 'F')

        self._st(C_BLUE)
        self.set_font('Helvetica', 'B', 14)
        self.set_xy(14, 5)
        self.cell(0, 8, 'FLOTA URABA  -  Reporte de Gestion de Lavados',
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self._st(C_MUTED)
        self.set_font('Helvetica', '', 8)
        self.set_xy(14, 13)
        self.cell(0, 5,
                  f'Generado el {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}  '
                  f'|  Programacion: {self.mes_label}',
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(26)

    def footer(self):
        self.set_y(-12)
        self._sf(C_CARD)
        self.rect(0, self.get_y(), 210, 15, 'F')
        self._st(C_MUTED)
        self.set_font('Helvetica', '', 7)
        self.set_x(14)
        resp = f'Responsable: {self.responsable}  |  ' if self.responsable else ''
        self.cell(
            0, 8,
            f'{resp}Sistema de Gestion de Lavados  |  Zona Uraba  |  Pag. {self.page_no()}',
            align='C'
        )


# ── Funcion principal ─────────────────────────────────────────────────────────
def generar_pdf(db_data: dict, programacion: list,
                start_date: str, end_date: str, responsable: str = '') -> bytes:
    """
    Genera el PDF ejecutivo y devuelve bytes del archivo.

    Args:
        db_data:      Datos del sistema (vehiculos, stats, chartData).
        programacion: Lista con campos diaAsignado, horaMejorDia, etc.
        start_date:   Fecha de inicio del rango ('YYYY-MM-DD').
        end_date:     Fecha de fin del rango ('YYYY-MM-DD').
        responsable:  Nombre para el footer (opcional).

    Returns:
        bytes del PDF.
    """
    stats     = db_data.get('stats', {})
    vehiculos = db_data.get('vehiculos', [])
    mes_label = f'Del {start_date} al {end_date}'

    pdf = FlotaReport(mes_label, responsable)
    pdf.set_compression(True)
    pdf.add_page()

    # ── KPIs ─────────────────────────────────────────────────────────────────
    _section_title(pdf, 'Resumen de Cumplimiento')

    kpi_data = [
        ('Vehiculos en flota', str(stats.get('total_veh', len(vehiculos))), C_BLUE),
        ('Lavados realizados', str(stats.get('total_gen', 0)),              C_GREEN),
        ('Meta del periodo',   str(stats.get('meta', 0)),                   C_MUTED),
        ('Deficit acumulado',  str(stats.get('deficit', 0)),                C_RED),
        ('Sin ningun lavado',  str(stats.get('sin_gen', 0)),                C_GOLD),
        ('Cumplimiento',       f"{stats.get('pct_cum', 0)}%",
         C_GREEN if float(stats.get('pct_cum', 0)) >= 80 else C_GOLD),
    ]
    _kpi_row(pdf, kpi_data)

    # ── Barra de progreso ─────────────────────────────────────────────────────
    pct = float(stats.get('pct_cum', 0))
    _progress_bar(pdf, pct)

    # ── Municipios ────────────────────────────────────────────────────────────
    _section_title(pdf, 'Cumplimiento por municipio')
    _municipio_bars(pdf, vehiculos, stats)

    # ── Tabla programacion ────────────────────────────────────────────────────
    _section_title(pdf, f'Propuesta de programacion - {mes_label}')
    _programacion_table(pdf, programacion, start_date, end_date)

    return bytes(pdf.output())


# ── Dibujo ────────────────────────────────────────────────────────────────────
def _section_title(pdf: FlotaReport, title: str):
    y = pdf.get_y() + 4
    pdf._sd(C_BLUE)
    pdf.set_line_width(0.8)
    pdf.line(14, y, 20, y)
    pdf.set_line_width(0.2)
    pdf._st(C_TEXT)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_xy(22, y - 3)
    pdf.cell(0, 6, _t(title).upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)


def _kpi_row(pdf: FlotaReport, kpi_data: list):
    x0    = 14
    w_c   = (210 - 28 - 5 * 3) / 6
    h_c   = 18
    y     = pdf.get_y()

    for i, (label, value, color) in enumerate(kpi_data):
        x = x0 + i * (w_c + 3)
        pdf._sf(C_CARD); pdf._sd(C_BORDER); pdf.set_line_width(0.3)
        pdf.rect(x, y, w_c, h_c, 'FD')
        pdf._sf(color); pdf.rect(x, y, w_c, 1.2, 'F')   # barra top

        pdf._st(color); pdf.set_font('Helvetica', 'B', 12)
        pdf.set_xy(x + 2, y + 2.5)
        pdf.cell(w_c - 4, 7, _t(value), align='C')

        pdf._st(C_MUTED); pdf.set_font('Helvetica', '', 5.5)
        pdf.set_xy(x + 1, y + 9.5)
        pdf.cell(w_c - 2, 5, _t(label).upper(), align='C')

    pdf.set_y(y + h_c + 5)


def _progress_bar(pdf: FlotaReport, pct: float):
    y = pdf.get_y()
    pdf._st(C_MUTED); pdf.set_font('Helvetica', '', 7)
    pdf.set_xy(14, y)
    pdf.cell(0, 4, f'CUMPLIMIENTO GENERAL DEL PERIODO: {pct:.1f}%')
    pdf.ln(4)

    y2    = pdf.get_y()
    bar_w = 182
    pdf._sf(C_CARD); pdf._sd(C_BORDER)
    pdf.rect(14, y2, bar_w, 5, 'FD')

    fill_w = min(bar_w * pct / 100, bar_w)
    color  = C_GREEN if pct >= 80 else (C_GOLD if pct >= 50 else C_RED)
    pdf._sf(color)
    if fill_w > 0:
        pdf.rect(14, y2, fill_w, 5, 'F')
    pdf.set_y(y2 + 9)


def _municipio_bars(pdf: FlotaReport, vehiculos: list, stats: dict):
    from collections import defaultdict
    grupos  = defaultdict(lambda: {'veh': 0, 'lav': 0})
    n_meses = stats.get('n_meses', 3)

    for v in vehiculos:
        mun = v.get('mun', '')
        if mun and mun.upper() not in ('N/D', '0', ''):
            grupos[mun]['veh'] += 1
            grupos[mun]['lav'] += v.get('lavGen', 0)

    if not grupos:
        pdf._st(C_MUTED); pdf.set_font('Helvetica', '', 8)
        pdf.cell(0, 6, 'Sin datos de municipio disponibles.',
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)
        return

    sorted_muns = sorted(
        grupos.items(),
        key=lambda x: -(x[1]['lav'] / max(x[1]['veh'] * n_meses, 1))
    )

    bar_x = 60; bar_max_w = 120; row_h = 7
    y = pdf.get_y()

    for mun, g in sorted_muns:
        if y + row_h > 270:
            break
        meta  = g['veh'] * n_meses
        pct   = (g['lav'] / meta * 100) if meta > 0 else 0
        color = C_GREEN if pct >= 80 else (C_GOLD if pct >= 40 else C_RED)

        pdf._st(C_TEXT); pdf.set_font('Helvetica', '', 7.5)
        pdf.set_xy(14, y + 1)
        pdf.cell(44, row_h - 2, _t(mun)[:22], align='L')

        pdf._sf(C_CARD); pdf.rect(bar_x, y + 1.5, bar_max_w, 4, 'F')

        fill_w = bar_max_w * pct / 100
        pdf._sf(color)
        if fill_w > 0:
            pdf.rect(bar_x, y + 1.5, fill_w, 4, 'F')

        pdf._st(color); pdf.set_font('Helvetica', 'B', 7)
        pdf.set_xy(bar_x + bar_max_w + 2, y + 1)
        pdf.cell(20, row_h - 2, f'{pct:.0f}%  ({g["lav"]}/{meta})', align='L')

        y += row_h

    pdf.set_y(y + 4)


def _programacion_table(pdf: FlotaReport, programacion: list,
                         start_date: str, end_date: str):
    col_w   = [22, 32, 38, 14, 18, 18, 36]
    headers = ['Placa', 'Municipio', 'Supervisor', 'Dia', 'Llegada', 'Fin est.', 'Turno / Estado']
    h_row   = 5.5

    # Encabezado
    y = pdf.get_y()
    pdf._sf(C_BG); pdf._sd(C_BORDER); pdf.set_line_width(0.3)
    pdf.rect(14, y, sum(col_w), h_row, 'FD')

    x = 14
    for hdr, w in zip(headers, col_w):
        pdf._st(C_MUTED); pdf.set_font('Helvetica', 'B', 6.5)
        pdf.set_xy(x + 1, y + 1)
        pdf.cell(w - 2, h_row - 2, hdr.upper(), align='L')
        x += w
    pdf.set_y(y + h_row)

    # Ordenar: asignados primero
    prog_sorted = sorted(
        programacion,
        key=lambda v: (v.get('diaAsignado') is None, v.get('diaAsignado') or 99)
    )

    for idx, v in enumerate(prog_sorted):
        if pdf.get_y() + h_row > 274:
            pdf.add_page()
            pdf.set_y(28)
            _section_title(pdf, f'Programacion del {start_date} al {end_date} (continuacion)')

        row_y    = pdf.get_y()
        asignado = v.get('diaAsignado')
        turno    = v.get('turno') or {}
        bg       = (255, 255, 255) if idx % 2 == 0 else C_CARD
        t_color  = _turno_rgb(turno.get('cls', 'ok')) if asignado else C_MUTED

        pdf._sf(bg); pdf._sd(C_BORDER); pdf.set_line_width(0.15)
        pdf.rect(14, row_y, sum(col_w), h_row, 'FD')
        pdf._sf(t_color); pdf.rect(14, row_y, 1.5, h_row, 'F')

        row_data = [
            (_t(v.get('placa', '')),                       C_BLUE,  'B'),
            (_t(v.get('mun', 'N/D')),                      C_TEXT,  ''),
            (_t(v.get('sup', 'N/D')),                      C_TEXT,  ''),
            (str(asignado) if asignado else '-',           C_GOLD if asignado else C_MUTED, 'B'),
            (_t(v.get('horaMejorDia', '-')),               C_TEXT,  ''),
            (_t(v.get('finEstimado3h', '-')),              C_MUTED, ''),
            (_t(turno.get('label', 'Sin registros'))
             if asignado else 'Sin datos de llegada',      t_color, ''),
        ]

        x = 14
        for (txt, color, style), w in zip(row_data, col_w):
            pdf._st(color); pdf.set_font('Helvetica', style, 6.5)
            pdf.set_xy(x + (1.5 if x == 14 else 1), row_y + 1.2)
            pdf.cell(w - 2, h_row - 2, str(txt)[:28], align='L')
            x += w
        pdf.set_y(row_y + h_row)

    # Resumen final
    pdf.ln(3)
    asignados = sum(1 for v in programacion if v.get('diaAsignado'))
    sin_datos = len(programacion) - asignados
    pdf._st(C_MUTED); pdf.set_font('Helvetica', '', 7)
    pdf.set_x(14)
    pdf.cell(
        0, 5,
        f'Total programados: {asignados}   |   Sin datos de llegada: {sin_datos}'
        f'   |   Max. 4 vehiculos/dia'
    )


def _turno_rgb(cls: str) -> tuple:
    return {
        'ideal': C_GREEN,
        'good':  (138, 204, 104),
        'ok':    C_GOLD,
        'late':  (227, 179, 65),
    }.get(cls, C_MUTED)
