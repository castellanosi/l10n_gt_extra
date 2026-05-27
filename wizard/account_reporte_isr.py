# -*- encoding: utf-8 -*-

from odoo import models, fields
from odoo.exceptions import UserError
import time
import xlsxwriter
import base64
import io


class AsistenteReporteISR(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_isr.wizard'
    _description = 'Reporte ISR Retenciones'
    folio_inicial = fields.Integer(string='Folio Inicial', required=True, default=1)

    fecha_desde = fields.Date(string="Fecha Inicial", required=True,
                              default=lambda self: time.strftime('%Y-%m-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True,
                              default=lambda self: time.strftime('%Y-%m-%d'))
    tipo_reporte = fields.Selection([('compra', 'Compras'), ('venta', 'Ventas')],
                                    string="Tipo", required=True, default='compra')
    impuestos_isr_id = fields.Many2many(
        "account.tax", string="Impuestos ISR",
        domain="[('amount', '<', 0)]",
        required=True,
    )
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    def _build_dict(self):
        return {
            'folio_inicial': self.folio_inicial,
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
            'tipo_reporte': self.tipo_reporte,
            'impuestos_isr_id': [i.id for i in self.impuestos_isr_id],
        }

    def print_report(self):
        if not self.impuestos_isr_id:
            raise UserError("Por favor seleccione al menos un impuesto ISR.")
        data = {'ids': [], 'model': self._name, 'form': self._build_dict()}
        return self.env.ref('l10n_gt_extra.reporte_isr_wizard_report').with_context(
            landscape=True).report_action(self, data=data)


    def preview_report(self):
        data = {
            'ids': [],
            'model': self._name,
            'form': self.read()[0],
        }
        action = self.env.ref('l10n_gt_extra.reporte_isr_wizard_report').with_context(landscape=True).report_action(self, data=data)
        action['report_type'] = 'qweb-html'
        return action

    def print_report_excel(self):
        if not self.impuestos_isr_id:
            raise UserError("Por favor seleccione al menos un impuesto ISR.")

        res = self.env['report.l10n_gt_extra.reporte_isr'].lineas(self._build_dict())
        lineas = res['lineas']
        totales = res['totales']

        f = io.BytesIO()
        libro = xlsxwriter.Workbook(f)
        hoja = libro.add_worksheet('ISR')
        fmt_fecha = libro.add_format({'num_format': 'dd/mm/yy'})
        fmt_num = libro.add_format({'num_format': '#,##0.00'})
        fmt_bold = libro.add_format({'bold': True})

        hoja.write(0, 0, self.env.company.name + ': Retenciones ISR')
        hoja.write(2, 0, 'Período del:')
        hoja.write(2, 1, self.fecha_desde, fmt_fecha)
        hoja.write(2, 2, 'al')
        hoja.write(2, 3, self.fecha_hasta, fmt_fecha)

        y = 4
        for col, header in enumerate(['Fecha', 'Tipo', 'Documento', 'Proveedor/Cliente',
                                       'NIT', 'Base Imponible', 'ISR Retenido', 'Total']):
            hoja.write(y, col, header, fmt_bold)

        for linea in lineas:
            y += 1
            hoja.write(y, 0, linea['fecha'], fmt_fecha)
            hoja.write(y, 1, linea['tipo'])
            hoja.write(y, 2, linea['numero'])
            hoja.write(y, 3, linea['proveedor'])
            hoja.write(y, 4, linea['nit'])
            hoja.write(y, 5, linea['base'], fmt_num)
            hoja.write(y, 6, linea['isr'], fmt_num)
            hoja.write(y, 7, linea['total'], fmt_num)

        y += 1
        hoja.write(y, 4, 'Totales', fmt_bold)
        hoja.write(y, 5, totales['base'], fmt_num)
        hoja.write(y, 6, totales['isr'], fmt_num)
        hoja.write(y, 7, totales['total'], fmt_num)

        libro.close()
        self.write({'archivo': base64.b64encode(f.getvalue()), 'name': 'isr_retenciones.xlsx'})

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
