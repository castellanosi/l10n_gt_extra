# -*- encoding: utf-8 -*-

from odoo import models, fields
import time
import xlsxwriter
import base64
import io


class AsistenteReporteEstadoResultados(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_estado_resultados.wizard'
    _description = 'Estado de Resultados'
    folio_inicial = fields.Integer(string='Folio Inicial', required=True, default=1)

    fecha_desde = fields.Date(string="Fecha Inicial", required=True,
                              default=lambda self: time.strftime('%Y-01-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True,
                              default=lambda self: time.strftime('%Y-%m-%d'))
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    def _build_dict(self):
        return {
            'folio_inicial': self.folio_inicial,
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
        }

    def print_report(self):
        data = {'ids': [], 'model': self._name, 'form': self._build_dict()}
        return self.env.ref('l10n_gt_extra.reporte_estado_resultados_wizard_report').report_action(
            self, data=data)


    def preview_report(self):
        data = {
            'ids': [],
            'model': self._name,
            'form': self.read()[0],
        }
        action = self.env.ref('l10n_gt_extra.reporte_estado_resultados_wizard_report').report_action(self, data=data)
        action['report_type'] = 'qweb-html'
        return action

    def print_report_excel(self):
        res = self.env['report.l10n_gt_extra.reporte_estado_resultados'].datos(self._build_dict())

        f = io.BytesIO()
        libro = xlsxwriter.Workbook(f)
        hoja = libro.add_worksheet('Estado de Resultados')
        fmt_num = libro.add_format({'num_format': '#,##0.00'})
        fmt_bold = libro.add_format({'bold': True})
        fmt_titulo = libro.add_format({'bold': True, 'font_size': 12})

        hoja.write(0, 0, self.env.company.name + ': Estado de Resultados', fmt_titulo)
        hoja.write(1, 0, 'Del {} al {}'.format(self.fecha_desde, self.fecha_hasta))

        y = 3
        hoja.write(y, 0, 'INGRESOS', fmt_bold)
        for l in res['ingresos']:
            y += 1
            hoja.write(y, 0, '{} — {}'.format(l['codigo'], l['nombre']))
            hoja.write(y, 1, l['saldo'], fmt_num)
        y += 1
        hoja.write(y, 0, 'Total ingresos', fmt_bold)
        hoja.write(y, 1, res['total_ingresos'], fmt_num)

        y += 2
        hoja.write(y, 0, 'COSTO DE VENTAS', fmt_bold)
        for l in res['costos']:
            y += 1
            hoja.write(y, 0, '{} — {}'.format(l['codigo'], l['nombre']))
            hoja.write(y, 1, l['saldo'], fmt_num)
        y += 1
        hoja.write(y, 0, 'Total costo de ventas', fmt_bold)
        hoja.write(y, 1, res['total_costos'], fmt_num)

        y += 1
        hoja.write(y, 0, 'UTILIDAD BRUTA', fmt_bold)
        hoja.write(y, 1, res['utilidad_bruta'], fmt_num)

        y += 2
        hoja.write(y, 0, 'GASTOS DE OPERACIÓN', fmt_bold)
        for l in res['gastos']:
            y += 1
            hoja.write(y, 0, '{} — {}'.format(l['codigo'], l['nombre']))
            hoja.write(y, 1, l['saldo'], fmt_num)
        y += 1
        hoja.write(y, 0, 'Total gastos', fmt_bold)
        hoja.write(y, 1, res['total_gastos'], fmt_num)

        y += 1
        label = 'UTILIDAD NETA' if res['utilidad_neta'] >= 0 else 'PÉRDIDA NETA'
        hoja.write(y, 0, label, fmt_bold)
        hoja.write(y, 1, res['utilidad_neta'], fmt_num)

        libro.close()
        self.write({'archivo': base64.b64encode(f.getvalue()),
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
        help="Fecha de inicio para calcular la utilidad/pérdida del período",
    )
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    def _build_dict(self):
        return {
            'folio_inicial': self.folio_inicial,
            'fecha_hasta': self.fecha_hasta,
            'fecha_desde_er': self.fecha_desde_er,
        }

    def print_report(self):
        data = {'ids': [], 'model': self._name, 'form': self._build_dict()}
        return self.env.ref('l10n_gt_extra.reporte_balance_general_wizard_report').report_action(
            self, data=data)


    def preview_report(self):
        data = {
            'ids': [],
            'model': self._name,
            'form': self.read()[0],
        }
        action = self.env.ref('l10n_gt_extra.reporte_balance_general_wizard_report').report_action(self, data=data)
        action['report_type'] = 'qweb-html'
        return action

    def print_report_excel(self):
        res = self.env['report.l10n_gt_extra.reporte_balance_general'].datos(self._build_dict())

        f = io.BytesIO()
        libro = xlsxwriter.Workbook(f)
        hoja = libro.add_worksheet('Balance General')
        fmt_num = libro.add_format({'num_format': '#,##0.00'})
        fmt_bold = libro.add_format({'bold': True})
        fmt_titulo = libro.add_format({'bold': True, 'font_size': 12})

        hoja.write(0, 0, self.env.company.name + ': Balance General', fmt_titulo)
        hoja.write(1, 0, 'Al: {}'.format(self.fecha_hasta))

        y = 3
        hoja.write(y, 0, 'ACTIVOS', fmt_bold)
        for l in res['activos']:
            y += 1
            hoja.write(y, 0, '{} — {}'.format(l['codigo'], l['nombre']))
            hoja.write(y, 1, l['saldo'], fmt_num)
        y += 1
        hoja.write(y, 0, 'Total activos', fmt_bold)
        hoja.write(y, 1, res['total_activo'], fmt_num)

        y += 2
        hoja.write(y, 0, 'PASIVOS', fmt_bold)
        for l in res['pasivos']:
            y += 1
            hoja.write(y, 0, '{} — {}'.format(l['codigo'], l['nombre']))
            hoja.write(y, 1, l['saldo'], fmt_num)
        y += 1
        hoja.write(y, 0, 'Total pasivos', fmt_bold)
        hoja.write(y, 1, res['total_pasivo'], fmt_num)

        y += 2
        hoja.write(y, 0, 'CAPITAL', fmt_bold)
        for l in res['capital']:
            y += 1
            hoja.write(y, 0, '{} — {}'.format(l['codigo'], l['nombre']))
            hoja.write(y, 1, l['saldo'], fmt_num)
        y += 1
        label = 'Utilidad del período' if res['utilidad_periodo'] >= 0 else 'Pérdida del período'
        hoja.write(y, 0, label)
        hoja.write(y, 1, res['utilidad_periodo'], fmt_num)
        y += 1
        hoja.write(y, 0, 'Total capital', fmt_bold)
        hoja.write(y, 1, res['total_capital_mas_utilidad'], fmt_num)

        y += 1
        hoja.write(y, 0, 'TOTAL PASIVOS + CAPITAL', fmt_bold)
        hoja.write(y, 1, res['total_pasivo_capital'], fmt_num)

        libro.close()
        self.write({'archivo': base64.b64encode(f.getvalue()),
                    'name': 'balance_general.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id, 'target': 'new'}
