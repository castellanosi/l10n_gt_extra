# -*- encoding: utf-8 -*-

from odoo import models, fields
import time
import xlsxwriter
import base64
import io


class AsistenteReporteCuentasCobrar(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_cuentas_cobrar.wizard'
    _description = 'Reporte Cuentas por Cobrar'

    folio_inicial = fields.Integer(string='Folio Inicial', required=True, default=1)
    fecha_corte = fields.Date(
        string='Al corte del', required=True,
        default=lambda self: time.strftime('%Y-%m-%d'),
    )
    solo_con_saldo = fields.Boolean(
        string='Solo con saldo pendiente', default=True,
        help='Muestra únicamente clientes que tienen saldo pendiente al corte',
    )
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    def _build_dict(self):
        return {
            'folio_inicial': self.folio_inicial,
            'fecha_corte': self.fecha_corte,
            'solo_con_saldo': self.solo_con_saldo,
            'lang': self.env.lang or 'en_US',
        }

    def print_report(self):
        data = {'ids': [], 'model': self._name, 'form': self._build_dict()}
        return self.env.ref('l10n_gt_extra.reporte_cuentas_cobrar_wizard_report').with_context(
            landscape=True).report_action(self, data=data)


    def preview_report(self):
        data = {
            'ids': [],
            'model': self._name,
            'form': self.read()[0],
        }
        action = self.env.ref('l10n_gt_extra.reporte_cuentas_cobrar_wizard_report').with_context(landscape=True).report_action(self, data=data)
        action['report_type'] = 'qweb-html'
        return action

    def print_report_excel(self):
        datos = self._build_dict()
        res = self.env['report.l10n_gt_extra.reporte_cuentas_cobrar'].lineas(datos)
        lineas = res['lineas']
        totales = res['totales']

        f = io.BytesIO()
        libro = xlsxwriter.Workbook(f)
        hoja = libro.add_worksheet('Cuentas por Cobrar')
        fmt_num = libro.add_format({'num_format': '#,##0.00'})
        fmt_bold = libro.add_format({'bold': True})
        fmt_header = libro.add_format({'bold': True, 'bg_color': '#ede9f7'})
        fmt_total = libro.add_format({'bold': True, 'bg_color': '#e8e4f5', 'num_format': '#,##0.00'})

        hoja.write(0, 0, self.env.company.name + ': Cuentas por Cobrar', fmt_bold)
        hoja.write(1, 0, 'Al corte del: {}'.format(self.fecha_corte))

        y = 3
        cols = ['Cliente', 'NIT', 'Corriente', '1-30 días', '31-60 días',
                '61-90 días', '+90 días', 'Saldo Total']
        for i, h in enumerate(cols):
            hoja.write(y, i, h, fmt_header)
        hoja.set_column(0, 0, 35)
        hoja.set_column(1, 1, 15)
        hoja.set_column(2, 7, 14)

        for linea in lineas:
            y += 1
            hoja.write(y, 0, linea['nombre'])
            hoja.write(y, 1, linea['nit'])
            hoja.write(y, 2, linea['corriente'], fmt_num)
            hoja.write(y, 3, linea['d30'], fmt_num)
            hoja.write(y, 4, linea['d60'], fmt_num)
            hoja.write(y, 5, linea['d90'], fmt_num)
            hoja.write(y, 6, linea['d90mas'], fmt_num)
            hoja.write(y, 7, linea['saldo'], fmt_num)

        y += 1
        hoja.write(y, 0, 'Totales ({} clientes)'.format(totales['num_clientes']), fmt_total)
        hoja.write(y, 1, '', fmt_total)
        hoja.write(y, 2, totales['corriente'], fmt_total)
        hoja.write(y, 3, totales['d30'], fmt_total)
        hoja.write(y, 4, totales['d60'], fmt_total)
        hoja.write(y, 5, totales['d90'], fmt_total)
        hoja.write(y, 6, totales['d90mas'], fmt_total)
        hoja.write(y, 7, totales['saldo'], fmt_total)

        libro.close()
        self.write({'archivo': base64.b64encode(f.getvalue()),
                    'name': 'cuentas_por_cobrar.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id, 'target': 'new'}


class AsistenteReporteCuentasPagar(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_cuentas_pagar.wizard'
    _description = 'Reporte Cuentas por Pagar'

    folio_inicial = fields.Integer(string='Folio Inicial', required=True, default=1)
    fecha_corte = fields.Date(
        string='Al corte del', required=True,
        default=lambda self: time.strftime('%Y-%m-%d'),
    )
    solo_con_saldo = fields.Boolean(
        string='Solo con saldo pendiente', default=True,
        help='Muestra únicamente proveedores que tienen saldo pendiente al corte',
    )
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    def _build_dict(self):
        return {
            'folio_inicial': self.folio_inicial,
            'fecha_corte': self.fecha_corte,
            'solo_con_saldo': self.solo_con_saldo,
            'lang': self.env.lang or 'en_US',
        }

    def print_report(self):
        data = {'ids': [], 'model': self._name, 'form': self._build_dict()}
        return self.env.ref('l10n_gt_extra.reporte_cuentas_pagar_wizard_report').with_context(
            landscape=True).report_action(self, data=data)


    def preview_report(self):
        data = {
            'ids': [],
            'model': self._name,
            'form': self.read()[0],
        }
        action = self.env.ref('l10n_gt_extra.reporte_cuentas_pagar_wizard_report').with_context(landscape=True).report_action(self, data=data)
        action['report_type'] = 'qweb-html'
        return action

    def print_report_excel(self):
        datos = self._build_dict()
        res = self.env['report.l10n_gt_extra.reporte_cuentas_pagar'].lineas(datos)
        lineas = res['lineas']
        totales = res['totales']

        f = io.BytesIO()
        libro = xlsxwriter.Workbook(f)
        hoja = libro.add_worksheet('Cuentas por Pagar')
        fmt_num = libro.add_format({'num_format': '#,##0.00'})
        fmt_bold = libro.add_format({'bold': True})
        fmt_header = libro.add_format({'bold': True, 'bg_color': '#fef3cd'})
        fmt_total = libro.add_format({'bold': True, 'bg_color': '#fde68a', 'num_format': '#,##0.00'})

        hoja.write(0, 0, self.env.company.name + ': Cuentas por Pagar', fmt_bold)
        hoja.write(1, 0, 'Al corte del: {}'.format(self.fecha_corte))

        y = 3
        cols = ['Proveedor', 'NIT', 'Corriente', '1-30 días', '31-60 días',
                '61-90 días', '+90 días', 'Saldo Total']
        for i, h in enumerate(cols):
            hoja.write(y, i, h, fmt_header)
        hoja.set_column(0, 0, 35)
        hoja.set_column(1, 1, 15)
        hoja.set_column(2, 7, 14)

        for linea in lineas:
            y += 1
            hoja.write(y, 0, linea['nombre'])
            hoja.write(y, 1, linea['nit'])
            hoja.write(y, 2, linea['corriente'], fmt_num)
            hoja.write(y, 3, linea['d30'], fmt_num)
            hoja.write(y, 4, linea['d60'], fmt_num)
            hoja.write(y, 5, linea['d90'], fmt_num)
            hoja.write(y, 6, linea['d90mas'], fmt_num)
            hoja.write(y, 7, linea['saldo'], fmt_num)

        y += 1
        hoja.write(y, 0, 'Totales ({} proveedores)'.format(totales['num_proveedores']), fmt_total)
        hoja.write(y, 1, '', fmt_total)
        hoja.write(y, 2, totales['corriente'], fmt_total)
        hoja.write(y, 3, totales['d30'], fmt_total)
        hoja.write(y, 4, totales['d60'], fmt_total)
        hoja.write(y, 5, totales['d90'], fmt_total)
        hoja.write(y, 6, totales['d90mas'], fmt_total)
        hoja.write(y, 7, totales['saldo'], fmt_total)

        libro.close()
        self.write({'archivo': base64.b64encode(f.getvalue()),
                    'name': 'cuentas_por_pagar.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id, 'target': 'new'}
