# -*- encoding: utf-8 -*-

from odoo import models, fields
import time
import xlsxwriter
import base64
import io


class AsistenteReporteFEL(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_fel.wizard'
    _description = 'Reporte Facturas Electrónicas FEL'

    fecha_desde = fields.Date(string="Fecha Inicial", required=True,
                              default=lambda self: time.strftime('%Y-%m-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True,
                              default=lambda self: time.strftime('%Y-%m-%d'))
    tipo = fields.Selection([('compra', 'Compras'), ('venta', 'Ventas')],
                            string="Tipo", required=True, default='compra')
    diarios_id = fields.Many2many("account.journal", string="Diarios")
    solo_fel = fields.Boolean(string="Solo facturas con autorización FEL",
                              help="Si está marcado, solo muestra documentos con número de autorización FEL")
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    def _build_dict(self):
        return {
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
            'tipo': self.tipo,
            'diarios_id': [j.id for j in self.diarios_id],
            'solo_fel': self.solo_fel,
        }

    def print_report(self):
        data = {'ids': [], 'model': self._name, 'form': self._build_dict()}
        return self.env.ref('l10n_gt_extra.reporte_fel_wizard_report').with_context(
            landscape=True).report_action(self, data=data)

    def print_report_excel(self):
        res = self.env['report.l10n_gt_extra.reporte_fel'].lineas(self._build_dict())
        lineas = res['lineas']
        totales = res['totales']

        f = io.BytesIO()
        libro = xlsxwriter.Workbook(f)
        hoja = libro.add_worksheet('FEL')
        fmt_fecha = libro.add_format({'num_format': 'dd/mm/yy'})
        fmt_num = libro.add_format({'num_format': '#,##0.00'})
        fmt_bold = libro.add_format({'bold': True})

        hoja.write(0, 0, self.env.company.name + ': Facturas Electrónicas FEL')

        y = 2
        for col, h in enumerate(['Fecha', 'Tipo', 'Serie', 'Número', 'UUID/Autorización',
                                   'Proveedor/Cliente', 'NIT', 'Base', 'IVA', 'ISR/Ret.', 'Total']):
            hoja.write(y, col, h, fmt_bold)

        for linea in lineas:
            y += 1
            hoja.write(y, 0, linea['fecha'], fmt_fecha)
            hoja.write(y, 1, linea['tipo'])
            hoja.write(y, 2, linea['serie'])
            hoja.write(y, 3, linea['numero'])
            hoja.write(y, 4, linea['uuid'])
            hoja.write(y, 5, linea['partner'])
            hoja.write(y, 6, linea['nit'])
            hoja.write(y, 7, linea['base'], fmt_num)
            hoja.write(y, 8, linea['iva'], fmt_num)
            hoja.write(y, 9, linea['isr'], fmt_num)
            hoja.write(y, 10, linea['total'], fmt_num)

        y += 1
        hoja.write(y, 6, 'Totales', fmt_bold)
        hoja.write(y, 7, totales['base'], fmt_num)
        hoja.write(y, 8, totales['iva'], fmt_num)
        hoja.write(y, 9, totales['isr'], fmt_num)
        hoja.write(y, 10, totales['total'], fmt_num)

        libro.close()
        self.write({'archivo': base64.b64encode(f.getvalue()), 'name': 'facturas_fel.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id, 'target': 'new'}
