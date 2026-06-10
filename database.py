import sqlite3
import json
import os

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
    c.execute('''
        CREATE TABLE IF NOT EXISTS store (
            key VARCHAR(255) PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_data(key, data_dict):
    conn = get_connection()
    c = conn.cursor()
    val_str = json.dumps(data_dict, ensure_ascii=False)
    
    if DATABASE_URL:
        # PostgreSQL syntax
        c.execute('''
            INSERT INTO store (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value
        ''', (key, val_str))
    else:
        # SQLite syntax
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
