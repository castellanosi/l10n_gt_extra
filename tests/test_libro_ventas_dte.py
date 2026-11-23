# -*- encoding: utf-8 -*-
"""Libro de ventas con el IVA del DTE y Excel con 2 decimales (desde 5.66).

- Factura sin datos del DTE: igual que antes.
- Factura con gt_dte_* (importador >= 18.0.1.8.0): IVA del DTE.
- Nota de crédito con gt_dte_*: resta con los montos del DTE.
- Filtro por fecha del documento (invoice_date), no por la contable.
- Excel: ninguna celda con más de 2 decimales.

Las facturas se crean con gt_dte_* en create y se publican SOLO en un diario
sin FEL (en tienda_odoo el integrador certifica al publicar). Si la base no
tiene lo necesario (impuesto 12 %, diario sin FEL, importador), la prueba se
salta con el motivo.
"""

import io
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..wizard.libro_excel import generar_excel


@tagged('post_install', '-at_install')
class TestLibroVentasDte(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.iva = cls.env['account.tax'].search(
            [
                ('company_id', '=', cls.company.id),
                ('type_tax_use', '=', 'sale'),
                ('amount_type', '=', 'percent'),
                ('amount', '=', 12),
            ],
            limit=1,
        )
        dominio = [('company_id', '=', cls.company.id), ('type', '=', 'sale')]
        if 'l10n_gt_fel_enabled' in cls.env['account.journal']._fields:
            dominio.append(('l10n_gt_fel_enabled', '=', False))
        cls.diario = cls.env['account.journal'].search(dominio, limit=1)
        cls.cliente = cls.env['res.partner'].create({'name': 'Cliente libro 5.66'})

    def _requisitos(self):
        if not self.iva:
            self.skipTest('No hay impuesto de venta de 12 % en la empresa de prueba')
        if not self.diario:
            self.skipTest('No hay diario de ventas sin FEL en la empresa de prueba')

    def _factura(self, tipo, fecha, contable, dte=None):
        """Factura de 273.80 con IVA incluido o 244.46 + IVA, según el impuesto."""
        precio = 273.80 if self.iva.price_include else 244.46
        vals = {
            'move_type': tipo,
            'partner_id': self.cliente.id,
            'journal_id': self.diario.id,
            'invoice_date': fecha,
            'date': contable,
            'invoice_line_ids': [
                (
                    0,
                    0,
                    {
                        'name': 'Venta libro 5.66',
                        'quantity': 1,
                        'price_unit': precio,
                        'tax_ids': [(6, 0, self.iva.ids)],
                    },
                )
            ],
        }
        if dte:
            vals.update(dte)
        factura = self.env['account.move'].create(vals)
        try:
            factura.action_post()
        except (UserError, ValidationError) as e:
            self.skipTest('No se pudo publicar la factura de prueba en esta base: %s' % e)
        return factura

    def _libro(self, desde, hasta):
        return self.env['report.l10n_gt_extra.reporte_ventas'].lineas(
            {
                'fecha_desde': desde,
                'fecha_hasta': hasta,
                'impuestos_id': self.iva.ids,
                'diarios_id': self.diario.ids,
                'resumido': False,
            }
        )

    def _fila(self, res, factura):
        for linea in res['lineas']:
            if linea.get('move_id') == factura.id:
                return linea
        self.fail('La factura %s no salió en el libro' % factura.name)

    def test_sin_dte_igual_que_antes(self):
        self._requisitos()
        f = self._factura('out_invoice', date(2026, 9, 10), date(2026, 9, 10))
        fila = self._fila(self._libro(date(2026, 9, 1), date(2026, 9, 30)), f)
        self.assertAlmostEqual(fila['total'], 273.80, places=2)
        self.assertAlmostEqual(fila['compra'] + fila['servicio'] + fila['iva'], 273.80, places=2)

    def test_con_dte_usa_iva_del_dte_y_nc_resta(self):
        self._requisitos()
        if 'gt_dte_iva' not in self.env['account.move']._fields:
            self.skipTest('El importador (gt_dte_iva) no está instalado en esta base')
        dte = {'gt_dte_total': 273.80, 'gt_dte_iva': 29.35}
        f = self._factura('out_invoice', date(2026, 9, 10), date(2026, 9, 10), dte)
        nc = self._factura('out_refund', date(2026, 9, 11), date(2026, 9, 11), dte)
        res = self._libro(date(2026, 9, 1), date(2026, 9, 30))

        fila = self._fila(res, f)
        self.assertAlmostEqual(fila['iva'], 29.35, places=2)
        self.assertAlmostEqual(fila['compra'] + fila['servicio'], 244.45, places=2)
        self.assertAlmostEqual(fila['total'], 273.80, places=2)

        fila_nc = self._fila(res, nc)
        self.assertAlmostEqual(fila_nc['iva'], -29.35, places=2)
        self.assertAlmostEqual(fila_nc['total'], -273.80, places=2)
        self.assertGreaterEqual(res['control']['dte_usados'], 2)

    def test_filtra_por_fecha_del_documento(self):
        self._requisitos()
        # Factura del 30/09 contabilizada el 01/10: sale en septiembre
        f = self._factura('out_invoice', date(2026, 9, 30), date(2026, 10, 1))
        self._fila(self._libro(date(2026, 9, 1), date(2026, 9, 30)), f)
        octubre = self._libro(date(2026, 10, 1), date(2026, 10, 31))
        self.assertFalse([x for x in octubre['lineas'] if x.get('move_id') == f.id])

    def test_excel_dos_decimales(self):
        self._requisitos()
        self._factura('out_invoice', date(2026, 9, 10), date(2026, 9, 10))
        res = self._libro(date(2026, 9, 1), date(2026, 9, 30))
        contenido = generar_excel(
            self.company, date(2026, 9, 1), date(2026, 9, 30), res, compras=False
        )
        try:
            import openpyxl
        except ImportError:
            self.skipTest('openpyxl no está instalado')
        hoja = openpyxl.load_workbook(io.BytesIO(contenido)).active
        encabezados = [c.value for c in hoja[6]]
        self.assertIn('Impuestos y contribuciones', encabezados)
        self.assertIn('Combustible', encabezados)
        for fila in hoja.iter_rows(min_row=7):
            for celda in fila:
                if isinstance(celda.value, float):
                    self.assertEqual(celda.value, round(celda.value, 2), celda.coordinate)

    # Pie «Control»: solo con la casilla del asistente (no necesita facturas)
    def test_control_solo_con_casilla(self):
        Reporte = self.env['report.l10n_gt_extra.reporte_ventas']
        datos = {
            'fecha_desde': date(2026, 9, 1),
            'fecha_hasta': date(2026, 9, 30),
            'impuestos_id': [],
            'diarios_id': [],
            'resumido': False,
        }
        self.assertIsNone(Reporte.lineas(dict(datos))['control'])
        datos['incluir_control'] = True
        control = Reporte.lineas(dict(datos))['control']
        self.assertEqual(control['diferencia'], 0.0)
        self.assertEqual(control['documentos'], [])
        compras = self.env['report.l10n_gt_extra.reporte_compras'].lineas(dict(datos))
        self.assertTrue(compras['control'])

    def test_control_separa_redondeo_dte(self):
        from decimal import Decimal

        from ..report.libro_control import control_libro, mensajes_control

        info = {
            'ventas': True,
            'iva_libro': Decimal('29.35'),
            'con_iva': {},
            'vigentes': [],
            'hallazgos': [],
            'dte_usados': 1,
            'iva_calculado': {1: Decimal('29.34')},
            'iva_fila': {1: Decimal('29.35')},
            'numeros': {1: '8D09FF63-1280721538'},
            'impuestos_ids': [],
            'diarios_ids': [],
            'tipos': ['out_invoice', 'out_refund'],
            'fecha_desde': date(2026, 9, 1),
            'fecha_hasta': date(2026, 9, 30),
        }
        control = control_libro(self.env, info)
        self.assertEqual(control['redondeo_dte'], 0.01)
        self.assertEqual(control['otras_diferencias'], 29.34)
        mensajes = mensajes_control(control)
        self.assertTrue(any('Redondeo del IVA de los DTE' in m for m in mensajes))
        self.assertTrue(any('Otras diferencias' in m for m in mensajes))
