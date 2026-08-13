"""
routes/auth.py
==============
Blueprint para autenticación: login y logout.
"""
from flask import Blueprint, render_template, request, session, redirect, url_for
from core.auth_helpers import load_users

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()

        user = next(
            (u for u in users
             if u['username'] == username
             and u['password'] == password
             and u.get('active', True)),
            None
        )
        if user:
            session['user'] = user['username']
            session['role'] = user['role']
            session['name'] = user.get('name', username)
            return redirect(url_for('vistas.index'))
        else:
            return render_template('login.html', error='Credenciales incorrectas o cuenta inactiva.')

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
