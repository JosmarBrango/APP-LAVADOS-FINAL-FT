import os
import webbrowser
import threading
import json
from datetime import date, datetime
from io import BytesIO
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from services import process_csv, allowed_file, generar_programacion
import database

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_dev_key_12345')

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
LATEST_DATA_KEY = 'latest_upload'

def _get_full_db_data():
    return {
        'vehiculos': database.get_all_vehiculos(),
        'historial_lavados': database.get_all_lavados(),
        'stats': database.get_data('stats') or {},
        'chartData': database.get_data('chartData') or {},
        'programacion_manual': database.get_data('programacion_manual') or {},
        'last_qr_event': database.get_data('last_qr_event')
    }

def _save_full_db_data(db_data):
    database.upsert_vehiculos(db_data.get('vehiculos', []))
    database.save_data('stats', db_data.get('stats', {}))
    database.save_data('chartData', db_data.get('chartData', {}))
    database.save_data('programacion_manual', db_data.get('programacion_manual', {}))


# Inicializar carpetas y DB (para que funcione con Gunicorn en Render)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
database.init_db()

# ─── Sistema de Usuarios y Roles ──────────────────────────────────────────────
def load_users():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    users_path = os.path.join(base_dir, 'data', 'usuarios_app.json')
    if not os.path.exists(users_path):
        return []
    with open(users_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    users_path = os.path.join(base_dir, 'data', 'usuarios_app.json')
    with open(users_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def load_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, 'data', 'config.json')
    if not os.path.exists(config_path):
        return {"tarifas": {"General": 0, "Sencillo": 0, "Enjuague": 0}}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"tarifas": {"General": 0, "Sencillo": 0, "Enjuague": 0}}

def save_config(config_data):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, 'data', 'config.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({'error': 'Acceso denegado: solo administradores'}), 403
        return f(*args, **kwargs)
    return decorated_function

# ─── Helpers internos ─────────────────────────────────────────────────────────
def _recalcular_stats(db_data: dict) -> dict:
    """
    Recalcula todos los KPIs desde cero usando los vehículos en memoria.
    Evita que el frontend use meta hardcodeada a 3 meses.
    """
    vehiculos = db_data.get('vehiculos', [])
    n_meses   = db_data.get('stats', {}).get('n_meses', 3)
    total_veh = len(vehiculos)
    total_gen = sum(v.get('lavGen', 0) for v in vehiculos)
    sin_gen   = sum(1 for v in vehiculos if v.get('lavGen', 0) == 0)
    meta      = total_veh * n_meses
    deficit   = max(0, meta - total_gen)
    pct_cum   = round(total_gen / meta * 100, 1) if meta > 0 else 0

    db_data['stats'].update({
        'total_veh': total_veh,
        'total_gen': total_gen,
        'sin_gen':   sin_gen,
        'meta':      meta,
        'deficit':   deficit,
        'pct_cum':   pct_cum,
    })
    
    # Reconstruir lavadores_stats desde el historial para que sea retroactivo
    historial = db_data.get('historial_lavados', [])
    lavadores_stats = {}
    for h in historial:
        lavador = h.get('lavador')
        if not lavador: continue
        lavador = lavador.strip().upper()
        tipo_lavado = h.get('tipo_lavado', 'General')
        minutos = calc_minutos(h.get('hora_inicio'), h.get('hora_fin'))
        
        l_stat = lavadores_stats.setdefault(lavador, {
            'total_lavados': 0, 
            'tiempo_total_minutos': 0, 
            'tipos': {'General': 0, 'Sencillo': 0, 'Enjuague': 0}
        })
        l_stat['total_lavados'] += 1
        l_stat['tiempo_total_minutos'] += minutos
        if tipo_lavado in l_stat['tipos']:
            l_stat['tipos'][tipo_lavado] += 1
        else:
            l_stat['tipos'][tipo_lavado] = 1

    db_data['lavadores_stats'] = lavadores_stats

    # Calcular pago_estimado para cada lavador
    config = load_config()
    tarifas = config.get('tarifas', {"General": 0, "Sencillo": 0, "Enjuague": 0})
    
    for lavador, data in lavadores_stats.items():
        tipos = data.get('tipos', {})
        pago = 0
        for tipo, cantidad in tipos.items():
            tarifa = 0
            try:
                tarifa = float(tarifas.get(tipo, 0))
            except:
                pass
            pago += cantidad * tarifa
        data['pago_estimado'] = pago
            
    return db_data

