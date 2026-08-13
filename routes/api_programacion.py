"""
routes/api_programacion.py
==========================
Blueprint para programación de lavados y exportación de PDFs:
  POST /api/programacion
  POST /api/programacion/update_fecha
  POST /exportar-pdf
  POST /api/exportar-nomina-pdf
"""
from io import BytesIO
from flask import Blueprint, jsonify, request, send_file
from core.auth_helpers import login_required, admin_required, load_config
from core.stats import get_full_db_data, recalcular_stats
from services import generar_programacion

api_programacion_bp = Blueprint('api_programacion', __name__)


@api_programacion_bp.route('/api/programacion', methods=['POST'])
@login_required
@admin_required
def get_programacion():
    """
    Genera la propuesta de programación de lavados.
    Body JSON:
      - start_date: 'YYYY-MM-DD'
      - end_date:   'YYYY-MM-DD'
      - placas:     list (opcional)
      - max_dia:    int (default 3)
    """
    data       = request.json or {}
    start_date = data.get('start_date')
    end_date   = data.get('end_date')
    placas     = data.get('placas', [])
    max_dia    = int(data.get('max_dia', 3))

    if not start_date or not end_date:
        return jsonify({'error': 'Faltan fechas de inicio o fin.'}), 400

    db_data = get_full_db_data()
    if not db_data:
        return jsonify({'error': 'Sin datos cargados.'}), 400

    vehiculos_a_programar = db_data.get('vehiculos', [])
    if placas:
        vehiculos_a_programar = [v for v in vehiculos_a_programar if v['placa'] in placas]

    prog_manual = db_data.get('programacion_manual', {})
    prog = generar_programacion(vehiculos_a_programar, start_date, end_date, max_dia, prog_manual)
    return jsonify({
        'programacion': prog,
        'start_date':   start_date,
        'end_date':     end_date,
        'max_dia':      max_dia,
    })


@api_programacion_bp.route('/api/programacion/update_fecha', methods=['POST'])
@login_required
@admin_required
def update_fecha_prog():
    data      = request.json or {}
    placa     = data.get('placa')
    nuevo_dia = data.get('nuevo_dia')

    if not placa:
        return jsonify({'error': 'Falta la placa del vehículo.'}), 400

    db_data = get_full_db_data()
    if not db_data:
        return jsonify({'error': 'Sin datos cargados.'}), 400

    from core.stats import save_full_db_data
    prog_manual = db_data.setdefault('programacion_manual', {})

    if nuevo_dia is None or nuevo_dia in ('null', ''):
        prog_manual.pop(placa, None)
    else:
        prog_manual[placa] = str(nuevo_dia)

    save_full_db_data(db_data)
    return jsonify({'success': True, 'placa': placa, 'nuevo_dia': nuevo_dia})


@api_programacion_bp.route('/exportar-pdf', methods=['POST'])
@login_required
@admin_required
def exportar_pdf():
    """
    Genera y descarga el reporte PDF ejecutivo.
    Body JSON:
      - start_date, end_date, placas, max_dia, responsable, tipo_reporte
    """
    from pdf_report import generar_pdf

    data         = request.json or {}
    start_date   = data.get('start_date')
    end_date     = data.get('end_date')
    placas       = data.get('placas', [])
    max_dia      = int(data.get('max_dia', 4))
    responsable  = data.get('responsable', '').strip()
    tipo_reporte = data.get('tipo_reporte', 'completo')

    if not start_date or not end_date:
        return jsonify({'error': 'Faltan fechas de inicio o fin.'}), 400

    db_data = get_full_db_data()
    if not db_data:
        return jsonify({'error': 'Sin datos cargados. Sube un CSV primero.'}), 400

    # Recalcular lavGen desde historial real para el PDF
    _historial_pdf = db_data.get('historial_lavados', [])
    for _v in db_data.get('vehiculos', []):
        _v_hist_gen = [
            h for h in _historial_pdf
            if h.get('placa') == _v.get('placa')
            and h.get('tipo_lavado', 'General') == 'General'
        ]
        _v['lavGen'] = len(_v_hist_gen)
        if _v_hist_gen:
            _fechas = sorted([h.get('fecha') for h in _v_hist_gen if h.get('fecha')], reverse=True)
            if _fechas:
                _parts = _fechas[0].split('-')
                _v['ultimo'] = f"{_parts[2]}/{_parts[1]}/{_parts[0]}" if len(_parts) == 3 else _fechas[0]
            else:
                _v['ultimo'] = 'NUNCA'
        else:
            _v['ultimo'] = 'NUNCA'

    vehiculos_a_programar = db_data.get('vehiculos', [])
    if placas:
        vehiculos_a_programar = [v for v in vehiculos_a_programar if v['placa'] in placas]

    # Validación especial para Lavados Diarios
    if tipo_reporte == 'diarios':
        historial = db_data.get('historial_lavados', [])
        registros = [h for h in historial if start_date <= h.get('fecha', '') <= end_date]
        if not registros:
            return jsonify({
                'error': (
                    f'No hay lavados registrados para el rango {start_date} al {end_date}. '
                    'Registra al menos un lavado antes de generar la planilla.'
                )
            }), 400

    prog_manual = db_data.get('programacion_manual', {})
    prog = generar_programacion(vehiculos_a_programar, start_date, end_date, max_dia, prog_manual)

    pdf_bytes = generar_pdf(db_data, prog, start_date, end_date, responsable, tipo_reporte)

    buf = BytesIO(pdf_bytes)
    buf.seek(0)

    nombre_archivo = (
        f"Reporte_Programacion_{start_date}_al_{end_date}.pdf"
        if tipo_reporte == 'programacion'
        else f"Reporte_{tipo_reporte.capitalize()}_{start_date}.pdf"
    )
    return send_file(
        buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=nombre_archivo,
    )


@api_programacion_bp.route('/api/exportar-nomina-pdf', methods=['POST'])
@login_required
@admin_required
def exportar_nomina_pdf():
    """
    Genera y descarga el PDF de liquidación de nómina.
    Body JSON: desde, hasta, responsable
    """
    from pdf_report import generar_nomina_pdf

    data        = request.json or {}
    desde       = data.get('desde', '').strip()
    hasta       = data.get('hasta', '').strip()
    responsable = data.get('responsable', '').strip()

    db_data = get_full_db_data()
    if not db_data:
        return jsonify({'error': 'Sin datos cargados.'}), 400

    config   = load_config()
    tarifas  = config.get('tarifas', {'General': 0, 'Sencillo': 0, 'Enjuague': 0})
    historial = db_data.get('historial_lavados', [])

    pdf_bytes = generar_nomina_pdf(historial, tarifas, responsable, desde, hasta)

    buf = BytesIO(pdf_bytes)
    buf.seek(0)

    periodo        = f'{desde}_al_{hasta}' if (desde and hasta) else (desde or hasta or 'completo')
    nombre_archivo = f'Nomina_FlotaUraba_{periodo}.pdf'

    return send_file(
        buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=nombre_archivo,
    )
