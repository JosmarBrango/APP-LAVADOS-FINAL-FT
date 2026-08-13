"""
routes/api_misc.py
==================
Blueprint para endpoints misceláneos:
  GET  /api/last-qr-event
  POST /upload
"""
import os
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
    if 'file' not in request.files:
        return jsonify({'error': 'No se recibió ningún archivo.'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío.'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Solo se aceptan archivos .csv'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    result = process_csv(filepath)

    if os.path.exists(filepath):
        os.remove(filepath)

    if 'error' in result:
        return jsonify(result), 422

    database.upsert_vehiculos(result.get('vehiculos', []))

    db_data = get_full_db_data()
    db_data = recalcular_stats(db_data)
    save_full_db_data(db_data)

    return jsonify(db_data)