def calc_minutos(h_inicio, h_fin):
    if not h_inicio or not h_fin: return 0
    try:
        hi_h, hi_m = map(int, h_inicio.split(':'))
        hf_h, hf_m = map(int, h_fin.split(':'))
        mi = hi_h * 60 + hi_m
        mf = hf_h * 60 + hf_m
        if mf < mi: mf += 24 * 60
        return mf - mi
    except Exception:
        return 0



# ─── Rutas principales ────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        
        user = next((u for u in users if u['username'] == username and u['password'] == password and u.get('active', True)), None)
        if user:
            session['user'] = user['username']
            session['role'] = user['role']
            session['name'] = user.get('name', username)
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Credenciales incorrectas o cuenta inactiva.')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', user=session)

@app.route('/api/data')
@login_required
def get_data():
    data = _get_full_db_data()
    if data:
        data = _recalcular_stats(data)
        return jsonify(data)
    return jsonify({'error': 'Sin datos. Sube un archivo CSV para comenzar.'})

# ─── MEJORA #3: /api/stats — KPIs siempre calculados en el backend ────────────
@app.route('/api/stats')
@login_required
def get_stats():
    """Devuelve estadísticas recalculadas en tiempo real desde el backend."""
    db_data = _get_full_db_data()
    if not db_data:
        return jsonify({'error': 'Sin datos cargados.'}), 400

    db_data = _recalcular_stats(db_data)
    return jsonify(db_data['stats'])

# ─── MEJORA #1: /api/programacion — Algoritmo en Python ──────────────────────
@app.route('/api/programacion', methods=['POST'])
@login_required
@admin_required
def get_programacion():
    """
    Genera la propuesta de programación de lavados para un rango de fechas dado.
    Body JSON:
      - start_date: 'YYYY-MM-DD'
      - end_date:   'YYYY-MM-DD'
      - placas:     ['ABC123', ...] (lista opcional para filtrar vehículos)
      - max_dia:    int (default: 4)
    """
    data = request.json or {}
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    placas = data.get('placas', [])
    max_dia = int(data.get('max_dia', 4))

    if not start_date or not end_date:
        return jsonify({'error': 'Faltan fechas de inicio o fin.'}), 400

    db_data = _get_full_db_data()
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

@app.route('/api/programacion/update_fecha', methods=['POST'])
@login_required
@admin_required
def update_fecha_prog():
    data = request.json or {}
    placa = data.get('placa')
    nuevo_dia = data.get('nuevo_dia')  # format: 'YYYY-MM-DD' or None

    if not placa:
        return jsonify({'error': 'Falta la placa del vehículo.'}), 400

    db_data = _get_full_db_data()
    if not db_data:
        return jsonify({'error': 'Sin datos cargados.'}), 400

    prog_manual = db_data.setdefault('programacion_manual', {})

    if nuevo_dia is None or nuevo_dia == 'null' or nuevo_dia == '':
        if placa in prog_manual:
            del prog_manual[placa]
    else:
        prog_manual[placa] = str(nuevo_dia)

    _save_full_db_data(db_data)
    return jsonify({'success': True, 'placa': placa, 'nuevo_dia': nuevo_dia})

# ─── Upload CSV ───────────────────────────────────────────────────────────────
@app.route('/upload', methods=['POST'])
@login_required
@admin_required
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No se recibió ningún archivo.'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío.'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Solo se aceptan archivos .csv'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    result = process_csv(filepath)

    if os.path.exists(filepath):
        os.remove(filepath)

    if 'error' in result:
        return jsonify(result), 422

    database.upsert_vehiculos(result.get('vehiculos', []))
    database.save_data('stats', result.get('stats', {}))
    database.save_data('chartData', result.get('chartData', {}))
    return jsonify(result)

