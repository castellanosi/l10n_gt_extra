# -*- encoding: utf-8 -*-
"""Pruebas de la retención como pago y de la fecha del documento (5.62)."""

from odoo.tests import TransactionCase, tagged

from ..report import reporte_compras, reporte_estado_cuenta
from ..wizard import registrar_retencion as rr


@tagged('post_install', '-at_install')
class TestRetencion(TransactionCase):

    # ---------- textos del asistente (funciones puras)
    def test_memo_completo(self):
        self.assertEqual(rr.texto_memo('isr', 'SAT-1911 2353625', 'INV/2026/00023'),
                         'Retención ISR · constancia SAT-1911 2353625 · INV/2026/00023')

    def test_memo_sin_constancia(self):
        self.assertEqual(rr.texto_memo('iva', '', 'FACTU/2026/10/0003'),
                         'Retención IVA · FACTU/2026/10/0003')

    def test_aviso_iva_menor_2500(self):
        self.assertTrue(rr.texto_aviso('iva', 1000.0))
        self.assertFalse(rr.texto_aviso('iva', 2500.0))
        self.assertFalse(rr.texto_aviso('isr', 1000.0))
        self.assertFalse(rr.texto_aviso(False, 1000.0))

    # ---------- piezas instaladas
    def test_asistente_sin_calculo(self):
        campos = self.env['l10n_gt_extra.registrar_retencion.wizard']._fields
        self.assertIn('journal_id', campos)
        self.assertIn('monto', campos)
        for quitado in ('tipo', 'modo_iva', 'porcentaje'):
            self.assertNotIn(quitado, campos)

    def test_campo_del_diario_y_boton(self):
        self.assertIn('l10n_gt_retencion', self.env['account.journal']._fields)
        self.assertTrue(hasattr(self.env['account.move'], 'action_registrar_retencion'))
        self.assertFalse(hasattr(self.env['account.move'], 'agregar_linea_impuesto_global'))

    # ---------- fecha del documento
    def test_libro_compras_por_fecha_de_factura(self):
        self.assertEqual(reporte_compras.CAMPO_FECHA_LIBRO_COMPRAS, 'invoice_date')

    def test_estado_cuenta_por_fecha_de_factura(self):
        self.assertEqual(reporte_estado_cuenta.FECHA_DOCUMENTO_SQL,
                         'COALESCE(m.invoice_date, l.date)')
