# -*- encoding: utf-8 -*-

from odoo import models, fields
import time
import xlsxwriter
import base64
import io


class AsistenteReporteBalanceSaldos(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_balance_saldos.wizard'
    _description = 'Balanza de Comprobación'

    fecha_desde = fields.Date(string="Fecha Inicial", required=True,
                              default=lambda self: time.strftime('%Y-%m-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True,
                              default=lambda self: time.strftime('%Y-%m-%d'))
    filtro_tipo = fields.Selection([
        ('todas', 'Todas las cuentas'),
        ('balance', 'Solo Balance General'),
        ('resultados', 'Solo Estado de Resultados'),
    ], string="Filtrar cuentas", required=True, default='todas')
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    def _build_dict(self):
        return {
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
            'filtro_tipo': self.filtro_tipo,
        }

    def print_report(self):
        data = {'ids': [], 'model': self._name, 'form': self._build_dict()}
        return self.env.ref('l10n_gt_extra.reporte_balance_saldos_wizard_report').with_context(
            landscape=True).report_action(self, data=data)

    def print_report_excel(self):
        res = self.env['report.l10n_gt_extra.reporte_balance_saldos'].lineas(self._build_dict())
        lineas = res['lineas']
        totales = res['totales']

        f = io.BytesIO()
        libro = xlsxwriter.Workbook(f)
        hoja = libro.add_worksheet('Balanza')
        fmt_num = libro.add_format({'num_format': '#,##0.00'})
        fmt_bold = libro.add_format({'bold': True})

        hoja.write(0, 0, self.env.company.name + ': Balanza de Comprobación')
        hoja.write(2, 0, 'Del {} al {}'.format(self.fecha_desde, self.fecha_hasta))

        y = 4
        for col, h in enumerate(['Código', 'Cuenta', 'Saldo Anterior',
                                   'Debe', 'Haber', 'Saldo Deudor', 'Saldo Acreedor']):
            hoja.write(y, col, h, fmt_bold)

        for linea in lineas:
            y += 1
            hoja.write(y, 0, linea['codigo'])
            hoja.write(y, 1, linea['cuenta'])
            hoja.write(y, 2, linea['saldo_anterior'], fmt_num)
            hoja.write(y, 3, linea['debe'], fmt_num)
            hoja.write(y, 4, linea['haber'], fmt_num)
            hoja.write(y, 5, linea['saldo_deudor'], fmt_num)
            hoja.write(y, 6, linea['saldo_acreedor'], fmt_num)

        y += 1
        hoja.write(y, 1, 'Totales', fmt_bold)
        hoja.write(y, 2, totales['saldo_anterior'], fmt_num)
        hoja.write(y, 3, totales['debe'], fmt_num)
        hoja.write(y, 4, totales['haber'], fmt_num)
        hoja.write(y, 5, totales['saldo_deudor'], fmt_num)
        hoja.write(y, 6, totales['saldo_acreedor'], fmt_num)

        libro.close()
        self.write({'archivo': base64.b64encode(f.getvalue()), 'name': 'balanza_comprobacion.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id, 'target': 'new'}