# ─── Lavados (add / remove) ───────────────────────────────────────────────────
@app.route('/api/lavado/add', methods=['POST'])
@login_required
@admin_required
def add_lavado():
    data = request.json or {}
    placa = data.get('placa')
    tipo  = data.get('tipo')  # 'lavGen', 'Sencillo', 'Enjuague'

    db_data = _get_full_db_data()
    if not db_data:
        return jsonify({'error': 'No hay datos cargados.'}), 400

    vehiculo = next((v for v in db_data.get('vehiculos', []) if v['placa'] == placa), None)
    if not vehiculo:
        return jsonify({'error': f'Vehículo {placa} no encontrado.'}), 404

    if tipo == 'lavGen':
        vehiculo['lavGen'] = vehiculo.get('lavGen', 0) + 1
        
        # Registrar en historial
        historial = db_data.setdefault('historial_lavados', [])
        historial.insert(0, {
            'placa': placa,
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'hora': datetime.now().strftime('%H:%M'),
            'origen': 'dashboard_sumar'
        })
        # Mantener solo los últimos 200 registros por rendimiento
        db_data['historial_lavados'] = historial[:200]
        
        # ─── FIX Bug #3: recalcular stats completos, no parchear parcialmente ─
        db_data = _recalcular_stats(db_data)
    elif tipo == 'Sencillo':
        db_data['chartData']['tiposLavado']['Sencillo'] += 1
    elif tipo == 'Enjuague':
        db_data['chartData']['tiposLavado']['Enjuague'] += 1

    _save_full_db_data(db_data)
    return jsonify(db_data)

@app.route('/api/lavado/remove', methods=['POST'])
@login_required
@admin_required
def remove_lavado():
    data  = request.json or {}
    placa = data.get('placa')
    tipo  = data.get('tipo')

    db_data = _get_full_db_data()
    if not db_data:
        return jsonify({'error': 'No hay datos cargados.'}), 400

    vehiculo = next((v for v in db_data.get('vehiculos', []) if v['placa'] == placa), None)
    if not vehiculo:
        return jsonify({'error': f'Vehículo {placa} no encontrado.'}), 404

    if tipo == 'lavGen':
        if vehiculo.get('lavGen', 0) > 0:
            vehiculo['lavGen'] -= 1
            db_data = _recalcular_stats(db_data)
    elif tipo == 'Sencillo':
        if db_data['chartData']['tiposLavado'].get('Sencillo', 0) > 0:
            db_data['chartData']['tiposLavado']['Sencillo'] -= 1
    elif tipo == 'Enjuague':
        if db_data['chartData']['tiposLavado'].get('Enjuague', 0) > 0:
            db_data['chartData']['tiposLavado']['Enjuague'] -= 1

    _save_full_db_data(db_data)
    return jsonify(db_data)

@app.route('/api/lavado/add_manual', methods=['POST'])
@login_required
def add_lavado_manual():
    data  = request.json or {}
    placa = data.get('placa')
    fecha = data.get('fecha')
    hora_inicio = data.get('hora_inicio', '')
    hora_fin    = data.get('hora_fin', '')
    tipo_lavado = data.get('tipo_lavado', 'General')
    lavador     = data.get('lavador', '')

    db_data = _get_full_db_data()
    if not db_data:
        return jsonify({'error': 'No hay datos cargados.'}), 400

    vehiculo = next((v for v in db_data.get('vehiculos', []) if v['placa'] == placa), None)
    if not vehiculo:
        return jsonify({'error': f'Vehículo {placa} no encontrado.'}), 404

    if tipo_lavado == 'General':
        vehiculo['lavGen'] = vehiculo.get('lavGen', 0) + 1
        # Actualizar fecha último lavado
        if fecha:
            parts = fecha.split('-')
            vehiculo['ultimo'] = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else fecha
        
    # Registrar en historial
    historial = db_data.setdefault('historial_lavados', [])
    historial.insert(0, {
        'placa': placa,
        'fecha': fecha,
        'hora': hora_inicio or datetime.now().strftime('%H:%M'),
        'hora_inicio': hora_inicio,
        'hora_fin': hora_fin,
        'lavador': lavador,
        'tipo_lavado': tipo_lavado,
        'origen': 'dashboard_manual'
    })
    db_data['historial_lavados'] = historial[:200]
    

    # Actualizar horaDow con promedio móvil (actualiza el heatmap en tiempo real)
    if hora_inicio and fecha and tipo_lavado == 'General':
        try:
            import datetime as dt
            d_obj = dt.datetime.strptime(fecha, "%Y-%m-%d")
            dow   = d_obj.isoweekday() % 7   # 0=Domingo
            hh, mm = map(int, hora_inicio.split(':'))
            mins  = hh * 60 + mm

            hora_dow = vehiculo.setdefault('horaDow', {})
            dow_str  = str(dow)
            existing = hora_dow.get(dow_str)
            if existing:
                new_n = existing['n'] + 1
                new_m = round((existing['m'] * existing['n'] + mins) / new_n)
                new_s = f"{new_m // 60:02d}:{new_m % 60:02d}"
                hora_dow[dow_str] = {'s': new_s, 'm': new_m, 'n': new_n, 'std': existing.get('std', 0)}
            else:
                hora_dow[dow_str] = {'s': hora_inicio, 'm': mins, 'n': 1, 'std': 0}
        except Exception:
            pass

    db_data = _recalcular_stats(db_data)
    _save_full_db_data(db_data)
    return jsonify(db_data)

