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
                hora_llegada VARCHAR(20),
                hora_inicio VARCHAR(20),
                hora_fin VARCHAR(20),
                tiempo_espera INTEGER,
                tiempo_lavado INTEGER,
                lavadores TEXT,
                tipo_lavado VARCHAR(50),
                municipio VARCHAR(100),
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
                hora_llegada VARCHAR(20),
                hora_inicio VARCHAR(20),
                hora_fin VARCHAR(20),
                tiempo_espera INTEGER,
                tiempo_lavado INTEGER,
                lavadores TEXT,
                tipo_lavado VARCHAR(50),
                municipio VARCHAR(100),
                origen VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    conn.commit()

    # ─── MIGRACIÓN AUTOMÁTICA DE COLUMNAS NUEVAS ────────────────────────────────
    # Agrega columnas nuevas si no existen (para bases de datos ya existentes)
    _migrate_columns(conn, c)

    # MIGRACIÓN AUTOMÁTICA DE DATOS LEGACY (de store 'latest_upload')
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
            for h in reversed(historial):
                placa = h.get('placa', '')
                fecha = h.get('fecha', '')
                hora = h.get('hora', '')
                h_llegada = h.get('hora_llegada', '')
                h_ini = h.get('hora_inicio', '')
                h_fin = h.get('hora_fin', '')
                lavador = h.get('lavador', '')
                lavadores_str = json.dumps([lavador] if lavador else [], ensure_ascii=False)
                tipo = h.get('tipo_lavado', '')
                mun = h.get('municipio', '')
                origen = h.get('origen', '')
                
                if DATABASE_URL:
                    c.execute('''INSERT INTO lavados 
                                 (placa, fecha, hora, hora_llegada, hora_inicio, hora_fin, lavadores, tipo_lavado, municipio, origen) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''', 
                                 (placa, fecha, hora, h_llegada, h_ini, h_fin, lavadores_str, tipo, mun, origen))
                else:
                    c.execute('''INSERT INTO lavados 
                                 (placa, fecha, hora, hora_llegada, hora_inicio, hora_fin, lavadores, tipo_lavado, municipio, origen) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                                 (placa, fecha, hora, h_llegada, h_ini, h_fin, lavadores_str, tipo, mun, origen))
                                 
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


def _migrate_columns(conn, c):
    """Agrega columnas nuevas a la tabla lavados si no existen (migración no destructiva)."""
    new_columns = [
        ('hora_llegada', 'VARCHAR(20)'),
        ('tiempo_espera', 'INTEGER'),
        ('tiempo_lavado', 'INTEGER'),
        ('lavadores', 'TEXT'),
        ('municipio', 'VARCHAR(100)'),
    ]
    
    if DATABASE_URL:
        # PostgreSQL: consultar columnas existentes
        c.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'lavados'
        """)
        existing_cols = {row[0] for row in c.fetchall()}
    else:
        # SQLite: PRAGMA table_info
        c.execute("PRAGMA table_info(lavados)")
        existing_cols = {row[1] for row in c.fetchall()}
    
    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            try:
                c.execute(f"ALTER TABLE lavados ADD COLUMN {col_name} {col_type}")
                conn.commit()
                print(f"Columna '{col_name}' añadida a la tabla lavados.")
            except Exception as e:
                print(f"No se pudo añadir columna '{col_name}': {e}")


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

def remove_vehiculo(placa):
    """Elimina un vehículo de la base de datos."""
    conn = get_connection()
    c = conn.cursor()
    if DATABASE_URL:
        c.execute('DELETE FROM vehiculos WHERE placa = %s', (placa,))
    else:
        c.execute('DELETE FROM vehiculos WHERE placa = ?', (placa,))
    conn.commit()
    conn.close()

# ─── Operaciones Lavados ─────────────────────────────────────────────────────
def add_lavado(lavado_dict):
    """
    lavado_dict puede contener:
      - placa, fecha, hora, hora_llegada, hora_inicio, hora_fin
      - lavadores (lista de strings), tipo_lavado, municipio, origen
      - tiempo_espera, tiempo_lavado (calculados automáticamente si no vienen)
    """
    conn = get_connection()
    c = conn.cursor()
    
    hora_llegada = lavado_dict.get('hora_llegada', '') or ''
    hora_inicio  = lavado_dict.get('hora_inicio', '') or ''
    hora_fin     = lavado_dict.get('hora_fin', '') or ''
    
    # Calcular tiempos automáticamente si no se proveen
    tiempo_espera = lavado_dict.get('tiempo_espera')
    if tiempo_espera is None and hora_llegada and hora_inicio:
        tiempo_espera = _calc_minutos(hora_llegada, hora_inicio)
    
    tiempo_lavado = lavado_dict.get('tiempo_lavado')
    if tiempo_lavado is None and hora_inicio and hora_fin:
        tiempo_lavado = _calc_minutos(hora_inicio, hora_fin)
    
    # Lavadores: siempre guardados como JSON array
    lavadores = lavado_dict.get('lavadores', [])
    # Compatibilidad: si viene un string 'lavador' (legado), convertirlo a lista
    if not lavadores:
        lavador_str = lavado_dict.get('lavador', '')
        lavadores = [lavador_str] if lavador_str else []
    lavadores_json = json.dumps(lavadores, ensure_ascii=False)
    
    p = (
        lavado_dict.get('placa', ''),
        lavado_dict.get('fecha', ''),
        lavado_dict.get('hora', '') or hora_inicio,
        hora_llegada,
        hora_inicio,
        hora_fin,
        tiempo_espera,
        tiempo_lavado,
        lavadores_json,
        lavado_dict.get('tipo_lavado', ''),
        lavado_dict.get('municipio', ''),
        lavado_dict.get('origen', '')
    )
    
    if DATABASE_URL:
        c.execute('''INSERT INTO lavados 
                     (placa, fecha, hora, hora_llegada, hora_inicio, hora_fin, tiempo_espera, tiempo_lavado, lavadores, tipo_lavado, municipio, origen) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''', p)
    else:
        c.execute('''INSERT INTO lavados 
                     (placa, fecha, hora, hora_llegada, hora_inicio, hora_fin, tiempo_espera, tiempo_lavado, lavadores, tipo_lavado, municipio, origen) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', p)
    conn.commit()
    conn.close()

def add_lavados_batch(lavados_list):
    """Inserta una lista de lavados en lote."""
    if not lavados_list:
        return
    conn = get_connection()
    c = conn.cursor()
    for l in lavados_list:
        lavadores_json = json.dumps(l.get('lavadores', []), ensure_ascii=False)
        p = (
            l.get('placa', ''),
            l.get('fecha', ''),
            l.get('hora', '') or l.get('hora_inicio', ''),
            l.get('hora_llegada', ''),
            l.get('hora_inicio', ''),
            l.get('hora_fin', ''),
            l.get('tiempo_espera'),
            l.get('tiempo_lavado'),
            lavadores_json,
            l.get('tipo_lavado', ''),
            l.get('municipio', ''),
            l.get('origen', 'csv_import')
        )
        if DATABASE_URL:
            c.execute('''INSERT INTO lavados 
                         (placa, fecha, hora, hora_llegada, hora_inicio, hora_fin, tiempo_espera, tiempo_lavado, lavadores, tipo_lavado, municipio, origen) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''', p)
        else:
            c.execute('''INSERT INTO lavados 
                         (placa, fecha, hora, hora_llegada, hora_inicio, hora_fin, tiempo_espera, tiempo_lavado, lavadores, tipo_lavado, municipio, origen) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', p)
    conn.commit()
    conn.close()

def remove_lavado(lavado_id):
    """Elimina un lavado por su ID."""
    conn = get_connection()
    c = conn.cursor()
    if DATABASE_URL:
        c.execute('DELETE FROM lavados WHERE id=%s', (lavado_id,))
    else:
        c.execute('DELETE FROM lavados WHERE id=?', (lavado_id,))
    conn.commit()
    conn.close()

def update_lavado_fecha(lavado_id, nueva_fecha):
    """Actualiza la fecha de un lavado por su ID."""
    conn = get_connection()
    c = conn.cursor()
    if DATABASE_URL:
        c.execute('UPDATE lavados SET fecha=%s WHERE id=%s', (nueva_fecha, lavado_id))
    else:
        c.execute('UPDATE lavados SET fecha=? WHERE id=?', (nueva_fecha, lavado_id))
    conn.commit()
    conn.close()

def get_all_lavados(desde=None, hasta=None):
    """
    Retorna todos los lavados, opcionalmente filtrados por rango de fechas.
    Formato: desde='YYYY-MM-DD', hasta='YYYY-MM-DD'
    """
    conn = get_connection()
    c = conn.cursor()
    
    if desde and hasta:
        if DATABASE_URL:
            c.execute('''SELECT id, placa, fecha, hora, hora_llegada, hora_inicio, hora_fin, 
                                tiempo_espera, tiempo_lavado, lavadores, tipo_lavado, municipio, origen 
                         FROM lavados WHERE fecha >= %s AND fecha <= %s ORDER BY id DESC''', (desde, hasta))
        else:
            c.execute('''SELECT id, placa, fecha, hora, hora_llegada, hora_inicio, hora_fin, 
                                tiempo_espera, tiempo_lavado, lavadores, tipo_lavado, municipio, origen 
                         FROM lavados WHERE fecha >= ? AND fecha <= ? ORDER BY id DESC''', (desde, hasta))
    else:
        c.execute('''SELECT id, placa, fecha, hora, hora_llegada, hora_inicio, hora_fin, 
                            tiempo_espera, tiempo_lavado, lavadores, tipo_lavado, municipio, origen 
                     FROM lavados ORDER BY id DESC''')
    
    rows = c.fetchall()
    conn.close()
    
    lavados = []
    for r in rows:
        lavadores_raw = r[9]
        try:
            lavadores = json.loads(lavadores_raw) if lavadores_raw else []
        except Exception:
            lavadores = [lavadores_raw] if lavadores_raw else []
        
        lavados.append({
            'id': r[0],
            'placa': r[1],
            'fecha': r[2],
            'hora': r[3],
            'hora_llegada': r[4] or '',
            'hora_inicio': r[5] or '',
            'hora_fin': r[6] or '',
            'tiempo_espera': r[7],
            'tiempo_lavado': r[8],
            'lavadores': lavadores,
            # Compatibilidad legado: campo 'lavador' como string del primer lavador
            'lavador': lavadores[0] if lavadores else '',
            'tipo_lavado': r[10] or '',
            'municipio': r[11] or '',
            'origen': r[12] or ''
        })
    return lavados


def _calc_minutos(h_ini, h_fin):
    """Calcula la diferencia en minutos entre dos strings HH:MM."""
    try:
        hi_h, hi_m = map(int, h_ini.split(':'))
        hf_h, hf_m = map(int, h_fin.split(':'))
        mi = hi_h * 60 + hi_m
        mf = hf_h * 60 + hf_m
        if mf < mi:
            mf += 24 * 60
        return mf - mi
    except Exception:
        return None
