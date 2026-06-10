import app as flask_app
import database

client = flask_app.app.test_client()

print("--- Testing Case 1: Accented characters in responsable ---")
response = client.get('/exportar-pdf?mes=2026-07&max_dia=4&responsable=Ramón%20Díaz')
print("Status:", response.status_code)
if response.status_code != 200:
    print("Error:", response.data.decode('utf-8')[:500])
else:
    print("Success. PDF length:", len(response.data))

print("\n--- Testing Case 2: Empty/Missing mes (should default) ---")
response = client.get('/exportar-pdf?mes=&max_dia=4&responsable=')
print("Status:", response.status_code)
if response.status_code != 200:
    print("Error:", response.data.decode('utf-8')[:500])
else:
    print("Success. PDF length:", len(response.data))

print("\n--- Testing Case 3: Empty Database ---")
# Temporary clear database
database.init_db()
import sqlite3
conn = sqlite3.connect(database.DB_FILE)
c = conn.cursor()
c.execute("DELETE FROM store WHERE key='latest_upload'")
conn.commit()
conn.close()

response = client.get('/exportar-pdf?mes=2026-07&max_dia=4&responsable=Test')
print("Status:", response.status_code)
print("Data:", response.data.decode('utf-8'))

# Restore DB data from grandparent database
import shutil
shutil.copyfile('../../data/database.db', database.DB_FILE)
print("\nRestored DB.")