# ─── CRUD Vehículos ───────────────────────────────────────────────────────────
@app.route('/api/vehiculo/add', methods=['POST'])
@login_required
@admin_required
def add_vehiculo():
    data    = request.json or {}
    db_data = _get_full_db_data() or {'vehiculos': [], 'stats': {'n_meses': 3}, 'chartData': {}}

    placa = (data.get('placa') or '').strip().upper()
    if not placa:
        return jsonify({'error': 'La placa es obligatoria.'}), 400

    if any(v['placa'] == placa for v in db_data.get('vehiculos', [])):
        return jsonify({'error': 'Ya existe un vehículo con esa placa.'}), 400

    nuevo = {
        'placa':   placa,
        'mun':     data.get('mun', 'N/D').upper(),
        'tipo':    data.get('tipo', 'N/D').upper(),
        'ruta':    data.get('ruta', 'N/D').upper(),
        'sup':     data.get('sup', 'N/D').upper(),
        'lavGen':  0,
        'ultimo':  'NUNCA',
        'horaDow': {}
    }
    db_data.setdefault('vehiculos', []).append(nuevo)
    db_data = _recalcular_stats(db_data)
    _save_full_db_data(db_data)
    return jsonify(db_data)

@app.route('/api/vehiculo/edit', methods=['POST'])
@login_required
@admin_required
def edit_vehiculo():
    data  = request.json or {}
    placa = data.get('placa')

    db_data = _get_full_db_data()
    if not db_data:
        return jsonify({'error': 'No hay datos cargados.'}), 400

    vehiculo = next((v for v in db_data.get('vehiculos', []) if v['placa'] == placa), None)
    if not vehiculo:
        return jsonify({'error': f'Vehículo {placa} no encontrado.'}), 404

    vehiculo['mun']  = data.get('mun',  vehiculo['mun']).upper()
    vehiculo['tipo'] = data.get('tipo', vehiculo['tipo']).upper()
    vehiculo['ruta'] = data.get('ruta', vehiculo['ruta']).upper()
    vehiculo['sup']  = data.get('sup',  vehiculo['sup']).upper()

    _save_full_db_data(db_data)
    return jsonify(db_data)

@app.route('/api/vehiculo/remove', methods=['POST'])
@login_required
@admin_required
def remove_vehiculo():
    data  = request.json or {}
    placa = data.get('placa')

    db_data = _get_full_db_data()
    if not db_data:
        return jsonify({'error': 'No hay datos cargados.'}), 400

    db_data['vehiculos'] = [v for v in db_data.get('vehiculos', []) if v['placa'] != placa]
    db_data = _recalcular_stats(db_data)
    _save_full_db_data(db_data)
    return jsonify(db_data)

