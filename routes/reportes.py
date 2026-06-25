from flask import Blueprint, request, jsonify, send_file
from utils import login_required, admin_required
from models import db, Vehiculo, Lavado, Configuracion
from pdf_report import generar_pdf, generar_nomina_pdf
import json
from io import BytesIO

reportes_bp = Blueprint('reportes', __name__)

def _get_legacy_db_data():
    # Traduce SQLAlchemy a diccionarios para no reescribir pdf_report.py
    v_list = []
    for v in Vehiculo.query.all():
        lavs = [{'fecha': l.fecha, 'hora': l.hora, 'lavador': l.lavador, 'tipo_lavado': l.tipo_lavado, 'hora_inicio': l.hora_inicio, 'hora_fin': l.hora_fin, 'origen': l.origen} for l in v.lavados]
        v_list.append({
            'placa': v.placa,
            'mun': v.municipio,
            'tipo': v.tipo,
            'ruta': v.ruta,
            'sup': v.supervisor,
            'lavGen': len([l for l in lavs if l['tipo_lavado'] == 'General'])
        })
    
    h_list = []
    for l in Lavado.query.order_by(Lavado.id.desc()).all():
        h_list.append({
            'id': l.id,
            'placa': l.placa,
            'fecha': l.fecha,
            'hora': l.hora,
            'hora_inicio': l.hora_inicio,
            'hora_fin': l.hora_fin,
            'lavador': l.lavador,
            'tipo_lavado': l.tipo_lavado,
            'origen': l.origen
        })
        
    stats = {}
    # Podríamos calcular los stats o dejarlos vacíos si no los usa el reporte a fondo
    stats['total_veh'] = len(v_list)
    stats['total_gen'] = sum(v['lavGen'] for v in v_list)
    stats['meta'] = stats['total_veh'] * 3
    stats['deficit'] = max(0, stats['meta'] - stats['total_gen'])
    stats['pct_cum'] = round(stats['total_gen'] / stats['meta'] * 100, 1) if stats['meta'] > 0 else 0
    
    return {
        'vehiculos': v_list,
        'historial_lavados': h_list,
        'stats': stats
    }

@reportes_bp.route('/exportar-pdf', methods=['POST'])
@login_required
@admin_required
def exportar_pdf():
    data = request.json or {}
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    placas = data.get('placas', [])
    max_dia = int(data.get('max_dia', 4))
    responsable = data.get('responsable', '').strip()
    tipo_reporte = data.get('tipo_reporte', 'completo')

    if not start_date or not end_date:
        return jsonify({'error': 'Faltan fechas de inicio o fin.'}), 400

    db_data = _get_legacy_db_data()
    vehiculos_a_programar = db_data.get('vehiculos', [])
    if placas:
        vehiculos_a_programar = [v for v in vehiculos_a_programar if v['placa'] in placas]

    from services import generar_programacion
    
    conf = Configuracion.query.filter_by(key='programacion_manual').first()
    prog_manual = json.loads(conf.value) if conf and conf.value else {}

    prog = generar_programacion(vehiculos_a_programar, start_date, end_date, max_dia, prog_manual)
    pdf_bytes = generar_pdf(db_data, prog, start_date, end_date, responsable, tipo_reporte)

    buf = BytesIO(pdf_bytes)
    buf.seek(0)
    nombre_archivo = f"Reporte_{tipo_reporte.capitalize()}_{start_date}.pdf"
    
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=nombre_archivo)

@reportes_bp.route('/api/exportar-nomina-pdf', methods=['POST'])
@login_required
@admin_required
def exportar_nomina_pdf():
    data = request.json or {}
    desde = data.get('desde', '').strip()
    hasta = data.get('hasta', '').strip()
    responsable = data.get('responsable', '').strip()

    db_data = _get_legacy_db_data()
    
    conf = Configuracion.query.filter_by(key='tarifas').first()
    tarifas = json.loads(conf.value) if conf and conf.value else {'General': 0, 'Sencillo': 0, 'Enjuague': 0}
    
    pdf_bytes = generar_nomina_pdf(db_data['historial_lavados'], tarifas, responsable, desde, hasta)

    buf = BytesIO(pdf_bytes)
    buf.seek(0)

    periodo = f'{desde}_al_{hasta}' if (desde and hasta) else (desde or hasta or 'completo')
    nombre_archivo = f'Nomina_{periodo}.pdf'

    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=nombre_archivo)
