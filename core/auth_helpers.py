"""
core/auth_helpers.py
====================
Decoradores de autenticación y funciones de carga/guardado
de usuarios y configuración del sistema.
"""
import os
import json
from functools import wraps
from flask import session, redirect, url_for, request, jsonify


# ─── Rutas de archivos ────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, '..', 'data')


def _data_path(filename: str) -> str:
    return os.path.join(_DATA_DIR, filename)


# ─── Usuarios ─────────────────────────────────────────────────────────────────
def load_users() -> list:
    path = _data_path('usuarios_app.json')
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_users(users: list) -> None:
    path = _data_path('usuarios_app.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


# ─── Configuración (tarifas, etc.) ────────────────────────────────────────────
def load_config() -> dict:
    path = _data_path('config.json')
    if not os.path.exists(path):
        return {"tarifas": {"General": 0, "Sencillo": 0, "Enjuague": 0}}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg.setdefault('tarifas', {})
        for t in ['General', 'Sencillo', 'Enjuague']:
            cfg['tarifas'].setdefault(t, 0)
        return cfg
    except Exception:
        return {"tarifas": {"General": 0, "Sencillo": 0, "Enjuague": 0}}


def save_config(config_data: dict) -> None:
    path = _data_path('config.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)


# ─── Decoradores de autenticación ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'error': 'Sesión no iniciada o expirada'}), 401
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session.get('role') != 'admin':
            return jsonify({'error': 'Acceso denegado: solo administradores'}), 403
        return f(*args, **kwargs)
    return decorated_function
