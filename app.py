import os
from flask import Flask
from flask_socketio import SocketIO
from models import db

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_dev_key_12345')

# Configuración Base de Datos SQLAlchemy
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'app.db')

# Si existe DATABASE_URL (ej. en Render con Supabase), se usa. Sino, usa SQLite local.
db_uri = os.environ.get('DATABASE_URL')
if db_uri:
    # SQLAlchemy requiere que la URL de Postgres empiece con postgresql://
    if db_uri.startswith('postgres://'):
        db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración Uploads
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Inicializar extensiones
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Importar y registrar Blueprints
from routes.auth import auth_bp
from routes.pages import pages_bp
from routes.api import api_bp, upload_bp
from routes.reportes import reportes_bp

app.register_blueprint(auth_bp)
app.register_blueprint(pages_bp)
app.register_blueprint(api_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(reportes_bp)

with app.app_context():
    # En caso de que se haya borrado la DB, se crean las tablas vacías.
    # Los datos ya fueron migrados por migrate_to_sqlalchemy.py
    db.create_all()
    
    # Crear usuario administrador por defecto si la tabla está vacía
    from models import User
    if User.query.count() == 0:
        admin_user = User(username='admin', password='123', name='Administrador Principal', role='admin', active=True)
        db.session.add(admin_user)
        db.session.commit()
        print("Usuario administrador creado por defecto.")

if __name__ == '__main__':
    print(f" * Dashboard corriendo en: http://127.0.0.1:5001 (WebSockets)")
    socketio.run(app, debug=True, host='127.0.0.1', port=5001, use_reloader=False, allow_unsafe_werkzeug=True)
