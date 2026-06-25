from flask import Blueprint, request, jsonify
from utils import login_required, admin_required
from models import db, Vehiculo, Lavado, Configuracion, User
from services import process_csv, generar_programacion, allowed_file
from werkzeug.utils import secure_filename
import json
import datetime as dt
import os

api_bp = Blueprint('api', __name__, url_prefix='/api')
upload_bp = Blueprint('upload', __name__)

@api_bp.route('/data')
@login_required
def get_data():
    vehiculos = Vehiculo.query.all()
    v_list = []
    for v in vehiculos:
        lavados_gen = [l for l in v.lavados if l.tipo_lavado == 'General']
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
            'horaDow': {} # Placeholder para evitar errores de render
        })
    
    # Return everything required by frontend
    conf = Configuracion.query.filter_by(key='programacion_manual').first()
    prog_manual = json.loads(conf.value) if conf and conf.value else {}

    # Historial de lavados
    h_list = []
    lavadores_stats = {}
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
        # Stats por lavador
        if l.lavador:
            lav = l.lavador.strip().upper()
            if lav not in lavadores_stats:
                lavadores_stats[lav] = {'total_lavados': 0, 'tiempo_total_minutos': 0, 'tipos': {'General': 0, 'Sencillo': 0, 'Enjuague': 0}}
            lavadores_stats[lav]['total_lavados'] += 1
            if l.tipo_lavado in lavadores_stats[lav]['tipos']:
                lavadores_stats[lav]['tipos'][l.tipo_lavado] += 1
            else:
                lavadores_stats[lav]['tipos'][l.tipo_lavado] = 1

    chart_data = {'tiposLavado': {'Sencillo': 0, 'Enjuague': 0}}
    for l in Lavado.query.all():
        if l.tipo_lavado in chart_data['tiposLavado']:
            chart_data['tiposLavado'][l.tipo_lavado] += 1

    return jsonify({
        'vehiculos': v_list,
        'historial_lavados': h_list,
        'lavadores_stats': lavadores_stats,
        'programacion_manual': prog_manual,
        'chartData': chart_data
    })

@api_bp.route('/stats')
@login_required
def get_stats():
    total_veh = Vehiculo.query.count()
    total_gen = Lavado.query.filter_by(tipo_lavado='General').count()
    
    vehiculos_con_lavado = db.session.query(Lavado.placa).filter_by(tipo_lavado='General').distinct().count()
    sin_gen = total_veh - vehiculos_con_lavado

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
    else:
        if request.method == 'POST':
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
    res = []
    for u in users:
        res.append({
            'username': u.username,
            'name': u.name,
            'role': u.role,
            'active': u.active
        })
    return jsonify(res)

@api_bp.route('/users/save', methods=['POST'])
@login_required
@admin_required
def save_user():
    data = request.json or {}
    username = data.get('username')
    if not username: return jsonify({'error': 'Falta el nombre de usuario'}), 400
    u = User.query.filter_by(username=username).first()
    if not u:
        u = User(username=username)
        db.session.add(u)
    if data.get('password'): u.password = data.get('password')
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
    if username == 'admin': return jsonify({'error': 'No se puede eliminar al administrador principal'}), 400
    u = User.query.filter_by(username=username).first()
    if u:
        db.session.delete(u)
        db.session.commit()
    return jsonify({'status': 'ok'})

@api_bp.route('/lavado/add_manual', methods=['POST'])
@login_required
def add_lavado_manual():
    data  = request.json or {}
    placa = data.get('placa')
    fecha = data.get('fecha')
    hora_inicio = data.get('hora_inicio', '')
    hora_fin    = data.get('hora_fin', '')
    tipo_lavado = data.get('tipo_lavado', 'General')
    lavador     = data.get('lavador', '')

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
    return get_data()

@api_bp.route('/lavado/remove', methods=['POST'])
@login_required
@admin_required
def remove_lavado():
    data  = request.json or {}
    placa = data.get('placa')
    tipo  = data.get('tipo')
    
    l = Lavado.query.filter_by(placa=placa, tipo_lavado='General' if tipo == 'lavGen' else tipo).order_by(Lavado.id.desc()).first()
    if l:
        db.session.delete(l)
        db.session.commit()
    return get_data()

@api_bp.route('/vehiculo/add', methods=['POST'])
@login_required
@admin_required
def add_vehiculo():
    data = request.json or {}
    placa = (data.get('placa') or '').strip().upper()
    if not placa: return jsonify({'error': 'La placa es obligatoria.'}), 400
    if Vehiculo.query.filter_by(placa=placa).first(): return jsonify({'error': 'Ya existe un vehículo con esa placa.'}), 400
    
    v = Vehiculo(
        placa=placa,
        municipio=data.get('mun', 'N/D').upper(),
        tipo=data.get('tipo', 'N/D').upper(),
        ruta=data.get('ruta', 'N/D').upper(),
        supervisor=data.get('sup', 'N/D').upper()
    )
    db.session.add(v)
    db.session.commit()
    return get_data()

@api_bp.route('/vehiculo/edit', methods=['POST'])
@login_required
@admin_required
def edit_vehiculo():
    data = request.json or {}
    placa = data.get('placa')
    v = Vehiculo.query.filter_by(placa=placa).first()
    if not v: return jsonify({'error': f'Vehículo {placa} no encontrado.'}), 404
    
    v.municipio = data.get('mun', v.municipio).upper()
    v.tipo = data.get('tipo', v.tipo).upper()
    v.ruta = data.get('ruta', v.ruta).upper()
    v.supervisor = data.get('sup', v.supervisor).upper()
    db.session.commit()
    return get_data()

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
    return get_data()

@api_bp.route('/programacion', methods=['POST'])
@login_required
def get_programacion():
    data = request.json or {}
    start_date = data.get('start_date')
    end_date   = data.get('end_date')
    max_dia    = int(data.get('max_dia', 4))
    
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
    if conf: conf.value = val
    else: db.session.add(Configuracion(key='programacion_manual', value=val))
    db.session.commit()
    return jsonify({'status': 'ok'})

@upload_bp.route('/upload', methods=['POST'])
@login_required
@admin_required
def upload_file():
    from flask import current_app
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Procesar con pandas
        res = process_csv(filepath)
        if 'error' in res: return jsonify(res), 400
        
        # Guardar en DB
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
        return get_data()
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
