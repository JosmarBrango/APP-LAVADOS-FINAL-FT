from flask import Blueprint, request, jsonify
from utils import login_required, admin_required
from models import db, Vehiculo, Lavado, Configuracion, User
from services import process_csv, generar_programacion, allowed_file
from sqlalchemy import func, distinct
from werkzeug.utils import secure_filename
import json
import datetime as dt
import os

api_bp = Blueprint('api', __name__, url_prefix='/api')
upload_bp = Blueprint('upload', __name__)


def _build_full_response():
    """
    Construye el payload completo del dashboard usando el mínimo de consultas SQL.
    Evita el problema N+1 que causaba timeouts en Supabase.
    """
    # 1. Una sola consulta para todos los vehículos
    vehiculos = Vehiculo.query.all()

    # 2. Una sola consulta para todos los lavados (sin lazy-loading)
    todos_lavados = Lavado.query.order_by(Lavado.id.desc()).all()

    # 3. Agrupar lavados por placa en Python (sin más roundtrips a la DB)
    lavados_por_placa = {}  # placa -> [Lavado]
    for l in todos_lavados:
        lavados_por_placa.setdefault(l.placa, []).append(l)

    # 4. Construir lista de vehículos para el frontend
    v_list = []
    for v in vehiculos:
        lavs = lavados_por_placa.get(v.placa, [])
        lavados_gen = [l for l in lavs if l.tipo_lavado == 'General']
        lavGen = len(lavados_gen)
        lastGen = max([l.fecha for l in lavados_gen]) if lavados_gen else 'NUNCA'
        v_list.append({
            'placa': v.placa,
            'mun': v.municipio,
            'tipo': v.tipo,
            'ruta': v.ruta,
            'sup': v.supervisor,
            'lavGen': lavGen,
            'ultimo': lastGen,
            'horaDow': {}
        })

    # 5. Construir historial y stats de lavadores en un solo loop
    h_list = []
    lavadores_stats = {}
    chart_data = {'tiposLavado': {'Sencillo': 0, 'Enjuague': 0}}

    for l in todos_lavados:
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
        if l.lavador:
            lav = l.lavador.strip().upper()
            if lav not in lavadores_stats:
                lavadores_stats[lav] = {
                    'total_lavados': 0,
                    'tiempo_total_minutos': 0,
                    'tipos': {'General': 0, 'Sencillo': 0, 'Enjuague': 0}
                }
            lavadores_stats[lav]['total_lavados'] += 1
            tipo = l.tipo_lavado or 'General'
            lavadores_stats[lav]['tipos'][tipo] = lavadores_stats[lav]['tipos'].get(tipo, 0) + 1

        if l.tipo_lavado in chart_data['tiposLavado']:
            chart_data['tiposLavado'][l.tipo_lavado] += 1

    # 6. Stats globales calculados en Python
    total_veh = len(v_list)
    total_gen = sum(v['lavGen'] for v in v_list)
    vehiculos_con_lavado = sum(1 for v in v_list if v['lavGen'] > 0)
    sin_gen = total_veh - vehiculos_con_lavado
    meta = total_veh * 3
    deficit = max(0, meta - total_gen)
    pct_cum = round(total_gen / meta * 100, 1) if meta > 0 else 0

    stats = {
        'total_veh': total_veh,
        'total_gen': total_gen,
        'sin_gen': sin_gen,
        'meta': meta,
        'deficit': deficit,
        'pct_cum': pct_cum,
        'n_meses': 3
    }

    # 7. Programación manual
    conf = Configuracion.query.filter_by(key='programacion_manual').first()
    prog_manual = json.loads(conf.value) if conf and conf.value else {}

    return {
        'vehiculos': v_list,
        'historial_lavados': h_list,
        'lavadores_stats': lavadores_stats,
        'programacion_manual': prog_manual,
        'chartData': chart_data,
        'stats': stats
    }


@api_bp.route('/data')
@login_required
def get_data():
    payload = _build_full_response()
    return jsonify(payload)


@api_bp.route('/stats')
@login_required
def get_stats():
    # Reutilizar la misma lógica para evitar queries extra
    v_list = []
    vehiculos = Vehiculo.query.all()
    lavados_gen_count = {}  # placa -> count

    rows = db.session.query(Lavado.placa, func.count(Lavado.id)).filter(
        Lavado.tipo_lavado == 'General'
    ).group_by(Lavado.placa).all()

    for placa, cnt in rows:
        lavados_gen_count[placa] = cnt

    total_veh = len(vehiculos)
    total_gen = sum(lavados_gen_count.values())
    sin_gen = sum(1 for v in vehiculos if lavados_gen_count.get(v.placa, 0) == 0)
    meta = total_veh * 3
    deficit = max(0, meta - total_gen)
    pct_cum = round(total_gen / meta * 100, 1) if meta > 0 else 0

    return jsonify({
        'total_veh': total_veh,
        'total_gen': total_gen,
        'sin_gen': sin_gen,
        'meta': meta,
        'deficit': deficit,
        'pct_cum': pct_cum,
        'n_meses': 3
    })


