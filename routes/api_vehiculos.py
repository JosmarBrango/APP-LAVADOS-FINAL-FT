"""
routes/api_vehiculos.py
=======================
Blueprint para CRUD de vehículos:
  GET  /api/tipos-vehiculo
  POST /api/vehiculo/add
  POST /api/vehiculo/edit
  POST /api/vehiculo/remove
"""
from flask import Blueprint, jsonify, request
from core.auth_helpers import login_required, admin_required
from core.stats import get_full_db_data, save_full_db_data, recalcular_stats
import database

api_vehiculos_bp = Blueprint('api_vehiculos', __name__)

TIPOS_VEHICULO = [
    'DOBLE', 'SENCILLO', 'VOLQUETA', 'NPR', 'NQR',
    'NQR ESTACA', 'MOTOCARRO', 'CAMIONETA', 'NHR'
]


@api_vehiculos_bp.route('/api/tipos-vehiculo')
@login_required
def api_tipos_vehiculo():
    """Retorna la lista canónica de tipos de vehículo."""
    return jsonify(TIPOS_VEHICULO)


@api_vehiculos_bp.route('/api/vehiculo/add', methods=['POST'])
@login_required
@admin_required
def add_vehiculo():
    data    = request.json or {}
    db_data = get_full_db_data() or {
        'vehiculos': [], 'stats': {'n_meses': 3}, 'chartData': {}
    }

    placa = (data.get('placa') or '').strip().upper()
    if not placa:
        return jsonify({'error': 'La placa es obligatoria.'}), 400

    if any(v['placa'] == placa for v in db_data.get('vehiculos', [])):
        return jsonify({'error': 'Ya existe un vehículo con esa placa.'}), 400

    nuevo = {
        'placa':   placa,
        'mun':     data.get('mun',  'N/D').upper(),
        'tipo':    data.get('tipo', 'N/D').upper(),
        'ruta':    data.get('ruta', 'N/D').upper(),
        'sup':     data.get('sup',  'N/D').upper(),
        'lavGen':  0,
        'ultimo':  'NUNCA',
        'horaDow': {},
    }
    db_data.setdefault('vehiculos', []).append(nuevo)
    db_data = recalcular_stats(db_data)
    save_full_db_data(db_data)
    return jsonify(db_data)


@api_vehiculos_bp.route('/api/vehiculo/edit', methods=['POST'])
@login_required
@admin_required
def edit_vehiculo():
    data  = request.json or {}
    placa = data.get('placa')

    db_data = get_full_db_data()
    if not db_data:
        return jsonify({'error': 'No hay datos cargados.'}), 400

    vehiculo = next((v for v in db_data.get('vehiculos', []) if v['placa'] == placa), None)
    if not vehiculo:
        return jsonify({'error': f'Vehículo {placa} no encontrado.'}), 404

    vehiculo['mun']  = data.get('mun',  vehiculo['mun']).upper()
    vehiculo['tipo'] = data.get('tipo', vehiculo['tipo']).upper()
    vehiculo['ruta'] = data.get('ruta', vehiculo['ruta']).upper()
    vehiculo['sup']  = data.get('sup',  vehiculo['sup']).upper()

    save_full_db_data(db_data)
    return jsonify(db_data)


@api_vehiculos_bp.route('/api/vehiculo/remove', methods=['POST'])
@login_required
@admin_required
def remove_vehiculo():
    data  = request.json or {}
    placa = data.get('placa')

    if placa:
        database.remove_vehiculo(placa)

    db_data = get_full_db_data()
    if not db_data:
        return jsonify({'error': 'No hay datos cargados.'}), 400

    db_data = recalcular_stats(db_data)
    save_full_db_data(db_data)
    return jsonify(db_data)
