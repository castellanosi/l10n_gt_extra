# -*- encoding: utf-8 -*-
"""Pruebas de report/conciliacion_logica.py (conciliación bancaria).

Funciones puras: se prueban con diccionarios, sin tocar la base.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged

from ..report import conciliacion_logica as cl


def ln(fecha, debit=0.0, credit=0.0, transito=True, cobro=None, doc='X'):
    return {'date': fecha, 'debit': debit, 'credit': credit, 'en_transito': transito,
            'fecha_cobro': cobro, 'documento': doc, 'concepto': ''}


OCT = date(2026, 10, 31)
NOV = date(2026, 11, 30)


@tagged('post_install', '-at_install')
class TestConciliacion(TransactionCase):

    def test_sin_marca_esta_cobrado(self):
        self.assertFalse(cl.es_pendiente(ln(date(2026, 10, 5), transito=False), OCT))

    def test_cheque_de_meses_anteriores_sigue_pendiente(self):
        self.assertTrue(cl.es_pendiente(ln(date(2026, 9, 20)), NOV))

    def test_cobrado_despues_del_corte(self):
        cheque = ln(date(2026, 10, 25), cobro=date(2026, 11, 5))
        self.assertTrue(cl.es_pendiente(cheque, OCT))     # en octubre: pendiente
        self.assertFalse(cl.es_pendiente(cheque, NOV))    # en noviembre: ya cobrado

    def test_posterior_al_corte_no_sale(self):
        self.assertFalse(cl.es_pendiente(ln(date(2026, 11, 2)), OCT))

    def test_cuadre(self):
        lineas = [
            ln(date(2026, 10, 20), credit=5000, doc='CHK-1'),             # cheque en tránsito
            ln(date(2026, 10, 30), debit=2000, doc='DEP-1'),              # depósito en tránsito
            ln(date(2026, 10, 10), credit=800, cobro=date(2026, 10, 15)),  # ya cobrado
            ln(date(2026, 10, 12), credit=300, transito=False),            # sin marca
        ]
        # Libros 100,000; banco = 100,000 + 5,000 - 2,000 = 103,000
        res = cl.construir(lineas, 100000.0, 103000.0, OCT)
        self.assertEqual(res['total_cheques'], 5000.0)
        self.assertEqual(res['total_depositos'], 2000.0)
        self.assertEqual(res['saldo_banco_calculado'], 103000.0)
        self.assertEqual(res['diferencia'], 0.0)
        self.assertEqual([c['documento'] for c in res['cheques_pendientes']], ['CHK-1'])

    def test_cheque_olvidado_da_diferencia(self):
        # El banco ya descontó 300 que en libros quedaron sin registrar
        res = cl.construir([], 100000.0, 99700.0, OCT)
        self.assertEqual(res['diferencia'], -300.0)
