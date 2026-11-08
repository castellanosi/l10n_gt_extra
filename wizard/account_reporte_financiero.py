# -*- encoding: utf-8 -*-

import base64
import io
import time

import xlsxwriter

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..report import er_columnas

MODOS = [
    ('normal', 'Normal (un período)'),
    ('por_mes', 'Por mes'),
    ('acumulativo', 'Acumulativo (acumulado, mes y total)'),
]


def excel_financiero(cia, titulo, periodo, res):
    """Excel común del Estado de Resultados y del Balance General:
    encabezado, Resumen y Detalle por sección, columnas según el modo."""
    cols = res['columnas']
    ing = res['ingresos_col']

    f = io.BytesIO()
    libro = xlsxwriter.Workbook(f)
    hoja = libro.add_worksheet(titulo[:31])
    num = '#,##0.00;(#,##0.00);0.00'
    fmt = {
        (False, False): libro.add_format({'num_format': num}),
        (True, False): libro.add_format({'num_format': num, 'bold': True}),
        (False, True): libro.add_format({'num_format': '0.0'}),
        (True, True): libro.add_format({'num_format': '0.0', 'bold': True}),
    }
    fmt_total = {k: libro.add_format({'num_format': '0.0' if k else num, 'bold': True, 'top': 1})
                 for k in (False, True)}
    fmt_bold = libro.add_format({'bold': True})
    fmt_titulo = libro.add_format({'bold': True, 'font_size': 12})
    fmt_head = libro.add_format({'bold': True, 'bg_color': '#ede9f7', 'align': 'right'})
    fmt_head_izq = libro.add_format({'bold': True, 'bg_color': '#ede9f7'})
    fmt_seccion = libro.add_format({'bold': True, 'bg_color': '#f4f2fb'})

    hoja.write(0, 0, cia.name, fmt_titulo)
    hoja.write(1, 0, 'NIT {}'.format(cia.vat or ''), fmt_bold)
    hoja.write(2, 0, titulo, fmt_bold)
    hoja.write(3, 0, periodo)
    moneda = cia.currency_id.currency_unit_label or cia.currency_id.name
    hoja.write(4, 0, 'Expresado en {}'.format(moneda))

    heads = res['encabezados']
    hoja.set_column(0, 0, 14)
    hoja.set_column(1, 1, 38)
    for i, h in enumerate(heads):
        hoja.set_column(2 + i, 2 + i, 7 if h == '%' else 15)

    def encabezado(y, texto):
        hoja.write(y, 0, texto, fmt_head_izq)
        hoja.write(y, 1, '', fmt_head_izq)
        for i, h in enumerate(heads):
            hoja.write(y, 2 + i, h, fmt_head)

    def montos(y, valores, negrita, borde=False):
        for i, c in enumerate(er_columnas.celdas(valores, cols, ing)):
            hoja.write_number(y, 2 + i, c['v'], fmt_total[c['pct']] if borde else fmt[(negrita, c['pct'])])

    y = 6
    encabezado(y, 'Resumen')
    for r in res['resumen']:
        y += 1
        hoja.write(y, 0, r['etiqueta'], fmt_bold if r['negrita'] else None)
        montos(y, r['valores'], r['negrita'])

    y += 2
    encabezado(y, 'Detalle')
    hoja.freeze_panes(y + 1, 2)
    for sec in res['secciones']:
        if not sec['filas']:
            continue
        y += 1
        hoja.write(y, 0, sec['titulo'], fmt_seccion)
        hoja.write(y, 1, '', fmt_seccion)
        for r in sec['filas']:
            y += 1
            hoja.write(y, 0, r['codigo'])
            hoja.write(y, 1, r['nombre'])
            montos(y, r['valores'], False)
        y += 1
        hoja.write(y, 1, 'Total ' + sec['titulo'].lower(), fmt_bold)
        montos(y, sec['total'], True, borde=True)

    libro.close()
    return base64.b64encode(f.getvalue())


