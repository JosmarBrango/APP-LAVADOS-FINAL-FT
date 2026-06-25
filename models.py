from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(120))
    role = db.Column(db.String(20), default='lavador')
    active = db.Column(db.Boolean, default=True)

class Vehiculo(db.Model):
    __tablename__ = 'vehiculos'
    placa = db.Column(db.String(50), primary_key=True)
    municipio = db.Column(db.String(100), default='N/D')
    tipo = db.Column(db.String(50), default='N/D')
    ruta = db.Column(db.String(100), default='N/D')
    supervisor = db.Column(db.String(100), default='N/D')
    
    # Relación con lavados
    lavados = db.relationship('Lavado', backref='vehiculo', lazy=True, cascade="all, delete-orphan")

class Lavado(db.Model):
    __tablename__ = 'lavados'
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(50), db.ForeignKey('vehiculos.placa'), nullable=False)
    fecha = db.Column(db.String(20), nullable=False)
    hora = db.Column(db.String(20), nullable=False)
    hora_inicio = db.Column(db.String(20))
    hora_fin = db.Column(db.String(20))
    lavador = db.Column(db.String(100))
    tipo_lavado = db.Column(db.String(50))
    origen = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Configuracion(db.Model):
    __tablename__ = 'store'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
