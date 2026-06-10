import os
import webbrowser
import threading
import json
from datetime import date, datetime
from io import BytesIO
from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
from services import process_csv, allowed_file, generar_programacion
import database

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_dev_key_12345')

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
LATEST_DATA_KEY = 'latest_upload'

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
    return db_data

# ─── Rutas principales ────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    data = database.get_data(LATEST_DATA_KEY)
    if data:
        return jsonify(data)
    return jsonify({'error': 'Sin datos. Sube un archivo CSV para comenzar.'})

# ─── MEJORA #3: /api/stats — KPIs siempre calculados en el backend ────────────
@app.route('/api/stats')
def get_stats():
    """Devuelve estadísticas recalculadas en tiempo real desde el backend."""
    db_data = database.get_data(LATEST_DATA_KEY)
    if not db_data:
        return jsonify({'error': 'Sin datos cargados.'}), 400

    db_data = _recalcular_stats(db_data)
    return jsonify(db_data['stats'])

# ─── MEJORA #1: /api/programacion — Algoritmo en Python ──────────────────────
@app.route('/api/programacion', methods=['POST'])
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

    db_data = database.get_data(LATEST_DATA_KEY)
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
def update_fecha_prog():
    data = request.json or {}
    placa = data.get('placa')
    nuevo_dia = data.get('nuevo_dia')  # format: 'YYYY-MM-DD' or None

    if not placa:
        return jsonify({'error': 'Falta la placa del vehículo.'}), 400

    db_data = database.get_data(LATEST_DATA_KEY)
    if not db_data:
        return jsonify({'error': 'Sin datos cargados.'}), 400

    prog_manual = db_data.setdefault('programacion_manual', {})

    if nuevo_dia is None or nuevo_dia == 'null' or nuevo_dia == '':
        if placa in prog_manual:
            del prog_manual[placa]
    else:
        prog_manual[placa] = str(nuevo_dia)

    database.save_data(LATEST_DATA_KEY, db_data)
    return jsonify({'success': True, 'placa': placa, 'nuevo_dia': nuevo_dia})

# ─── Upload CSV ───────────────────────────────────────────────────────────────
@app.route('/upload', methods=['POST'])
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

    database.save_data(LATEST_DATA_KEY, result)
    return jsonify(result)

# ─── Lavados (add / remove) ───────────────────────────────────────────────────
@app.route('/api/lavado/add', methods=['POST'])
def add_lavado():
    data = request.json or {}
    placa = data.get('placa')
    tipo  = data.get('tipo')  # 'lavGen', 'Sencillo', 'Enjuague'

    db_data = database.get_data(LATEST_DATA_KEY)
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

    database.save_data(LATEST_DATA_KEY, db_data)
    return jsonify(db_data)

@app.route('/api/lavado/remove', methods=['POST'])
def remove_lavado():
    data  = request.json or {}
    placa = data.get('placa')
    tipo  = data.get('tipo')

    db_data = database.get_data(LATEST_DATA_KEY)
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

    database.save_data(LATEST_DATA_KEY, db_data)
    return jsonify(db_data)

@app.route('/api/lavado/add_manual', methods=['POST'])
def add_lavado_manual():
    data  = request.json or {}
    placa = data.get('placa')
    fecha = data.get('fecha')
    hora  = data.get('hora')

    db_data = database.get_data(LATEST_DATA_KEY)
    if not db_data:
        return jsonify({'error': 'No hay datos cargados.'}), 400

    vehiculo = next((v for v in db_data.get('vehiculos', []) if v['placa'] == placa), None)
    if not vehiculo:
        return jsonify({'error': f'Vehículo {placa} no encontrado.'}), 404

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
        'hora': hora or datetime.now().strftime('%H:%M'),
        'origen': 'dashboard_manual'
    })
    db_data['historial_lavados'] = historial[:200]

    # Actualizar horaDow con promedio móvil (actualiza el heatmap en tiempo real)
    if hora and fecha:
        try:
            import datetime as dt
            d_obj = dt.datetime.strptime(fecha, "%Y-%m-%d")
            dow   = d_obj.isoweekday() % 7   # 0=Domingo
            hh, mm = map(int, hora.split(':'))
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
                hora_dow[dow_str] = {'s': hora, 'm': mins, 'n': 1, 'std': 0}
        except Exception:
            pass

    db_data = _recalcular_stats(db_data)
    database.save_data(LATEST_DATA_KEY, db_data)
    return jsonify(db_data)

# ─── CRUD Vehículos ───────────────────────────────────────────────────────────
@app.route('/api/vehiculo/add', methods=['POST'])
def add_vehiculo():
    data    = request.json or {}
    db_data = database.get_data(LATEST_DATA_KEY) or {'vehiculos': [], 'stats': {'n_meses': 3}, 'chartData': {}}

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
    database.save_data(LATEST_DATA_KEY, db_data)
    return jsonify(db_data)

@app.route('/api/vehiculo/edit', methods=['POST'])
def edit_vehiculo():
    data  = request.json or {}
    placa = data.get('placa')

    db_data = database.get_data(LATEST_DATA_KEY)
    if not db_data:
        return jsonify({'error': 'No hay datos cargados.'}), 400

    vehiculo = next((v for v in db_data.get('vehiculos', []) if v['placa'] == placa), None)
    if not vehiculo:
        return jsonify({'error': f'Vehículo {placa} no encontrado.'}), 404

    vehiculo['mun']  = data.get('mun',  vehiculo['mun']).upper()
    vehiculo['tipo'] = data.get('tipo', vehiculo['tipo']).upper()
    vehiculo['ruta'] = data.get('ruta', vehiculo['ruta']).upper()
    vehiculo['sup']  = data.get('sup',  vehiculo['sup']).upper()

    database.save_data(LATEST_DATA_KEY, db_data)
    return jsonify(db_data)

