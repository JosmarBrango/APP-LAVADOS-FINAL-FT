"""
routes/api_lavados.py
=====================
Blueprint para operaciones de lavados:
  POST /api/lavado/add_manual
  POST /api/lavado/upload_foto
  POST /api/lavado/remove
  POST /api/lavado/edit_fecha
"""
import os
import uuid
import json
import datetime as dt
from werkzeug.utils import secure_filename
from flask import Blueprint, jsonify, request, current_app
from core.auth_helpers import login_required, admin_required
from core.stats import get_full_db_data, save_full_db_data, recalcular_stats, calc_minutos
import database

api_lavados_bp = Blueprint('api_lavados', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'heic', 'heif'}

def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@api_lavados_bp.route('/api/lavado/upload_foto', methods=['POST'])
@login_required
def upload_foto_lavado():
    """Sube hasta 3 fotos para un lavado. Retorna las URLs públicas."""
    if 'fotos' not in request.files:
        return jsonify({'error': 'No se encontraron archivos.'}), 400

    files = request.files.getlist('fotos')
    lavado_id = request.form.get('lavado_id', 'tmp_' + str(uuid.uuid4())[:8])

    saved_urls = []
    for f in files[:3]:  # máximo 3 fotos
        if f and _allowed_file(f.filename):
            ext = f.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex}.{ext}"
            folder = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                current_app.config['UPLOAD_FOLDER'],
                'evidencias',
                str(lavado_id)
            )
            os.makedirs(folder, exist_ok=True)
            filepath = os.path.join(folder, unique_name)
            f.save(filepath)
            saved_urls.append(f"/uploads/evidencias/{lavado_id}/{unique_name}")

    return jsonify({'fotos': saved_urls})


@api_lavados_bp.route('/api/lavado/add_manual', methods=['POST'])
@login_required
def add_lavado_manual():
    # Soporta tanto JSON como multipart/form-data (para fotos)
    if request.content_type and 'multipart' in request.content_type:
        data = request.form
        fotos_raw = data.get('fotos_json', '[]')
        try:
            fotos = json.loads(fotos_raw)
        except Exception:
            fotos = []
        checklist_raw = data.get('checklist_json', '{}')
        try:
            checklist = json.loads(checklist_raw)
        except Exception:
            checklist = {}
        # Si vienen archivos directamente en este request
        if 'fotos' in request.files:
            files = request.files.getlist('fotos')
            # Se guardan en carpeta temporal; el ID real se asigna tras inserción
            _fotos_files = files
        else:
            _fotos_files = []
    else:
        data = request.json or {}
        fotos = data.get('fotos', [])
        checklist = data.get('checklist', {})
        _fotos_files = []

    placa        = data.get('placa')
    fecha        = data.get('fecha')
    hora_llegada = data.get('hora_llegada', '')
    hora_inicio  = data.get('hora_inicio', '')
    hora_fin     = data.get('hora_fin', '')
    tipo_lavado  = data.get('tipo_lavado', 'General')
    municipio    = data.get('municipio', '')

    lavadores = data.getlist('lavadores') if hasattr(data, 'getlist') else data.get('lavadores', [])
    if not lavadores:
        lavador_str = data.get('lavador', '')
        lavadores   = [lavador_str] if lavador_str else []
    lavadores = [l.strip() for l in lavadores if l.strip()]

    db_data = get_full_db_data()
    if not db_data:
        return jsonify({'error': 'No hay datos cargados.'}), 400

    placa_norm = (placa or '').strip().upper()
    vehiculo = next((v for v in db_data.get('vehiculos', []) if v.get('placa', '').upper().strip() == placa_norm), None)
    if not vehiculo:
        return jsonify({'error': f'Vehículo {placa} no encontrado.'}), 404

    if tipo_lavado == 'General':
        vehiculo['lavGen'] = vehiculo.get('lavGen', 0) + 1
        if fecha:
            parts = fecha.split('-')
            vehiculo['ultimo'] = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else fecha

    if municipio:
        vehiculo['mun'] = municipio.strip().upper()
        database.upsert_vehiculos([vehiculo])

    # Calcular tiempos
    def _calc_diff(h1, h2):
        if not h1 or not h2:
            return None
        try:
            h1_h, h1_m = map(int, h1.split(':'))
            h2_h, h2_m = map(int, h2.split(':'))
            diff = (h2_h * 60 + h2_m) - (h1_h * 60 + h1_m)
            if diff < 0:
                diff += 24 * 60
            return diff
        except Exception:
            return None

    t_espera = _calc_diff(hora_llegada, hora_inicio)
    t_lavado = _calc_diff(hora_inicio, hora_fin)
    origen   = (data.get('origen') or '').strip() or 'dashboard_manual'

    nuevo_lavado = {
        'placa':        placa,
        'fecha':        fecha,
        'hora':         hora_inicio or dt.datetime.now().strftime('%H:%M'),
        'hora_llegada': hora_llegada,
        'hora_inicio':  hora_inicio,
        'hora_fin':     hora_fin,
        'tiempo_espera': t_espera,
        'tiempo_lavado': t_lavado,
        'lavadores':    lavadores,
        'tipo_lavado':  tipo_lavado,
        'municipio':    municipio,
        'origen':       origen,
        'fotos':        fotos,
        'checklist':    checklist,
    }
    database.add_lavado(nuevo_lavado)

    # Actualizar horaDow (promedio móvil, solo General)
    if hora_inicio and fecha and tipo_lavado == 'General':
        try:
            d_obj   = dt.datetime.strptime(fecha, "%Y-%m-%d")
            dow     = d_obj.isoweekday() % 7
            ref     = hora_llegada or hora_inicio
            hh, mm  = map(int, ref.split(':'))
            mins    = hh * 60 + mm
            hora_dow = vehiculo.setdefault('horaDow', {})
            dow_str  = str(dow)
            existing = hora_dow.get(dow_str)
            if existing:
                new_n = existing['n'] + 1
                new_m = round((existing['m'] * existing['n'] + mins) / new_n)
                new_s = f"{new_m // 60:02d}:{new_m % 60:02d}"
                hora_dow[dow_str] = {'s': new_s, 'm': new_m, 'n': new_n, 'std': existing.get('std', 0)}
            else:
                hora_dow[dow_str] = {'s': ref, 'm': mins, 'n': 1, 'std': 0}
        except Exception:
            pass

    db_data['historial_lavados'] = database.get_all_lavados()
    db_data = recalcular_stats(db_data)
    save_full_db_data(db_data)
    return jsonify(db_data)


