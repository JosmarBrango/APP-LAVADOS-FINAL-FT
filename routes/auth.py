"""
routes/auth.py
==============
Blueprint para autenticación: login y logout.
"""
from flask import Blueprint, render_template, request, session, redirect, url_for
from core.auth_helpers import load_users, save_users, verify_password, hash_password

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        users = load_users()

        user = next(
            (u for u in users
             if u.get('username') == username
             and u.get('active', True)
             and verify_password(u.get('password', ''), password)),
            None
        )
        if user:
            # Migración transparente: si la contraseña aún no estaba hasheada, actualizarla
            stored_pwd = user.get('password', '')
            if not stored_pwd.startswith(('scrypt:', 'pbkdf2:', 'argon2:')):
                user['password'] = hash_password(password)
                save_users(users)

            session.permanent = True
            session['user'] = user['username']
            session['role'] = user.get('role', 'lavador')
            session['name'] = user.get('name', username)
            return redirect(url_for('vistas.index'))
        else:
            return render_template('login.html', error='Credenciales incorrectas o cuenta inactiva.')

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