# ─── Exportar PDF ejecutivo ───────────────────────────────────────────────────
@app.route('/exportar-pdf', methods=['POST'])
@login_required
@admin_required
def exportar_pdf():
    """
    Genera y descarga el reporte PDF ejecutivo en base al rango de fechas y vehículos.
    Body JSON:
      - start_date:  'YYYY-MM-DD'
      - end_date:    'YYYY-MM-DD'
      - placas:      ['ABC123', ...]
      - max_dia:     int
      - responsable: str
    """
    from flask import send_file
    from pdf_report import generar_pdf

    data = request.json or {}
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    placas = data.get('placas', [])
    max_dia = int(data.get('max_dia', 4))
    responsable = data.get('responsable', '').strip()
    tipo_reporte = data.get('tipo_reporte', 'completo')

    if not start_date or not end_date:
        return jsonify({'error': 'Faltan fechas de inicio o fin.'}), 400

    db_data = _get_full_db_data()
    if not db_data:
        return jsonify({'error': 'Sin datos cargados. Sube un CSV primero.'}), 400

    vehiculos_a_programar = db_data.get('vehiculos', [])
    if placas:
        vehiculos_a_programar = [v for v in vehiculos_a_programar if v['placa'] in placas]

    prog_manual = db_data.get('programacion_manual', {})
    prog = generar_programacion(vehiculos_a_programar, start_date, end_date, max_dia, prog_manual)

    # Generar PDF
    pdf_bytes = generar_pdf(db_data, prog, start_date, end_date, responsable, tipo_reporte)

    buf = BytesIO(pdf_bytes)
    buf.seek(0)

    nombre_archivo = f"Reporte_{tipo_reporte.capitalize()}_{start_date}.pdf" if tipo_reporte == 'diagnostico' else f"Reporte_Programacion_{start_date}_al_{end_date}.pdf"
    return send_file(
        buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=nombre_archivo
    )

# ─── Exportar PDF de Nómina por Período ──────────────────────────────────────
@app.route('/api/exportar-nomina-pdf', methods=['POST'])
@login_required
@admin_required
def exportar_nomina_pdf():
    """
    Genera y descarga el PDF de liquidación de nómina del período indicado.
    Body JSON:
      - desde:       'YYYY-MM-DD' o ''
      - hasta:       'YYYY-MM-DD' o ''
      - responsable: str (quien firma)
    """
    from flask import send_file
    from pdf_report import generar_nomina_pdf

    data       = request.json or {}
    desde      = data.get('desde', '').strip()
    hasta      = data.get('hasta', '').strip()
    responsable = data.get('responsable', '').strip()

    db_data = _get_full_db_data()
    if not db_data:
        return jsonify({'error': 'Sin datos cargados.'}), 400

    config  = load_config()
    tarifas = config.get('tarifas', {'General': 0, 'Sencillo': 0, 'Enjuague': 0})
    historial = db_data.get('historial_lavados', [])

    pdf_bytes = generar_nomina_pdf(historial, tarifas, responsable, desde, hasta)

    buf = BytesIO(pdf_bytes)
    buf.seek(0)

    periodo = f'{desde}_al_{hasta}' if (desde and hasta) else (desde or hasta or 'completo')
    nombre_archivo = f'Nomina_FlotaUraba_{periodo}.pdf'

    return send_file(
        buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=nombre_archivo
    )


