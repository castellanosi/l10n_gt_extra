# -*- encoding: utf-8 -*-
"""Pruebas del cheque «Solo con saldo pendiente» de CxC / CxP.

agrupar_documentos() es una función pura: se prueba con diccionarios que
imitan las filas del SQL, sin tocar la base.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged

from ..report.reporte_cuentas_cobrar_pagar import agrupar_documentos

CORTE = date(2026, 11, 5)


def doc(comercial_id, nombre, nit, pendiente, fecha=date(2026, 10, 20)):
    return {
        'comercial_id': comercial_id,
        'nombre': nombre,
        'nit': nit,
        'pendiente': pendiente,
        'date': fecha,
        'date_maturity': fecha,
    }


DOCUMENTOS = [
    doc(1, 'Cliente pagado', '111', 0.0),       # factura ya pagada
    doc(1, 'Cliente pagado', '111', 0.001),     # residuo de redondeo
    doc(2, 'Cliente con saldo', '222', 150.0),
    doc(3, 'Cliente CF', 'CF', 0.0),
]


@tagged('post_install', '-at_install')
class TestCuentasCobrarPagar(TransactionCase):

    def test_con_cheque_solo_pendientes(self):
        lineas, totales = agrupar_documentos(DOCUMENTOS, CORTE, 1, solo_con_saldo=True)
        self.assertEqual([g['nombre'] for g in lineas], ['Cliente con saldo'])
        self.assertAlmostEqual(totales['saldo'], 150.0)

    def test_sin_cheque_incluye_pagados_en_cero(self):
        lineas, totales = agrupar_documentos(DOCUMENTOS, CORTE, 1, solo_con_saldo=False)
        nombres = [g['nombre'] for g in lineas]
        self.assertEqual(nombres, ['Cliente CF', 'Cliente con saldo', 'Cliente pagado'])
        pagado = lineas[2]
        self.assertEqual(pagado['saldo'], 0.0)
        self.assertEqual(
            (pagado['d30'], pagado['d60'], pagado['d90'], pagado['d90mas']),
            (0.0, 0.0, 0.0, 0.0),
        )
        # Los totales no cambian: los pagados suman cero
        self.assertAlmostEqual(totales['saldo'], 150.0)

    def test_cxp_con_signo_negativo(self):
        docs = [doc(5, 'Proveedor', '555', -80.0), doc(6, 'Proveedor pagado', '666', 0.0)]
        lineas, totales = agrupar_documentos(docs, CORTE, -1, solo_con_saldo=False)
        self.assertEqual(len(lineas), 2)
        self.assertAlmostEqual(totales['saldo'], 80.0)
        lineas, _ = agrupar_documentos(docs, CORTE, -1, solo_con_saldo=True)
        self.assertEqual([g['nombre'] for g in lineas], ['Proveedor'])