@app.route('/api/vehiculo/remove', methods=['POST'])
def remove_vehiculo():
    data  = request.json or {}
    placa = data.get('placa')

    db_data = database.get_data(LATEST_DATA_KEY)
    if not db_data:
        return jsonify({'error': 'No hay datos cargados.'}), 400

    db_data['vehiculos'] = [v for v in db_data.get('vehiculos', []) if v['placa'] != placa]
    db_data = _recalcular_stats(db_data)
    database.save_data(LATEST_DATA_KEY, db_data)
    return jsonify(db_data)

# ─── Exportar PDF ejecutivo ───────────────────────────────────────────────────
@app.route('/exportar-pdf', methods=['POST'])
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

    if not start_date or not end_date:
        return jsonify({'error': 'Faltan fechas de inicio o fin.'}), 400

    db_data = database.get_data(LATEST_DATA_KEY)
    if not db_data:
        return jsonify({'error': 'Sin datos cargados. Sube un CSV primero.'}), 400

    vehiculos_a_programar = db_data.get('vehiculos', [])
    if placas:
        vehiculos_a_programar = [v for v in vehiculos_a_programar if v['placa'] in placas]

    prog_manual = db_data.get('programacion_manual', {})
    prog = generar_programacion(vehiculos_a_programar, start_date, end_date, max_dia, prog_manual)

    # Generar PDF
    pdf_bytes = generar_pdf(db_data, prog, start_date, end_date, responsable)

    buf = BytesIO(pdf_bytes)
    buf.seek(0)

    nombre_archivo = f'Reporte_Lavados_{start_date}_al_{end_date}.pdf'
    return send_file(
        buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=nombre_archivo
    )

# ─── Registro por QR (página móvil para supervisores) ───────────────────────
@app.route('/registro/<placa>', methods=['GET', 'POST'])
def registro_qr(placa):
    """
    GET  — Muestra el formulario de registro de lavado (página móvil).
    POST — Procesa el registro y redirige a la página de confirmación.
    Accesible sin login: el supervisor escanea el QR y llena el formulario.
    """
    import datetime as dt

    placa = placa.upper().strip()
    db_data = database.get_data(LATEST_DATA_KEY)

    if not db_data:
        return render_template('registro.html', vehiculo=None,
                               error='El sistema no tiene datos cargados. Contacta al administrador.')

    vehiculo = next((v for v in db_data.get('vehiculos', []) if v['placa'] == placa), None)
    if not vehiculo:
        return render_template('registro.html', vehiculo=None,
                               error=f'El veh\u00edculo con placa {placa} no fue encontrado en el sistema.')

    if request.method == 'POST':
        fecha = request.form.get('fecha', '').strip()
        hora  = request.form.get('hora', '').strip()

        if not fecha or not hora:
            return render_template('registro.html', vehiculo=vehiculo,
                                   error='Debes ingresar la fecha y la hora del lavado.')

        # Incrementar lavados generales
        vehiculo['lavGen'] = vehiculo.get('lavGen', 0) + 1

        # Actualizar último lavado
        parts = fecha.split('-')
        vehiculo['ultimo'] = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else fecha
        
        # Registrar en historial
        historial = db_data.setdefault('historial_lavados', [])
        historial.insert(0, {
            'placa': placa,
            'fecha': fecha,
            'hora': hora,
            'origen': 'qr_registro'
        })
        db_data['historial_lavados'] = historial[:200]

        # Actualizar promedio horaDow con promedio móvil
        try:
            d_obj = dt.datetime.strptime(fecha, '%Y-%m-%d')
            dow   = d_obj.isoweekday() % 7   # 0=Domingo
            hh, mm = map(int, hora.split(':'))
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
                hora_dow[dow_str] = {'s': hora, 'm': mins, 'n': 1, 'std': 0}
        except Exception:
            pass

        db_data = _recalcular_stats(db_data)
        database.save_data(LATEST_DATA_KEY, db_data)

        # Calcular fin estimado para la p\u00e1gina de \u00e9xito
        try:
            hh2, mm2 = map(int, hora.split(':'))
            fin_m = hh2 * 60 + mm2 + 180
            fin_est = f"{fin_m // 60:02d}:{fin_m % 60:02d}"
        except Exception:
            fin_est = 'N/D'

        # Formatear fecha para mostrar
        try:
            fecha_fmt = dt.datetime.strptime(fecha, '%Y-%m-%d').strftime('%d/%m/%Y')
        except Exception:
            fecha_fmt = fecha

        return render_template('registro_ok.html',
                               placa=placa, fecha_fmt=fecha_fmt, hora=hora, fin_est=fin_est)

    return render_template('registro.html', vehiculo=vehiculo, error=None)

# ─── Arranque ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    database.init_db()
    threading.Timer(1.0, lambda: webbrowser.open('http://127.0.0.1:5001')).start()
    print('\n  * Dashboard corriendo en: http://127.0.0.1:5001\n')
    app.run(port=5001)
