"""
routes/api_misc.py
==================
Blueprint para endpoints misceláneos:
  GET  /api/last-qr-event
  POST /upload
"""
import os
import logging
from flask import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename
from core.auth_helpers import login_required, admin_required
from core.stats import get_full_db_data, save_full_db_data, recalcular_stats
from services import process_csv, allowed_file
import database

api_misc_bp = Blueprint('api_misc', __name__)


@api_misc_bp.route('/api/last-qr-event')
def api_last_qr_event():
    db_data = get_full_db_data()
    if not db_data:
        return jsonify({'event': None})
    return jsonify({'event': db_data.get('last_qr_event')})


@api_misc_bp.route('/upload', methods=['POST'])
@login_required
@admin_required
def upload():
    filepath = None
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No se recibió ningún archivo.'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nombre de archivo vacío.'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'Solo se aceptan archivos en formato .csv'}), 400

        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        if not os.path.isabs(upload_folder):
            upload_folder = os.path.join(current_app.root_path, upload_folder)
        os.makedirs(upload_folder, exist_ok=True)

        filename = secure_filename(file.filename)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)

        result = process_csv(filepath)

        if 'error' in result:
            return jsonify(result), 422

        # Guardar vehículos importados preservando los existentes
        vehiculos_nuevos = result.get('vehiculos', [])
        database.upsert_vehiculos(vehiculos_nuevos)

        # Recalcular estadísticas y persistir
        db_data = get_full_db_data()
        db_data = recalcular_stats(db_data)
        save_full_db_data(db_data)

        return jsonify({'status': 'ok', 'total_vehiculos': len(vehiculos_nuevos), 'db_data': db_data})

    except Exception as e:
        logging.exception("Error en /upload:")
        return jsonify({'error': f'Error en el servidor al procesar el archivo: {str(e)}'}), 500
    finally:
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

