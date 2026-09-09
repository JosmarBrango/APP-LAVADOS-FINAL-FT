"""
routes/api_users.py
===================
Blueprint para gestión de usuarios y configuración:
  GET  /api/users
  POST /api/users/save
  POST /api/users/delete
  GET  /api/config/tarifas
  POST /api/config/tarifas
"""
import uuid
from flask import Blueprint, jsonify, request
from core.auth_helpers import (
    login_required, admin_required,
    load_users, save_users,
    load_config, save_config,
    get_system_lavadores,
    hash_password,
    TIPOS_VEHICULO,
)

api_users_bp = Blueprint('api_users', __name__)


def _sanitize_user(u: dict) -> dict:
    """Elimina contraseñas/hashes antes de enviar datos al cliente frontend."""
    safe = dict(u)
    safe['has_password'] = bool(u.get('password') and u.get('password') != 'N/A')
    safe.pop('password', None)
    return safe


@api_users_bp.route('/api/lavadores', methods=['GET'])
@login_required
def api_get_lavadores():
    lavadores = get_system_lavadores()
    return jsonify(lavadores)


@api_users_bp.route('/api/users', methods=['GET'])
@login_required
@admin_required
def api_get_users():
    return jsonify([_sanitize_user(u) for u in load_users()])


@api_users_bp.route('/api/users/save', methods=['POST'])
@login_required
@admin_required
def api_save_user():
    data      = request.json or {}
    username  = data.get('username', '').strip()
    password  = data.get('password', '').strip()
    name      = data.get('name', '').strip()
    role      = data.get('role', 'lavador').strip()
    documento = data.get('documento', '').strip()
    telefono  = data.get('telefono', '').strip()
    active    = data.get('active', True)

    if not name:
        return jsonify({'error': 'El nombre completo es obligatorio.'}), 400

    users    = load_users()
    existing = next((u for u in users if u['username'] == username), None) if username else None

    if role == 'lavador':
        if not username:
            username = f"lavador_{uuid.uuid4().hex[:6]}"
        password_val = "N/A"
    else:
        # Rol admin
        if not existing and (not username or not password):
            return jsonify({'error': 'Usuario y contraseña son requeridos para nuevas cuentas de administrador.'}), 400
        if existing and password:
            password_val = hash_password(password)
        elif existing and not password:
            password_val = existing.get('password', '')
        else:
            password_val = hash_password(password)

    if existing:
        existing['password']  = password_val
        existing['name']      = name
        existing['role']      = role
        existing['documento'] = documento
        existing['telefono']  = telefono
        existing['active']    = active
    else:
        users.append({
            'username':  username,
            'password':  password_val,
            'name':      name,
            'role':      role,
            'documento': documento,
            'telefono':  telefono,
            'active':    active,
        })

    save_users(users)
    return jsonify({'success': True, 'users': [_sanitize_user(u) for u in users]})


@api_users_bp.route('/api/users/delete', methods=['POST'])
@login_required
@admin_required
def api_delete_user():
    data     = request.json or {}
    username = data.get('username', '').strip()
    users    = [u for u in load_users() if u['username'] != username]
    save_users(users)
    return jsonify({'success': True, 'users': [_sanitize_user(u) for u in users]})


@api_users_bp.route('/api/config/tarifas', methods=['GET'])
@login_required
@admin_required
def api_get_tarifas():
    config = load_config()
    return jsonify(config.get('tarifas', {"General": 0, "Alistamiento": 0, "Motor": 0}))


@api_users_bp.route('/api/config/tarifas', methods=['POST'])
@login_required
@admin_required
def api_save_tarifas():
    data   = request.json or {}
    config = load_config()
    config['tarifas'] = data
    save_config(config)
    return jsonify({'success': True, 'tarifas': data})


@api_users_bp.route('/api/config/tipos-vehiculo', methods=['GET'])
@login_required
def api_get_tipos_vehiculo():
    """Retorna la lista canónica de tipos de vehículo del negocio."""
    return jsonify(TIPOS_VEHICULO)


@api_users_bp.route('/api/config/tarifas-vehiculo', methods=['GET'])
@login_required
@admin_required
def api_get_tarifas_vehiculo():
    config = load_config()
    return jsonify(config.get('tarifas_vehiculo', {tv: 0 for tv in TIPOS_VEHICULO}))


@api_users_bp.route('/api/config/tarifas-vehiculo', methods=['POST'])
@login_required
@admin_required
def api_save_tarifas_vehiculo():
    data   = request.json or {}
    config = load_config()
    config['tarifas_vehiculo'] = data
    save_config(config)
    return jsonify({'success': True, 'tarifas_vehiculo': data})
