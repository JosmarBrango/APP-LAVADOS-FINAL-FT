from flask import Blueprint, request, redirect, url_for, render_template, session, jsonify
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()
        if user and user.password == password and user.active:
            session['user'] = user.username
            session['role'] = user.role
            session['name'] = user.name
            next_url = request.args.get('next')
            return redirect(next_url or url_for('pages.index'))
        else:
            return render_template('login.html', error='Credenciales inválidas o usuario inactivo.')

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
