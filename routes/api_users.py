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
)

api_users_bp = Blueprint('api_users', __name__)


@api_users_bp.route('/api/lavadores', methods=['GET'])
@login_required
def api_get_lavadores():
    users = load_users()
    lavadores = [
        (u.get('name') or u['username']).strip().upper()
        for u in users
        if u.get('role') == 'lavador' and u.get('active', True)
    ]
    return jsonify(lavadores)


@api_users_bp.route('/api/users', methods=['GET'])
@login_required
@admin_required
def api_get_users():
    return jsonify(load_users())


@api_users_bp.route('/api/users/save', methods=['POST'])
@login_required
@admin_required
def api_save_user():
    data     = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name     = data.get('name', '').strip()
    role     = data.get('role', 'lavador').strip()
    active   = data.get('active', True)

    if role == 'lavador' and not username:
        username = f"lavador_{uuid.uuid4().hex[:6]}"
        password = "N/A"

    if not username or not password:
        return jsonify({'error': 'Usuario y contraseña son requeridos para administradores.'}), 400

    users    = load_users()
    existing = next((u for u in users if u['username'] == username), None)

    if existing:
        existing['password'] = password
        existing['name']     = name
        existing['role']     = role
        existing['active']   = active
    else:
        users.append({
            'username': username,
            'password': password,
            'name':     name,
            'role':     role,
            'active':   active,
        })

    save_users(users)
    return jsonify({'success': True, 'users': users})


@api_users_bp.route('/api/users/delete', methods=['POST'])
@login_required
@admin_required
def api_delete_user():
    data     = request.json or {}
    username = data.get('username', '').strip()
    users    = [u for u in load_users() if u['username'] != username]
    save_users(users)
    return jsonify({'success': True, 'users': users})


@api_users_bp.route('/api/config/tarifas', methods=['GET'])
@login_required
@admin_required
def api_get_tarifas():
    config = load_config()
    return jsonify(config.get('tarifas', {"General": 0, "Sencillo": 0, "Enjuague": 0}))


@api_users_bp.route('/api/config/tarifas', methods=['POST'])
@login_required
@admin_required
def api_save_tarifas():
    data   = request.json or {}
    config = load_config()
    config['tarifas'] = data
    save_config(config)
    return jsonify({'success': True, 'tarifas': data})
