"""
routes/vistas.py
================
Blueprint para vistas HTML: index principal y registro por QR.
"""
import datetime as dt
from flask import Blueprint, render_template, request, session, redirect, url_for

from core.auth_helpers import login_required, load_users, get_system_lavadores
from core.stats import get_full_db_data, save_full_db_data, recalcular_stats
import database

vistas_bp = Blueprint('vistas', __name__)


@vistas_bp.route('/')
@login_required
def index():
    return render_template('index.html', user=session)


@vistas_bp.route('/registro/<placa>', methods=['GET', 'POST'])
@login_required
def registro_qr(placa):
    placa = placa.upper().strip()
    db_data = get_full_db_data()

    if not db_data:
        return render_template(
            'registro.html', vehiculo=None,
            error='El sistema no tiene datos cargados. Contacta al administrador.'
        )

    vehiculo = next((v for v in db_data.get('vehiculos', []) if v.get('placa', '').upper().strip() == placa), None)
    if not vehiculo:
        return render_template(
            'registro.html', vehiculo=None,
            error=f'El vehículo con placa {placa} no fue encontrado en el sistema.'
        )

    # Municipio limpio: si no tiene o es inválido, se deja en blanco
    invalid_muns = {'', '0', '0.0', '0:00', '00:00', 'NAN', 'NONE', 'N/D', 'NULL', 'UNDEFINED'}
    mun_actual = (vehiculo.get('mun') or '').strip().upper()
    vehiculo['mun_clean'] = '' if mun_actual in invalid_muns else mun_actual

    # Lista consolidada y garantizada de lavadores del sistema
    lavadores_sistema = get_system_lavadores(db_data)

    if request.method == 'POST':
        fecha        = request.form.get('fecha', '').strip()
        hora_llegada = request.form.get('hora_llegada', '').strip()
        hora_inicio  = request.form.get('hora_inicio', '').strip()
        hora_fin     = request.form.get('hora_fin', '').strip()
        tipo_lavado  = request.form.get('tipo_lavado', '').strip()
        municipio    = request.form.get('municipio', '').strip().upper()

        lavadores = [l.strip().upper() for l in request.form.getlist('lavadores') if l.strip()]
        if not lavadores:
            lav = request.form.get('lavador', '').strip()
            lavadores = [lav.upper()] if lav else []

        if not fecha or not hora_inicio or not hora_fin or not lavadores or not tipo_lavado:
            return render_template(
                'registro.html', vehiculo=vehiculo,
                lavadores_sistema=lavadores_sistema,
                error='Faltan datos obligatorios en el formulario (debes seleccionar fecha, horas, tipo de lavado y al menos un lavador).'
            )

        if tipo_lavado == 'General':
            vehiculo['lavGen'] = vehiculo.get('lavGen', 0) + 1
            parts = fecha.split('-')
            vehiculo['ultimo'] = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else fecha

            try:
                d_obj = dt.datetime.strptime(fecha, '%Y-%m-%d')
                dow = d_obj.isoweekday() % 7
                ref_hora = hora_llegada or hora_inicio
                hh, mm = map(int, ref_hora.split(':'))
                mins = hh * 60 + mm
                hora_dow = vehiculo.setdefault('horaDow', {})
                dow_str = str(dow)
                existing = hora_dow.get(dow_str)
                if existing:
                    new_n = existing['n'] + 1
                    new_m = round((existing['m'] * existing['n'] + mins) / new_n)
                    new_s = f"{new_m // 60:02d}:{new_m % 60:02d}"
                    hora_dow[dow_str] = {'s': new_s, 'm': new_m, 'n': new_n, 'std': existing.get('std', 0)}
                else:
                    hora_dow[dow_str] = {'s': ref_hora, 'm': mins, 'n': 1, 'std': 0}
            except Exception:
                pass

        if municipio:
            vehiculo['mun'] = municipio.upper()
            database.upsert_vehiculos([vehiculo])

        def calc_diff(h1, h2):
            if not h1 or not h2:
                return None
            try:
                h1_h, h1_m = map(int, h1.split(':'))
                h2_h, h2_m = map(int, h2.split(':'))
                diff = (h2_h * 60 + h2_m) - (h1_h * 60 + h1_m)
                if diff < 0:
                    diff += 24 * 60
                return diff
            except Exception:
                return None

        t_espera = calc_diff(hora_llegada, hora_inicio)
        t_lavado = calc_diff(hora_inicio, hora_fin)

        nuevo_lavado = {
            'placa':        placa,
            'fecha':        fecha,
            'hora':         hora_llegada or hora_inicio,
            'hora_llegada': hora_llegada,
            'hora_inicio':  hora_inicio,
            'hora_fin':     hora_fin,
            'tiempo_espera': t_espera,
            'tiempo_lavado': t_lavado,
            'lavadores':    lavadores,
            'tipo_lavado':  tipo_lavado,
            'municipio':    municipio,
            'origen':       'qr_registro',
        }
        database.add_lavado(nuevo_lavado)
        db_data['historial_lavados'] = database.get_all_lavados()

        import time as _time
        db_data['last_qr_event'] = {
            'placa':       placa,
            'lavadores':   lavadores,
            'tipo_lavado': tipo_lavado,
            'timestamp':   _time.time(),
        }
        db_data = recalcular_stats(db_data)
        save_full_db_data(db_data)
        database.save_data('last_qr_event', db_data['last_qr_event'])

        try:
            fecha_fmt = dt.datetime.strptime(fecha, '%Y-%m-%d').strftime('%d/%m/%Y')
        except Exception:
            fecha_fmt = fecha

        return render_template(
            'registro_ok.html',
            placa=placa, fecha_fmt=fecha_fmt,
            hora_llegada=hora_llegada, hora_inicio=hora_inicio,
            hora_fin=hora_fin, lavadores=lavadores, tipo_lavado=tipo_lavado
        )

    return render_template('registro.html', vehiculo=vehiculo,
                           lavadores_sistema=lavadores_sistema, error=None)
