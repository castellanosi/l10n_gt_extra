# -*- encoding: utf-8 -*-

from odoo import models, fields
import time
import xlsxwriter
import base64
import io


class AsistenteReportePequeno(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_pequeno.wizard'
    _description = 'Libro Compras/Ventas Pequeño Contribuyente'
    folio_inicial = fields.Integer(string='Folio Inicial', required=True, default=1)

    tipo = fields.Selection([('compra', 'Compras'), ('venta', 'Ventas')],
                            string="Tipo", required=True, default='compra')
    fecha_desde = fields.Date(string="Fecha Inicial", required=True,
                              default=lambda self: time.strftime('%Y-%m-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True,
                              default=lambda self: time.strftime('%Y-%m-%d'))
    diarios_id = fields.Many2many("account.journal", string="Diarios")
    solo_pequenos = fields.Boolean(string="Solo pequeños contribuyentes",
                                   help="Filtra únicamente documentos de/para pequeños contribuyentes")
    tasa_cuota = fields.Float(string="Tasa cuota (%)", default=5.0,
                              help="Tasa de la cuota del pequeño contribuyente (generalmente 5%)")
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    def _build_dict(self):
        return {
            'folio_inicial': self.folio_inicial,
            'tipo': self.tipo,
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
            'diarios_id': [j.id for j in self.diarios_id],
            'solo_pequenos': self.solo_pequenos,
            'tasa_cuota': self.tasa_cuota,
        }

    def print_report(self):
        data = {'ids': [], 'model': self._name, 'form': self._build_dict()}
        return self.env.ref('l10n_gt_extra.reporte_pequeno_wizard_report').with_context(
            landscape=True).report_action(self, data=data)

    def print_report_excel(self):
        res = self.env['report.l10n_gt_extra.reporte_pequeno'].lineas(self._build_dict())
        lineas = res['lineas']
        totales = res['totales']

        f = io.BytesIO()
        libro = xlsxwriter.Workbook(f)
        hoja = libro.add_worksheet('Pequeño Contribuyente')
        fmt_fecha = libro.add_format({'num_format': 'dd/mm/yy'})
        fmt_num = libro.add_format({'num_format': '#,##0.00'})
        fmt_bold = libro.add_format({'bold': True})

        titulo = 'Libro de {} - Pequeño Contribuyente'.format(
            'Compras' if self.tipo == 'compra' else 'Ventas')
        hoja.write(0, 0, self.env.company.name + ': ' + titulo)

        y = 2
        for col, h in enumerate(['Fecha', 'Tipo', 'Documento', 'Proveedor/Cliente',
                                   'NIT', 'Total Factura', 'Cuota 5%']):
            hoja.write(y, col, h, fmt_bold)

        for linea in lineas:
            y += 1
            hoja.write(y, 0, linea['fecha'], fmt_fecha)
            hoja.write(y, 1, linea['tipo'])
            hoja.write(y, 2, linea['numero'])
            hoja.write(y, 3, linea['partner'])
            hoja.write(y, 4, linea['nit'])
            hoja.write(y, 5, linea['total'], fmt_num)
            hoja.write(y, 6, linea['cuota'], fmt_num)

        y += 1
        hoja.write(y, 4, 'Totales', fmt_bold)
        hoja.write(y, 5, totales['total'], fmt_num)
        hoja.write(y, 6, totales['cuota'], fmt_num)

        libro.close()
        self.write({'archivo': base64.b64encode(f.getvalue()),
                    'name': 'libro_pequeno_contribuyente.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id, 'target': 'new'}