@app.route('/registro/<placa>', methods=['GET', 'POST'])
@login_required
def registro_qr(placa):
    import datetime as dt

    placa = placa.upper().strip()
    db_data = _get_full_db_data()

    if not db_data:
        return render_template('registro.html', vehiculo=None,
                               error='El sistema no tiene datos cargados. Contacta al administrador.')

    vehiculo = next((v for v in db_data.get('vehiculos', []) if v['placa'] == placa), None)
    if not vehiculo:
        return render_template('registro.html', vehiculo=None,
                               error=f'El vehículo con placa {placa} no fue encontrado en el sistema.')

    if request.method == 'POST':
        fecha = request.form.get('fecha', '').strip()
        hora_inicio  = request.form.get('hora_inicio', '').strip()
        hora_fin = request.form.get('hora_fin', '').strip()
        lavador = request.form.get('lavador', '').strip()
        tipo_lavado = request.form.get('tipo_lavado', '').strip()

        if not fecha or not hora_inicio or not hora_fin or not lavador or not tipo_lavado:
            return render_template('registro.html', vehiculo=vehiculo,
                                   error='Faltan datos obligatorios en el formulario.')

        if tipo_lavado == 'General':
            vehiculo['lavGen'] = vehiculo.get('lavGen', 0) + 1
            parts = fecha.split('-')
            vehiculo['ultimo'] = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else fecha
            
            try:
                d_obj = dt.datetime.strptime(fecha, '%Y-%m-%d')
                dow   = d_obj.isoweekday() % 7
                hh, mm = map(int, hora_inicio.split(':'))
                mins  = hh * 60 + mm
                hora_dow = vehiculo.setdefault('horaDow', {})
                dow_str  = str(dow)
                existing = hora_dow.get(dow_str)
                if existing:
                    new_n = existing['n'] + 1
                    new_m = round((existing['m'] * existing['n'] + mins) / new_n)
                    new_s = f"{new_m // 60:02d}:{new_m % 60:02d}"
                    hora_dow[dow_str] = {'s': new_s, 'm': new_m, 'n': new_n, 'std': existing.get('std', 0)}
                else:
                    hora_dow[dow_str] = {'s': hora_inicio, 'm': mins, 'n': 1, 'std': 0}
            except Exception:
                pass
        
        # Registrar en la base de datos de lavados de manera persistente e infinita
        nuevo_lavado = {
            'placa': placa,
            'fecha': fecha,
            'hora': hora_inicio,
            'hora_inicio': hora_inicio,
            'hora_fin': hora_fin,
            'lavador': lavador,
            'tipo_lavado': tipo_lavado,
            'origen': 'qr_registro'
        }
        database.add_lavado(nuevo_lavado)
        
        # Recargar historial para stats
        db_data['historial_lavados'] = database.get_all_lavados()

        import time as _time
        db_data['last_qr_event'] = {
            'placa':      placa,
            'lavador':    lavador,
            'tipo_lavado': tipo_lavado,
            'timestamp':  _time.time()
        }
        db_data = _recalcular_stats(db_data)
        _save_full_db_data(db_data)

        # Se guarda el evento al final para evitar race conditions con los clientes que sondean
        database.save_data('last_qr_event', db_data['last_qr_event'])

        try:
            fecha_fmt = dt.datetime.strptime(fecha, '%Y-%m-%d').strftime('%d/%m/%Y')
        except Exception:
            fecha_fmt = fecha

        return render_template('registro_ok.html',
                               placa=placa, fecha_fmt=fecha_fmt, hora_inicio=hora_inicio, 
                               hora_fin=hora_fin, lavador=lavador, tipo_lavado=tipo_lavado)

    return render_template('registro.html', vehiculo=vehiculo, error=None)

# ─── Último evento QR (para polling de notificaciones) ───────────────────────────────────
@app.route('/api/last-qr-event')
def api_last_qr_event():
    db_data = _get_full_db_data()
    if not db_data:
        return jsonify({'event': None})
    return jsonify({'event': db_data.get('last_qr_event')})

# ─── Configuración de Usuarios (API) ─────────────────────────────────────────────────────────────
@app.route('/api/users', methods=['GET'])
@login_required
@admin_required
def api_get_users():
    users = load_users()
    # Removemos contraseñas si queremos seguridad extra, pero por facilidad las mandamos para que el admin las vea
    return jsonify(users)

@app.route('/api/users/save', methods=['POST'])
@login_required
@admin_required
def api_save_user():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    role = data.get('role', 'lavador').strip()
    active = data.get('active', True)
    
    if not username or not password:
        return jsonify({'error': 'Usuario y contraseña son requeridos.'}), 400
        
    users = load_users()
    existing = next((u for u in users if u['username'] == username), None)
    
    if existing:
        existing['password'] = password
        existing['name'] = name
        existing['role'] = role
        existing['active'] = active
    else:
        users.append({
            'username': username,
            'password': password,
            'name': name,
            'role': role,
            'active': active
        })
        
    save_users(users)
    return jsonify({'success': True, 'users': users})

@app.route('/api/users/delete', methods=['POST'])
@login_required
@admin_required
def api_delete_user():
    data = request.json or {}
    username = data.get('username', '').strip()
    
    users = load_users()
    users = [u for u in users if u['username'] != username]
    save_users(users)
    return jsonify({'success': True, 'users': users})

@app.route('/api/config/tarifas', methods=['GET'])
@login_required
@admin_required
def api_get_tarifas():
    config = load_config()
    return jsonify(config.get('tarifas', {"General": 0, "Sencillo": 0, "Enjuague": 0}))

@app.route('/api/config/tarifas', methods=['POST'])
@login_required
@admin_required
def api_save_tarifas():
    data = request.json or {}
    config = load_config()
    config['tarifas'] = data
    save_config(config)
    return jsonify({'success': True, 'tarifas': data})

# ─── Arranque ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    threading.Timer(1.0, lambda: webbrowser.open('http://127.0.0.1:5001')).start()
    print('\n  * Dashboard corriendo en: http://127.0.0.1:5001\n')
    app.run(port=5001, debug=True, use_reloader=False)
