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


@tagged('post_install', '-at_install')
class TestDiariosRetencion(TransactionCase):

    def test_codigo_libre(self):
        from ..models.res_company import codigo_libre
        self.assertEqual(codigo_libre('RIVA', set()), 'RIVA')
        self.assertEqual(codigo_libre('RIVA', {'RIVA'}), 'RIVA2')
        self.assertEqual(codigo_libre('1.0.01.90', {'1.0.01.90'}), '1.0.01.91')

    def test_crea_diarios_sin_cuentas_e_idempotente(self):
        # Como en la realidad (migración y plan nuevo): una empresa con plan
        # contable. La empresa por omisión de la prueba puede no tenerlo.
        company = self.env['res.company'].search([('chart_template', '!=', False)], limit=1)
        if not company:
            self.skipTest('No hay empresa con plan contable en esta base')
        company._l10n_gt_crear_diarios_retencion()
        J = self.env['account.journal']
        for tipo in ('iva', 'isr'):
            diarios = J.with_company(company).search([('company_id', '=', company.id), ('l10n_gt_retencion', '=', tipo)])
            self.assertTrue(diarios)
            self.assertEqual(diarios[:1].type, 'cash')
            self.assertEqual(diarios[:1].default_account_id.account_type, 'asset_cash')
            self.assertIn(company, diarios[:1].default_account_id.company_ids)
        antes = J.search_count([('l10n_gt_retencion', '!=', False), ('company_id', '=', company.id)])
        company._l10n_gt_crear_diarios_retencion()
        despues = J.search_count([('l10n_gt_retencion', '!=', False), ('company_id', '=', company.id)])
        self.assertEqual(antes, despues)

    def test_asistente_no_usa_message_post(self):
        import inspect
        from ..wizard import registrar_retencion as rr
        src = inspect.getsource(rr.RegistrarRetencionWizard.action_confirmar)
        self.assertNotIn('.message_post(', src)
        self.assertIn('._message_log(', src)