@api_lavados_bp.route('/api/lavado/remove', methods=['POST'])
@login_required
@admin_required
def remove_lavado():
    """Elimina un lavado por su ID."""
    data      = request.json or {}
    lavado_id = data.get('id')
    if not lavado_id:
        return jsonify({'error': 'Falta el ID del lavado.'}), 400

    database.remove_lavado(lavado_id)
    db_data  = get_full_db_data()
    historial = db_data.get('historial_lavados', [])
    vehiculos = db_data.get('vehiculos', [])

    for v in vehiculos:
        v_lavados_gen = [
            h for h in historial
            if h.get('placa') == v['placa'] and h.get('tipo_lavado', 'General') == 'General'
        ]
        v['lavGen'] = len(v_lavados_gen)
        if v_lavados_gen:
            fechas = sorted([h.get('fecha') for h in v_lavados_gen if h.get('fecha')], reverse=True)
            if fechas:
                parts = fechas[0].split('-')
                v['ultimo'] = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else fechas[0]
            else:
                v['ultimo'] = 'NUNCA'
        else:
            v['ultimo'] = 'NUNCA'

    db_data = recalcular_stats(db_data)
    save_full_db_data(db_data)
    return jsonify({'success': True})


@api_lavados_bp.route('/api/lavado/edit_fecha', methods=['POST'])
@login_required
@admin_required
def api_edit_lavado_fecha():
    data       = request.json or {}
    lavado_id  = data.get('id')
    nueva_fecha = data.get('fecha')
    if not lavado_id or not nueva_fecha:
        return jsonify({'error': 'Faltan datos'}), 400

    database.update_lavado_fecha(lavado_id, nueva_fecha)

    db_data = get_full_db_data()
    db_data['historial_lavados'] = database.get_all_lavados()
    db_data = recalcular_stats(db_data)
    save_full_db_data(db_data)
    return jsonify({'success': True})
