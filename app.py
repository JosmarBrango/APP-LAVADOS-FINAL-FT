"""
app.py
======
Punto de entrada de la aplicación Flask.
Solo inicializa la app, registra los blueprints y arranca el servidor.
Toda la lógica de negocio vive en core/ y routes/.
"""
import os
import logging
import threading
import webbrowser
from datetime import timedelta

from flask import Flask, send_from_directory
import database

# ─── Logging ─────────────────────────────────────────────────────────────────
class NoQREventFilter(logging.Filter):
    def filter(self, record):
        return 'GET /api/last-qr-event' not in record.getMessage()

logging.getLogger('werkzeug').addFilter(NoQREventFilter())

# ─── Creación de la app ────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_dev_key_12345')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Deshabilitar caché estática en desarrollo

# ─── Configuración de Sesión Segura ──────────────────────────────────────────
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ─── Inicialización ───────────────────────────────────────────────────────────
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'evidencias'), exist_ok=True)
database.init_db()

# ─── Ruta para servir fotos de evidencia ─────────────────────────────────────
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), app.config['UPLOAD_FOLDER'])
    return send_from_directory(upload_dir, filename)

# ─── Registro de blueprints ───────────────────────────────────────────────────
from routes.auth             import auth_bp
from routes.vistas           import vistas_bp
from routes.api_data         import api_data_bp
from routes.api_lavados      import api_lavados_bp
from routes.api_vehiculos    import api_vehiculos_bp
from routes.api_users        import api_users_bp
from routes.api_programacion import api_programacion_bp
from routes.api_misc         import api_misc_bp

app.register_blueprint(auth_bp)
app.register_blueprint(vistas_bp)
app.register_blueprint(api_data_bp)
app.register_blueprint(api_lavados_bp)
app.register_blueprint(api_vehiculos_bp)
app.register_blueprint(api_users_bp)
app.register_blueprint(api_programacion_bp)
app.register_blueprint(api_misc_bp)

# ─── Arranque ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    threading.Timer(1.0, lambda: webbrowser.open('http://127.0.0.1:5001')).start()
    print('\n  * Dashboard corriendo en: http://127.0.0.1:5001\n')
    app.run(port=5001, debug=True, use_reloader=False)