@api_bp.route('/last-qr-event')
@login_required
def get_last_qr_event():
    return jsonify({'event': None})


@api_bp.route('/config/tarifas', methods=['GET', 'POST'])
@login_required
def handle_tarifas():
    conf = Configuracion.query.filter_by(key='tarifas').first()
    if request.method == 'GET':
        if conf:
            return jsonify(json.loads(conf.value))
        return jsonify({"General": 0, "Sencillo": 0, "Enjuague": 0})
    data = request.json or {}
    val = json.dumps(data)
    if conf:
        conf.value = val
    else:
        conf = Configuracion(key='tarifas', value=val)
        db.session.add(conf)
    db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.route('/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    users = User.query.all()
    return jsonify([{'username': u.username, 'name': u.name, 'role': u.role, 'active': u.active} for u in users])


@api_bp.route('/users/save', methods=['POST'])
@login_required
@admin_required
def save_user():
    data = request.json or {}
    username = data.get('username')
    if not username:
        return jsonify({'error': 'Falta el nombre de usuario'}), 400
    u = User.query.filter_by(username=username).first()
    if not u:
        u = User(username=username)
        db.session.add(u)
    if data.get('password'):
        u.password = data.get('password')
    u.name = data.get('name', u.name)
    u.role = data.get('role', u.role)
    u.active = data.get('active', True)
    db.session.commit()
    return jsonify({'status': 'ok'})


@api_bp.route('/users/delete', methods=['POST'])
@login_required
@admin_required
def delete_user():
    data = request.json or {}
    username = data.get('username')
    if username == 'admin':
        return jsonify({'error': 'No se puede eliminar al administrador principal'}), 400
    u = User.query.filter_by(username=username).first()
    if u:
        db.session.delete(u)
        db.session.commit()
    return jsonify({'status': 'ok'})


@api_bp.route('/lavado/add_manual', methods=['POST'])
@login_required
def add_lavado_manual():
    data = request.json or {}
    placa = data.get('placa')
    fecha = data.get('fecha')
    hora_inicio = data.get('hora_inicio', '')
    hora_fin = data.get('hora_fin', '')
    tipo_lavado = data.get('tipo_lavado', 'General')
    lavador = data.get('lavador', '')

    v = Vehiculo.query.filter_by(placa=placa).first()
    if not v:
        return jsonify({'error': f'Vehículo {placa} no encontrado.'}), 404

    now = dt.datetime.now()
    l = Lavado(
        placa=placa,
        fecha=fecha,
        hora=hora_inicio or now.strftime('%H:%M'),
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        lavador=lavador,
        tipo_lavado=tipo_lavado,
        origen='dashboard_manual'
    )
    db.session.add(l)
    db.session.commit()
    return jsonify(_build_full_response())


@api_bp.route('/lavado/remove', methods=['POST'])
@login_required
@admin_required
def remove_lavado():
    data = request.json or {}
    placa = data.get('placa')
    tipo = data.get('tipo')
    tipo_lav = 'General' if tipo == 'lavGen' else tipo

    l = Lavado.query.filter_by(placa=placa, tipo_lavado=tipo_lav).order_by(Lavado.id.desc()).first()
    if l:
        db.session.delete(l)
        db.session.commit()
    return jsonify(_build_full_response())


@api_bp.route('/vehiculo/add', methods=['POST'])
@login_required
@admin_required
def add_vehiculo():
    data = request.json or {}
    placa = (data.get('placa') or '').strip().upper()
    if not placa:
        return jsonify({'error': 'La placa es obligatoria.'}), 400
    if Vehiculo.query.filter_by(placa=placa).first():
        return jsonify({'error': 'Ya existe un vehículo con esa placa.'}), 400
    v = Vehiculo(
        placa=placa,
        municipio=data.get('mun', 'N/D').upper(),
        tipo=data.get('tipo', 'N/D').upper(),
        ruta=data.get('ruta', 'N/D').upper(),
        supervisor=data.get('sup', 'N/D').upper()
    )
    db.session.add(v)
    db.session.commit()
    return jsonify(_build_full_response())


@api_bp.route('/vehiculo/edit', methods=['POST'])
@login_required
@admin_required
def edit_vehiculo():
    data = request.json or {}
    placa = data.get('placa')
    v = Vehiculo.query.filter_by(placa=placa).first()
    if not v:
        return jsonify({'error': f'Vehículo {placa} no encontrado.'}), 404
    v.municipio = data.get('mun', v.municipio).upper()
    v.tipo = data.get('tipo', v.tipo).upper()
    v.ruta = data.get('ruta', v.ruta).upper()
    v.supervisor = data.get('sup', v.supervisor).upper()
    db.session.commit()
    return jsonify(_build_full_response())


@api_bp.route('/vehiculo/remove', methods=['POST'])
@login_required
@admin_required
def remove_vehiculo():
    data = request.json or {}
    placa = data.get('placa')
    v = Vehiculo.query.filter_by(placa=placa).first()
    if v:
        db.session.delete(v)
        db.session.commit()
    return jsonify(_build_full_response())


@api_bp.route('/programacion', methods=['POST'])
@login_required
def get_programacion():
    data = request.json or {}
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    max_dia = int(data.get('max_dia', 4))

    # Usar _build_full_response reutilizando los datos cargados
    vehiculos = Vehiculo.query.all()
    lavados_gen_count = {}
    rows = db.session.query(Lavado.placa, func.count(Lavado.id)).filter(
        Lavado.tipo_lavado == 'General'
    ).group_by(Lavado.placa).all()
    for placa, cnt in rows:
        lavados_gen_count[placa] = cnt

    v_list = [{
        'placa': v.placa,
        'mun': v.municipio,
        'tipo': v.tipo,
        'ruta': v.ruta,
        'sup': v.supervisor,
        'lavGen': lavados_gen_count.get(v.placa, 0)
    } for v in vehiculos]

    conf = Configuracion.query.filter_by(key='programacion_manual').first()
    prog_manual = json.loads(conf.value) if conf and conf.value else {}
    prog = generar_programacion(v_list, start_date, end_date, max_dia, prog_manual)
    return jsonify(prog)


@api_bp.route('/programacion/update_fecha', methods=['POST'])
@login_required
@admin_required
def update_programacion_fecha():
    data = request.json or {}
    placa = data.get('placa')
    nueva_fecha = data.get('nueva_fecha')

    conf = Configuracion.query.filter_by(key='programacion_manual').first()
    prog_manual = json.loads(conf.value) if conf and conf.value else {}
    if not nueva_fecha:
        prog_manual.pop(placa, None)
    else:
        prog_manual[placa] = nueva_fecha

    val = json.dumps(prog_manual)
    if conf:
        conf.value = val
    else:
        db.session.add(Configuracion(key='programacion_manual', value=val))
    db.session.commit()
    return jsonify({'status': 'ok'})


@upload_bp.route('/upload', methods=['POST'])
@login_required
@admin_required
def upload_file():
    from flask import current_app
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        res = process_csv(filepath)
        if 'error' in res:
            return jsonify(res), 400

        for v_data in res.get('vehiculos', []):
            placa = v_data['placa']
            v = Vehiculo.query.filter_by(placa=placa).first()
            if not v:
                v = Vehiculo(placa=placa)
                db.session.add(v)
            v.municipio = v_data.get('mun', 'N/D')
            v.tipo = v_data.get('tipo', 'N/D')
            v.ruta = v_data.get('ruta', 'N/D')
            v.supervisor = v_data.get('sup', 'N/D')
        db.session.commit()
        return jsonify(_build_full_response())
    return jsonify({'error': 'Formato no permitido.'}), 400


@api_bp.route('/lavado/add', methods=['POST'])
def add_lavado():
    data = request.json or {}
    placa = data.get('placa')
    lavador = data.get('lavador')

    if not placa or not lavador:
        return jsonify({'error': 'Datos incompletos.'}), 400

    v = Vehiculo.query.filter_by(placa=placa).first()
    if not v:
        return jsonify({'error': f'El vehículo {placa} no existe.'}), 404

    now = dt.datetime.now()
    l = Lavado(
        placa=placa,
        fecha=now.strftime('%Y-%m-%d'),
        hora=now.strftime('%H:%M'),
        hora_inicio=now.strftime('%H:%M'),
        hora_fin=now.strftime('%H:%M'),
        lavador=lavador,
        tipo_lavado='General',
        origen='QR'
    )
    db.session.add(l)
    db.session.commit()

    from app import socketio
    socketio.emit('qr_event', {
        'placa': placa,
        'fecha': l.fecha,
        'hora': l.hora,
        'lavador': lavador,
        'tipo': l.tipo_lavado
    })

    return jsonify({'status': 'ok'})
