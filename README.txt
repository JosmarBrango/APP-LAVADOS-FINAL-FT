========================================
 DASHBOARD DE LAVADOS — ZONA URABÁ
 App Flask — Instrucciones de uso
========================================

REQUISITOS
----------
- Python 3.9 o superior
- pip

INSTALACIÓN (solo la primera vez)
----------------------------------
1. Abre una terminal en la carpeta del proyecto

2. Crea un entorno virtual (recomendado):
   python -m venv venv

3. Actívalo:
   - Windows:   venv\Scripts\activate
   - Mac/Linux: source venv/bin/activate

4. Instala las dependencias:
   pip install -r requirements.txt

EJECUTAR LA APP
---------------
1. Activa el entorno virtual (si no está activo)
2. Corre el servidor:
   python app.py

3. Abre el navegador en:
   http://localhost:5000

USO
---
- Al abrir la app verás un estado vacío
- Haz clic en "Subir CSV" (botón arriba a la derecha)
- Selecciona el archivo BASE_PROG_URABA...csv
- El sistema procesa el archivo automáticamente
- El dashboard se actualiza con todos los datos

FORMATO DEL CSV ESPERADO
-------------------------
- Separador: punto y coma (;)
- Encoding: UTF-8 o Latin-1
- Primeras 2 filas: encabezados/metadatos (se saltan)
- Fila 3 en adelante: datos de vehículos
- Columnas requeridas:
    ITEM, PLACA, FECHA, MUNICIPIO, RUTA,
    TIPO DE VEHICULO, SUPERVISOR,
    HORA LLEGADA A LAVADERO,
    Enjuague, Sencillo , General

ESTRUCTURA DE CARPETAS
-----------------------
lavados_app/
├── app.py              ← servidor Flask
├── requirements.txt    ← dependencias
├── README.txt          ← este archivo
├── templates/
│   └── index.html      ← dashboard (HTML/JS)
├── uploads/            ← CSVs subidos (auto-creada)
└── data/
    └── processed.json  ← último CSV procesado (auto-creada)
