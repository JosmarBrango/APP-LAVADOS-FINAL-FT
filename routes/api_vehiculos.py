"""
routes/api_vehiculos.py
=======================
Blueprint para CRUD de vehículos:
  GET    /api/tipos-vehiculo
  GET    /api/vehiculos
  POST   /api/vehiculo (y /api/vehiculo/add)
  PUT    /api/vehiculo (y POST /api/vehiculo/edit)
  DELETE /api/vehiculo (y POST /api/vehiculo/remove)
"""
from flask import Blueprint, jsonify, request
from core.auth_helpers import login_required, admin_required
from core.stats import get_full_db_data, save_full_db_data, recalcular_stats
import database

api_vehiculos_bp = Blueprint('api_vehiculos', __name__)

TIPOS_VEHICULO = [
    'DOBLE TROQUE',
    'SENCILLO',
    'VOLQUETA DOBLE',
    'VOLQUETA SENCILLA',
    'VOLQUETA',
    'NQR COMPACTADOR',
    'NPR ESTACA',
    'NQR ESTACA',
    'NQR PLATON',
    'NPR',
    'NQR',
    'NHR',
    'CAMIONETA',
    'MOTOCARRO',
    'DOBLE'
]


@api_vehiculos_bp.route('/api/tipos-vehiculo', methods=['GET'])
@login_required
def api_tipos_vehiculo():
    """Retorna la lista canónica de tipos de vehículo combinada con los ya registrados."""
    db_data = get_full_db_data() or {}
    existing_tipos = {
        (v.get('tipo') or '').strip().upper()
        for v in db_data.get('vehiculos', [])
        if v.get('tipo')
    }
    merged = list(TIPOS_VEHICULO)
    for t in sorted(existing_tipos):
        if t and t not in merged:
            merged.append(t)
    return jsonify(merged)


@api_vehiculos_bp.route('/api/vehiculos', methods=['GET'])
@login_required
def get_vehiculos():
    db_data = get_full_db_data() or {}
    return jsonify(db_data.get('vehiculos', []))


@api_vehiculos_bp.route('/api/vehiculo', methods=['POST'])
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

    if any(v.get('placa', '').upper() == placa for v in db_data.get('vehiculos', [])):
        return jsonify({'error': f'Ya existe un vehículo con la placa {placa}.'}), 400

    nuevo = {
        'placa':   placa,
        'mun':     str(data.get('mun',  'N/D')).strip().upper(),
        'tipo':    str(data.get('tipo', 'N/D')).strip().upper(),
        'ruta':    str(data.get('ruta', 'N/D')).strip().upper(),
        'sup':     str(data.get('sup',  'N/D')).strip().upper(),
        'lavGen':  0,
        'ultimo':  'NUNCA',
        'horaDow': {},
    }
    db_data.setdefault('vehiculos', []).append(nuevo)
    db_data = recalcular_stats(db_data)
    save_full_db_data(db_data)
    return jsonify({'success': True, 'vehiculo': nuevo, 'data': db_data})


@api_vehiculos_bp.route('/api/vehiculo', methods=['PUT'])
@api_vehiculos_bp.route('/api/vehiculo/edit', methods=['POST'])
@login_required
@admin_required
def edit_vehiculo():
    data  = request.json or {}
    placa = (data.get('placa') or '').strip().upper()

    if not placa:
        return jsonify({'error': 'La placa es obligatoria.'}), 400

    db_data = get_full_db_data()
    if not db_data:
        return jsonify({'error': 'No hay datos cargados en el sistema.'}), 400

    vehiculo = next((v for v in db_data.get('vehiculos', []) if v.get('placa', '').upper() == placa), None)
    if not vehiculo:
        return jsonify({'error': f'Vehículo {placa} no encontrado.'}), 404

    if 'mun' in data:
        vehiculo['mun']  = str(data.get('mun',  vehiculo.get('mun', ''))).strip().upper()
    if 'tipo' in data:
        vehiculo['tipo'] = str(data.get('tipo', vehiculo.get('tipo', ''))).strip().upper()
    if 'ruta' in data:
        vehiculo['ruta'] = str(data.get('ruta', vehiculo.get('ruta', ''))).strip().upper()
    if 'sup' in data:
        vehiculo['sup']  = str(data.get('sup',  vehiculo.get('sup', ''))).strip().upper()

    db_data = recalcular_stats(db_data)
    save_full_db_data(db_data)
    return jsonify({'success': True, 'vehiculo': vehiculo, 'data': db_data})


@api_vehiculos_bp.route('/api/vehiculo', methods=['DELETE'])
@api_vehiculos_bp.route('/api/vehiculo/remove', methods=['POST'])
@login_required
@admin_required
def remove_vehiculo():
    data  = request.json or {}
    placa = (data.get('placa') or '').strip().upper()

    if not placa:
        return jsonify({'error': 'La placa es obligatoria.'}), 400

    database.remove_vehiculo(placa)

    db_data = get_full_db_data()
    if not db_data:
        return jsonify({'error': 'No hay datos cargados en el sistema.'}), 400

    # Asegurar filtrado en memoria
    db_data['vehiculos'] = [v for v in db_data.get('vehiculos', []) if v.get('placa', '').upper() != placa]

    db_data = recalcular_stats(db_data)
    save_full_db_data(db_data)
    return jsonify({'success': True, 'data': db_data})
