from flask import Blueprint, render_template, session, request
import datetime as dt
from utils import login_required
from models import Vehiculo, Configuracion

pages_bp = Blueprint('pages', __name__)

@pages_bp.route('/')
@login_required
def index():
    user_info = {
        'username': session.get('user'),
        'role': session.get('role'),
        'name': session.get('name')
    }
    return render_template('index.html', user=user_info)

@pages_bp.route('/registro/<placa>', methods=['GET', 'POST'])
@login_required
def registro_qr(placa):
    placa = placa.upper().strip()
    vehiculo = Vehiculo.query.filter_by(placa=placa).first()

    if not vehiculo:
        return render_template('registro.html', vehiculo=None,
                               error=f'El vehículo con placa {placa} no fue encontrado en el sistema.')

    if request.method == 'POST':
        # Esta lógica se delegó al frontend enviando a la API `/api/lavado/add`
        pass

    return render_template('registro.html', vehiculo=vehiculo.placa)
