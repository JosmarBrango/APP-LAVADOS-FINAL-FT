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

from flask import Flask
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

# ─── Inicialización ───────────────────────────────────────────────────────────
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
database.init_db()

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
