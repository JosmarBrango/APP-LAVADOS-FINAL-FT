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
    # 1. Intentar cargar desde la base de datos relacional (PostgreSQL / SQLite)
    try:
        import database
        users_db = database.get_data('usuarios_app')
        if users_db and isinstance(users_db, list) and len(users_db) > 0:
            return users_db
    except Exception as e:
        print(f"Advertencia: No se pudo leer usuarios de base de datos: {e}")

    # 2. Fallback al archivo local usuarios_app.json
    path = _data_path('usuarios_app.json')
    users = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                users = json.load(f)
        except Exception:
            users = []

    # 3. Si se leyeron del archivo, migrarlos automáticamente a la BD para persistencia
    if users:
        try:
            import database
            database.save_data('usuarios_app', users)
        except Exception:
            pass

    return users


def save_users(users: list) -> None:
    # 1. Guardar en base de datos (PostgreSQL / SQLite)
    try:
        import database
        database.save_data('usuarios_app', users)
    except Exception as e:
        print(f"Error guardando usuarios en base de datos: {e}")

    # 2. Guardar en archivo local como respaldo
    try:
        path = _data_path('usuarios_app.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ─── Configuración (tarifas, etc.) ────────────────────────────────────────────
def load_config() -> dict:
    # 1. Intentar cargar desde la base de datos
    try:
        import database
        cfg_db = database.get_data('config')
        if cfg_db and isinstance(cfg_db, dict):
            cfg_db.setdefault('tarifas', {})
            for t in ['General', 'Sencillo', 'Enjuague']:
                cfg_db['tarifas'].setdefault(t, 0)
            return cfg_db
    except Exception:
        pass

    # 2. Fallback a archivo config.json
    path = _data_path('config.json')
    default_cfg = {"tarifas": {"General": 0, "Sencillo": 0, "Enjuague": 0}}
    if not os.path.exists(path):
        return default_cfg
    try:
        with open(path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg.setdefault('tarifas', {})
        for t in ['General', 'Sencillo', 'Enjuague']:
            cfg['tarifas'].setdefault(t, 0)
        # Sincronizar a BD
        try:
            import database
            database.save_data('config', cfg)
        except Exception:
            pass
        return cfg
    except Exception:
        return default_cfg


def save_config(config_data: dict) -> None:
    try:
        import database
        database.save_data('config', config_data)
    except Exception:
        pass
    try:
        path = _data_path('config.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ─── Helper de Lavadores del Sistema ──────────────────────────────────────────
def get_system_lavadores(db_data: dict = None) -> list:
    """
    Retorna la lista consolidada y deduplicada de todos los lavadores disponibles:
    1. Usuarios activos con rol 'lavador' en el sistema (base de datos o archivo).
    2. Lavadores que aparecen en el historial de lavados o estadísticas.
    """
    lavadores_set = set()
    invalid_names = {'', 'N/D', '0', '0:00', '0.0', 'NAN', 'NONE', 'NULL', 'UNDEFINED', 'N/A', 'SIN ASIGNAR'}

    # 1. De usuarios registrados con rol lavador
    users = load_users()
    for u in users:
        if u.get('role') == 'lavador' and u.get('active', True):
            name = (u.get('name') or u.get('username') or '').strip().upper()
            if name and name not in invalid_names:
                lavadores_set.add(name)

    # 2. De historial y estadísticas de lavados
    try:
        import database
        if db_data is None:
            from core.stats import get_full_db_data
            db_data = get_full_db_data()

        if db_data:
            # Desde lavadores_stats
            for k in (db_data.get('lavadores_stats') or {}).keys():
                name = str(k).strip().upper()
                if name and name not in invalid_names:
                    lavadores_set.add(name)

            # Desde historial_lavados
            for h in (db_data.get('historial_lavados') or []):
                for l in (h.get('lavadores') or []):
                    name = str(l).strip().upper()
                    if name and name not in invalid_names:
                        lavadores_set.add(name)
                lav_single = str(h.get('lavador') or '').strip().upper()
                if lav_single and lav_single not in invalid_names:
                    lavadores_set.add(lav_single)
    except Exception as e:
        print(f"Advertencia al consolidar lavadores de historial: {e}")

    # Fallback directo al archivo usuarios_app.json si aún está vacío
    if not lavadores_set:
        try:
            path = _data_path('usuarios_app.json')
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    u_list = json.load(f)
                    for u in u_list:
                        if u.get('role') == 'lavador' and u.get('active', True):
                            name = (u.get('name') or u.get('username') or '').strip().upper()
                            if name and name not in invalid_names:
                                lavadores_set.add(name)
        except Exception:
            pass

    return sorted(list(lavadores_set))


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
