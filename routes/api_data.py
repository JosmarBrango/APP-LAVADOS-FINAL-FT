"""
routes/api_data.py
==================
Blueprint para endpoints de datos y estadísticas:
  GET  /api/data
  GET  /api/stats
  GET  /api/meses-disponibles
"""
from flask import Blueprint, jsonify, request
from core.auth_helpers import login_required
from core.stats import get_full_db_data, recalcular_stats

api_data_bp = Blueprint('api_data', __name__)


@api_data_bp.route('/api/data')
@login_required
def get_data():
    data = get_full_db_data()
    if data:
        data = recalcular_stats(data)
        return jsonify(data)
    return jsonify({'error': 'Sin datos. Sube un archivo CSV para comenzar.'})


@api_data_bp.route('/api/stats')
@login_required
def get_stats():
    """
    Devuelve estadísticas recalculadas en tiempo real desde el backend.

    Query params:
      ?mes=YYYY-MM  => stats del mes específico
      ?mes=TOTAL    => stats acumuladas históricas
      (sin ?mes)    => mes actual (por defecto)
    """
    mes_filtro = request.args.get('mes', None)
    db_data = get_full_db_data()
    if not db_data:
        return jsonify({'error': 'Sin datos cargados.'}), 400

    db_data = recalcular_stats(db_data, mes_filtro=mes_filtro)
    return jsonify(db_data['stats'])


@api_data_bp.route('/api/meses-disponibles')
@login_required
def get_meses_disponibles():
    """
    Devuelve la lista de meses (YYYY-MM) que tienen al menos un lavado,
    ordenados de más reciente a más antiguo.
    """
    MESES_ES = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]
    db_data  = get_full_db_data()
    historial = db_data.get('historial_lavados', []) if db_data else []

    meses_set = set()
    for h in historial:
        fecha = (h.get('fecha', '') or '').strip()
        if len(fecha) >= 7:
            meses_set.add(fecha[:7])

    resultado = []
    for m in sorted(meses_set, reverse=True):
        try:
            year, month = map(int, m.split('-'))
            label = f"{MESES_ES[month - 1]} {year}"
        except Exception:
            label = m
        resultado.append({'valor': m, 'label': label})

    return jsonify(resultado)
