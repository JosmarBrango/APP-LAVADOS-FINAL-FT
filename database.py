import sqlite3
import json
import os
import datetime

DATABASE_URL = os.environ.get('DATABASE_URL')

# Determinar la ruta absoluta de la base de datos relativa a este archivo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'data', 'database.db')

def get_connection():
    if DATABASE_URL:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    else:
        return sqlite3.connect(DB_FILE)

def init_db():
    if not DATABASE_URL:
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    
    conn = get_connection()
    c = conn.cursor()
    
    # Tabla key-value para configuraciones (stats precalculados, programacion manual)
    c.execute('''
        CREATE TABLE IF NOT EXISTS store (
            key VARCHAR(255) PRIMARY KEY,
            value TEXT
        )
    ''')

    if DATABASE_URL:
        # PostgreSQL syntax
        c.execute('''
            CREATE TABLE IF NOT EXISTS vehiculos (
                placa VARCHAR(50) PRIMARY KEY,
                data TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS lavados (
                id SERIAL PRIMARY KEY,
                placa VARCHAR(50),
                fecha VARCHAR(20),
                hora VARCHAR(20),
                hora_inicio VARCHAR(20),
                hora_fin VARCHAR(20),
                lavador VARCHAR(100),
                tipo_lavado VARCHAR(50),
                origen VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        # SQLite syntax
        c.execute('''
            CREATE TABLE IF NOT EXISTS vehiculos (
                placa VARCHAR(50) PRIMARY KEY,
                data TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS lavados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                placa VARCHAR(50),
                fecha VARCHAR(20),
                hora VARCHAR(20),
                hora_inicio VARCHAR(20),
                hora_fin VARCHAR(20),
                lavador VARCHAR(100),
                tipo_lavado VARCHAR(50),
                origen VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    conn.commit()

    # MIGRACIÓN AUTOMÁTICA
    if DATABASE_URL:
        c.execute("SELECT value FROM store WHERE key = %s", ('latest_upload',))
    else:
        c.execute("SELECT value FROM store WHERE key = ?", ('latest_upload',))
        
    row = c.fetchone()
    if row:
        print("Realizando migración automática de datos a tablas relacionales...")
        try:
            old_data = json.loads(row[0])
            
            # 1. Migrar vehículos
            vehiculos = old_data.get('vehiculos', [])
            for v in vehiculos:
                placa = v.get('placa')
                val_str = json.dumps(v, ensure_ascii=False)
                if DATABASE_URL:
                    c.execute('INSERT INTO vehiculos (placa, data) VALUES (%s, %s) ON CONFLICT (placa) DO UPDATE SET data=EXCLUDED.data', (placa, val_str))
                else:
                    c.execute('INSERT INTO vehiculos (placa, data) VALUES (?, ?) ON CONFLICT(placa) DO UPDATE SET data=excluded.data', (placa, val_str))
                    
            # 2. Migrar historial de lavados
            historial = old_data.get('historial_lavados', [])
            for h in reversed(historial): # Más antiguos primero para mantener orden cronológico
                placa = h.get('placa', '')
                fecha = h.get('fecha', '')
                hora = h.get('hora', '')
                h_ini = h.get('hora_inicio', '')
                h_fin = h.get('hora_fin', '')
                lavador = h.get('lavador', '')
                tipo = h.get('tipo_lavado', '')
                origen = h.get('origen', '')
                
                if DATABASE_URL:
                    c.execute('''INSERT INTO lavados 
                                 (placa, fecha, hora, hora_inicio, hora_fin, lavador, tipo_lavado, origen) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''', 
                                 (placa, fecha, hora, h_ini, h_fin, lavador, tipo, origen))
                else:
                    c.execute('''INSERT INTO lavados 
                                 (placa, fecha, hora, hora_inicio, hora_fin, lavador, tipo_lavado, origen) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                                 (placa, fecha, hora, h_ini, h_fin, lavador, tipo, origen))
                                 
            # 3. Guardar otras configuraciones importantes
            prog_str = json.dumps(old_data.get('programacion_manual', {}), ensure_ascii=False)
            if DATABASE_URL:
                c.execute('INSERT INTO store (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value', ('programacion_manual', prog_str))
                c.execute("DELETE FROM store WHERE key = %s", ('latest_upload',))
            else:
                c.execute('INSERT INTO store (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('programacion_manual', prog_str))
                c.execute("DELETE FROM store WHERE key = ?", ('latest_upload',))
                
            conn.commit()
            print("Migración completada exitosamente.")
        except Exception as e:
            print(f"Error durante migración: {e}")
            conn.rollback()

    conn.close()

# ─── Operaciones key-value (store) ─────────────────────────────────────────────
def save_data(key, data_dict):
    conn = get_connection()
    c = conn.cursor()
    val_str = json.dumps(data_dict, ensure_ascii=False)
    
    if DATABASE_URL:
        c.execute('''
            INSERT INTO store (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value
        ''', (key, val_str))
    else:
        c.execute('''
            INSERT INTO store (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        ''', (key, val_str))
        
    conn.commit()
    conn.close()

def get_data(key):
    conn = get_connection()
    c = conn.cursor()
    
    if DATABASE_URL:
        c.execute('SELECT value FROM store WHERE key = %s', (key,))
    else:
        c.execute('SELECT value FROM store WHERE key = ?', (key,))
        
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

# ─── Operaciones Vehículos ───────────────────────────────────────────────────
def upsert_vehiculos(vehiculos_list):
    """Inserta o actualiza una lista de vehículos."""
    conn = get_connection()
    c = conn.cursor()
    for v in vehiculos_list:
        placa = v.get('placa')
        val_str = json.dumps(v, ensure_ascii=False)
        if DATABASE_URL:
            c.execute('INSERT INTO vehiculos (placa, data) VALUES (%s, %s) ON CONFLICT (placa) DO UPDATE SET data=EXCLUDED.data', (placa, val_str))
        else:
            c.execute('INSERT INTO vehiculos (placa, data) VALUES (?, ?) ON CONFLICT(placa) DO UPDATE SET data=excluded.data', (placa, val_str))
    conn.commit()
    conn.close()

def get_all_vehiculos():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT data FROM vehiculos')
    rows = c.fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]

# ─── Operaciones Lavados ─────────────────────────────────────────────────────
def add_lavado(lavado_dict):
    """
    lavado_dict debe contener: placa, fecha, hora, hora_inicio, hora_fin, lavador, tipo_lavado, origen
    """
    conn = get_connection()
    c = conn.cursor()
    
    p = (
        lavado_dict.get('placa', ''),
        lavado_dict.get('fecha', ''),
        lavado_dict.get('hora', ''),
        lavado_dict.get('hora_inicio', ''),
        lavado_dict.get('hora_fin', ''),
        lavado_dict.get('lavador', ''),
        lavado_dict.get('tipo_lavado', ''),
        lavado_dict.get('origen', '')
    )
    
    if DATABASE_URL:
        c.execute('''INSERT INTO lavados 
                     (placa, fecha, hora, hora_inicio, hora_fin, lavador, tipo_lavado, origen) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''', p)
    else:
        c.execute('''INSERT INTO lavados 
                     (placa, fecha, hora, hora_inicio, hora_fin, lavador, tipo_lavado, origen) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', p)
    conn.commit()
    conn.close()

def remove_lavado(placa, fecha, hora):
    """Elimina un lavado específico buscando por placa, fecha y hora."""
    conn = get_connection()
    c = conn.cursor()
    if DATABASE_URL:
        c.execute('DELETE FROM lavados WHERE placa=%s AND fecha=%s AND hora=%s', (placa, fecha, hora))
    else:
        c.execute('DELETE FROM lavados WHERE placa=? AND fecha=? AND hora=?', (placa, fecha, hora))
    conn.commit()
    conn.close()

def get_all_lavados():
    conn = get_connection()
    c = conn.cursor()
    # ORDENAR de más reciente a más antiguo (comportamiento actual esperado por frontend)
    c.execute('SELECT id, placa, fecha, hora, hora_inicio, hora_fin, lavador, tipo_lavado, origen FROM lavados ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    
    lavados = []
    for r in rows:
        lavados.append({
            'id': r[0],
            'placa': r[1],
            'fecha': r[2],
            'hora': r[3],
            'hora_inicio': r[4],
            'hora_fin': r[5],
            'lavador': r[6],
            'tipo_lavado': r[7],
            'origen': r[8]
        })
    return lavados
