# -*- encoding: utf-8 -*-

from odoo import models, fields
import time
import xlsxwriter
import base64
import io


class AsistenteReporteEstadoCuenta(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_estado_cuenta.wizard'
    _description = 'Estado de Cuenta por Cliente / Proveedor'

    partner_id = fields.Many2one('res.partner', string="Cliente / Proveedor", required=True)
    fecha_desde = fields.Date(string="Fecha Inicial", required=True,
                              default=lambda self: time.strftime('%Y-%m-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True,
                              default=lambda self: time.strftime('%Y-%m-%d'))
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    def _build_dict(self):
        return {
            'partner_id': [self.partner_id.id, self.partner_id.name],
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
        }

    def print_report(self):
        data = {'ids': [], 'model': self._name, 'form': self._build_dict()}
        return self.env.ref('l10n_gt_extra.reporte_estado_cuenta_wizard_report').report_action(
            self, data=data)

    def print_report_excel(self):
        rpt = self.env['report.l10n_gt_extra.reporte_estado_cuenta']
        datos = self._build_dict()
        res = rpt.lineas(datos)
        sal_ant = rpt.saldo_anterior(datos)

        f = io.BytesIO()
        libro = xlsxwriter.Workbook(f)
        hoja = libro.add_worksheet('Estado de Cuenta')
        fmt_fecha = libro.add_format({'num_format': 'dd/mm/yy'})
        fmt_num = libro.add_format({'num_format': '#,##0.00'})
        fmt_bold = libro.add_format({'bold': True})

        hoja.write(0, 0, self.env.company.name + ': Estado de Cuenta')
        hoja.write(2, 0, 'Cliente / Proveedor:')
        hoja.write(2, 1, self.partner_id.name)
        hoja.write(3, 0, 'NIT:')
        hoja.write(3, 1, self.partner_id.vat or 'CF')
        hoja.write(4, 0, 'Del {} al {}'.format(self.fecha_desde, self.fecha_hasta))

        y = 6
        for col, h in enumerate(['Fecha', 'Documento', 'Concepto', 'Debe', 'Haber', 'Saldo']):
            hoja.write(y, col, h, fmt_bold)

        y += 1
        hoja.write(y, 2, 'Saldo anterior', fmt_bold)
        hoja.write(y, 5, sal_ant, fmt_num)

        for linea in res['lineas']:
            y += 1
            hoja.write(y, 0, linea['fecha'], fmt_fecha)
            hoja.write(y, 1, linea['documento'])
            hoja.write(y, 2, linea['concepto'])
            hoja.write(y, 3, linea['debe'], fmt_num)
            hoja.write(y, 4, linea['haber'], fmt_num)
            hoja.write(y, 5, linea['saldo'], fmt_num)

        libro.close()
        self.write({'archivo': base64.b64encode(f.getvalue()), 'name': 'estado_cuenta.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id, 'target': 'new'}