def nota_acumulativo(fecha_hasta, fecha_desde=False):
    """Texto de ayuda: qué mes y qué acumulado se van a mostrar."""
    if not fecha_hasta:
        return False
    ini = fecha_hasta.replace(day=1)
    texto = 'El «Mes» es el de la fecha final: {}.'.format(ini.strftime('%m/%Y'))
    if fecha_desde and fecha_desde < ini:
        anterior = ini.fromordinal(ini.toordinal() - 1)
        texto += ' El acumulado va del {} al {}.'.format(
            fecha_desde.strftime('%d/%m/%Y'), anterior.strftime('%d/%m/%Y'))
    texto += ' Si ese mes no tiene movimientos, la columna sale en 0.00.'
    return texto


class AsistenteReporteEstadoResultados(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_estado_resultados.wizard'
    _description = 'Estado de Resultados'

    folio_inicial = fields.Integer(string='Folio Inicial', required=True, default=1)
    fecha_desde = fields.Date(string="Fecha Inicial", required=True,
                              default=lambda self: time.strftime('%Y-01-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True,
                              default=lambda self: time.strftime('%Y-%m-%d'))
    modo = fields.Selection(
        MODOS, string='Tipo de reporte', required=True, default='normal',
        help='Por mes: una columna por cada mes del rango (máximo 12) y el total.\n'
             'Acumulativo: meses anteriores, mes de la fecha final y total, con %.')
    nota_modo = fields.Char(compute='_compute_nota_modo')
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    @api.depends('modo', 'fecha_desde', 'fecha_hasta')
    def _compute_nota_modo(self):
        for w in self:
            w.nota_modo = nota_acumulativo(w.fecha_hasta, w.fecha_desde) if w.modo == 'acumulativo' else False

    def _validar(self):
        for w in self:
            if w.fecha_desde > w.fecha_hasta:
                raise UserError('La fecha inicial no puede ser mayor que la fecha final.')
            if w.modo == 'por_mes' and len(er_columnas.meses_entre(
                    w.fecha_desde, w.fecha_hasta)) > er_columnas.MAX_MESES:
                raise UserError('El reporte por mes admite como máximo {} meses.'.format(
                    er_columnas.MAX_MESES))

    def _build_dict(self):
        return {
            'folio_inicial': self.folio_inicial,
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
            'modo': self.modo,
        }

    def _accion_reporte(self, form):
        self._validar()
        return self.env.ref('l10n_gt_extra.reporte_estado_resultados_wizard_report').with_context(
            landscape=self.modo != 'normal').report_action(
                self, data={'ids': [], 'model': self._name, 'form': form})

    def print_report(self):
        return self._accion_reporte(self._build_dict())

    def preview_report(self):
        action = self._accion_reporte(self.read()[0])
        action['report_type'] = 'qweb-html'
        return action

    def print_report_excel(self):
        self._validar()
        res = self.env['report.l10n_gt_extra.reporte_estado_resultados'].datos(self._build_dict())
        periodo = 'del {} al {}'.format(self.fecha_desde.strftime('%d/%m/%Y'),
                                        self.fecha_hasta.strftime('%d/%m/%Y'))
        self.write({'archivo': excel_financiero(self.env.company, 'Estado de Resultados', periodo, res),
                    'name': 'estado_resultados.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id, 'target': 'new'}


class AsistenteReporteBalanceGeneral(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_balance_general.wizard'
    _description = 'Balance General'

    folio_inicial = fields.Integer(string='Folio Inicial', required=True, default=1)
    fecha_hasta = fields.Date(string="Al corte del", required=True,
                              default=lambda self: time.strftime('%Y-%m-%d'))
    fecha_desde_er = fields.Date(
        string="Inicio período resultados", required=True,
        default=lambda self: time.strftime('%Y-01-01'),
        help="Fecha de inicio para calcular la utilidad/pérdida del período. "
             "En el modo Por mes, también es el primer mes que se muestra.",
    )
    modo = fields.Selection(
        MODOS, string='Tipo de reporte', required=True, default='normal',
        help='Por mes: saldo al cierre de cada mes, desde el inicio del período '
             'de resultados hasta el corte (máximo 12).\n'
             'Acumulativo: saldo anterior, movimiento del mes del corte y saldo al corte.')
    nota_modo = fields.Char(compute='_compute_nota_modo')
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    @api.depends('modo', 'fecha_hasta')
    def _compute_nota_modo(self):
        for w in self:
            if w.modo == 'acumulativo' and w.fecha_hasta:
                ini = w.fecha_hasta.replace(day=1)
                anterior = ini.fromordinal(ini.toordinal() - 1)
                w.nota_modo = ('El «Mes» es el de la fecha de corte: {}. «Saldo anterior» es el saldo '
                               'al {}. Si ese mes no tiene movimientos, la columna sale en 0.00.').format(
                    ini.strftime('%m/%Y'), anterior.strftime('%d/%m/%Y'))
            else:
                w.nota_modo = False

    def _validar(self):
        for w in self:
            if w.fecha_desde_er > w.fecha_hasta:
                raise UserError('El inicio del período de resultados no puede ser mayor que el corte.')
            if w.modo == 'por_mes' and len(er_columnas.meses_entre(
                    w.fecha_desde_er, w.fecha_hasta)) > er_columnas.MAX_MESES:
                raise UserError('El reporte por mes admite como máximo {} meses.'.format(
                    er_columnas.MAX_MESES))

    def _build_dict(self):
        return {
            'folio_inicial': self.folio_inicial,
            'fecha_hasta': self.fecha_hasta,
            'fecha_desde_er': self.fecha_desde_er,
            'modo': self.modo,
        }

    def _accion_reporte(self, form):
        self._validar()
        return self.env.ref('l10n_gt_extra.reporte_balance_general_wizard_report').with_context(
            landscape=self.modo != 'normal').report_action(
                self, data={'ids': [], 'model': self._name, 'form': form})

    def print_report(self):
        return self._accion_reporte(self._build_dict())

    def preview_report(self):
        action = self._accion_reporte(self.read()[0])
        action['report_type'] = 'qweb-html'
        return action

    def print_report_excel(self):
        self._validar()
        res = self.env['report.l10n_gt_extra.reporte_balance_general'].datos(self._build_dict())
        periodo = 'del {} al {}'.format(self.fecha_desde_er.strftime('%d/%m/%Y'),
                                        self.fecha_hasta.strftime('%d/%m/%Y'))
        self.write({'archivo': excel_financiero(self.env.company, 'Balance General', periodo, res),
                    'name': 'balance_general.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id, 'target': 'new'}


def excel_flujo(cia, periodo, res, filas):
    """Excel del Estado de Flujo de Efectivo, con las mismas filas del PDF."""
    f = io.BytesIO()
    libro = xlsxwriter.Workbook(f)
    hoja = libro.add_worksheet('Flujo de Efectivo')
    num = '#,##0.00;(#,##0.00);0.00'
    fmt_num = libro.add_format({'num_format': num})
    fmt_num_b = libro.add_format({'num_format': num, 'bold': True})
    fmt_num_t = libro.add_format({'num_format': num, 'bold': True, 'top': 1})
    fmt_num_c = libro.add_format({'num_format': num, 'font_color': '#555555'})
    fmt_num_i = libro.add_format({'num_format': num, 'italic': True})
    fmt_bold = libro.add_format({'bold': True})
    fmt_ital = libro.add_format({'italic': True})
    fmt_gris = libro.add_format({'font_color': '#555555', 'indent': 1})
    fmt_titulo = libro.add_format({'bold': True, 'font_size': 12})
    fmt_head = libro.add_format({'bold': True, 'bg_color': '#ede9f7', 'align': 'right'})
    fmt_head_izq = libro.add_format({'bold': True, 'bg_color': '#ede9f7'})
    fmt_seccion = libro.add_format({'bold': True, 'bg_color': '#f4f2fb'})

    hoja.write(0, 0, cia.name, fmt_titulo)
    hoja.write(1, 0, 'NIT {}'.format(cia.vat or ''), fmt_bold)
    hoja.write(2, 0, 'Estado de Flujo de Efectivo (método indirecto)', fmt_bold)
    hoja.write(3, 0, periodo)
    moneda = cia.currency_id.currency_unit_label or cia.currency_id.name
    hoja.write(4, 0, 'Expresado en {}'.format(moneda))

    heads = res['encabezados']
    hoja.set_column(0, 0, 14)
    hoja.set_column(1, 1, 52)
    hoja.set_column(2, 1 + len(heads), 15)
    y = 6
    hoja.write(y, 0, 'Cuenta', fmt_head_izq)
    hoja.write(y, 1, 'Concepto', fmt_head_izq)
    for i, h in enumerate(heads):
        hoja.write(y, 2 + i, h, fmt_head)
    hoja.freeze_panes(y + 1, 2)

    for fila in filas:
        y += 1
        tipo = fila['tipo']
        if tipo == 'seccion':
            hoja.write(y, 0, fila['etiqueta'], fmt_seccion)
            for i in range(1, 2 + len(heads)):
                hoja.write(y, i, '', fmt_seccion)
            continue
        if tipo == 'subtitulo':
            hoja.write(y, 1, fila['etiqueta'], fmt_ital)
            continue
        if tipo == 'cuenta':
            hoja.write(y, 0, fila['codigo'], fmt_gris)
            hoja.write(y, 1, fila['etiqueta'], fmt_gris)
            fmt_v = fmt_num_c
        elif tipo == 'nota':
            hoja.write(y, 1, fila['etiqueta'], fmt_ital)
            fmt_v = fmt_num_i
        elif tipo == 'total':
            hoja.write(y, 1, fila['etiqueta'], fmt_bold)
            fmt_v = fmt_num_t
        elif fila.get('negrita'):
            hoja.write(y, 1, fila['etiqueta'], fmt_bold)
            fmt_v = fmt_num_b
        else:
            hoja.write(y, 1, fila['etiqueta'])
            fmt_v = fmt_num
        for i, v in enumerate(fila['valores']):
            hoja.write_number(y, 2 + i, v, fmt_v)

    libro.close()
    return base64.b64encode(f.getvalue())


class AsistenteReporteFlujoEfectivo(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_flujo_efectivo.wizard'
    _description = 'Estado de Flujo de Efectivo'

    folio_inicial = fields.Integer(string='Folio Inicial', required=True, default=1)
    fecha_desde = fields.Date(string="Fecha Inicial", required=True,
                              default=lambda self: time.strftime('%Y-01-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True,
                              default=lambda self: time.strftime('%Y-%m-%d'))
    modo = fields.Selection(
        MODOS, string='Tipo de reporte', required=True, default='normal',
        help='Por mes: una columna por cada mes del rango (máximo 12) y el total.\n'
             'Acumulativo: meses anteriores, mes de la fecha final y total.')
    detalle = fields.Boolean(
        string='Detalle por cuenta', default=True,
        help='Muestra, debajo de cada renglón, las cuentas de donde sale la cifra.')
    nota_modo = fields.Char(compute='_compute_nota_modo')
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    @api.depends('modo', 'fecha_desde', 'fecha_hasta')
    def _compute_nota_modo(self):
        for w in self:
            w.nota_modo = nota_acumulativo(w.fecha_hasta, w.fecha_desde) if w.modo == 'acumulativo' else False

    def _validar(self):
        for w in self:
            if w.fecha_desde > w.fecha_hasta:
                raise UserError('La fecha inicial no puede ser mayor que la fecha final.')
            if w.modo == 'por_mes' and len(er_columnas.meses_entre(
                    w.fecha_desde, w.fecha_hasta)) > er_columnas.MAX_MESES:
                raise UserError('El reporte por mes admite como máximo {} meses.'.format(
                    er_columnas.MAX_MESES))

    def _build_dict(self):
        return {
            'folio_inicial': self.folio_inicial,
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
            'modo': self.modo,
            'detalle': self.detalle,
        }

    def _accion_reporte(self, form):
        self._validar()
        return self.env.ref('l10n_gt_extra.reporte_flujo_efectivo_wizard_report').with_context(
            landscape=self.modo != 'normal').report_action(
                self, data={'ids': [], 'model': self._name, 'form': form})

    def print_report(self):
        return self._accion_reporte(self._build_dict())

    def preview_report(self):
        action = self._accion_reporte(self.read()[0])
        action['report_type'] = 'qweb-html'
        return action

    def print_report_excel(self):
        self._validar()
        res, filas = self.env['report.l10n_gt_extra.reporte_flujo_efectivo'].filas(self._build_dict())
        periodo = 'del {} al {}'.format(self.fecha_desde.strftime('%d/%m/%Y'),
                                        self.fecha_hasta.strftime('%d/%m/%Y'))
        self.write({'archivo': excel_flujo(self.env.company, periodo, res, filas),
                    'name': 'flujo_efectivo.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id, 'target': 'new'}
