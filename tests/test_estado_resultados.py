# -*- encoding: utf-8 -*-
"""Pruebas de report/er_columnas.py (estado de resultados por modo).

Funciones puras: se prueban con diccionarios, sin tocar la base.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged

from ..report import bg_columnas as bg
from ..report import er_columnas as er

CUENTAS = {
    1: {'codigo': '4.1.01.01', 'nombre': 'Ventas', 'account_type': 'income'},
    2: {'codigo': '5.1.01.01', 'nombre': 'Compras', 'account_type': 'expense'},
    3: {'codigo': '6.2.01.12', 'nombre': 'Depreciación', 'account_type': 'expense'},
    4: {'codigo': '611510', 'nombre': 'Impuesto PEQ', 'account_type': 'expense'},
}


def mov(cuenta, mes, debe=0.0, haber=0.0):
    return {'account_id': cuenta, 'mes': date(2026, mes, 1), 'debe': debe, 'haber': haber}


MOVS = [
    mov(1, 7, haber=1000), mov(1, 8, haber=500),
    mov(2, 7, debe=600), mov(2, 8, debe=200),
    mov(3, 8, debe=100), mov(4, 8, debe=50),
]


@tagged('post_install', '-at_install')
class TestEstadoResultados(TransactionCase):

    def test_columnas_por_mes(self):
        cols = er.columnas('por_mes', date(2026, 1, 15), date(2026, 3, 10))
        self.assertEqual([c['titulo'] for c in cols], ['ENE-2026', 'FEB-2026', 'MAR-2026', 'Total'])

    def test_columnas_acumulativo(self):
        cols = er.columnas('acumulativo', date(2026, 1, 1), date(2026, 8, 31))
        self.assertEqual(er.encabezados(cols), ['Acumulado', 'Mes', '%', 'Total', '%'])
        self.assertEqual(len(cols[0]['meses']), 7)
        self.assertEqual(cols[1]['meses'], [date(2026, 8, 1)])
        # Un solo mes: el acumulado queda vacío
        cols = er.columnas('acumulativo', date(2026, 8, 1), date(2026, 8, 31))
        self.assertEqual(cols[0]['meses'], [])

    def test_seccion_y_niveles(self):
        self.assertEqual(er.seccion('expense', '5.1.01.01'), 'costos')
        self.assertEqual(er.seccion('expense_direct_cost', '6.1'), 'costos')
        self.assertEqual(er.seccion('expense', '6.2.01.12'), 'gastos')
        self.assertEqual(er.seccion('income_other', '999997'), 'ingresos')
        self.assertFalse(er.seccion('asset_cash', '1.1'))

    def test_acumulativo_valores_y_porcentaje(self):
        res = er.construir(CUENTAS, MOVS, 'acumulativo', date(2026, 7, 1), date(2026, 8, 31))
        neta = res['resumen'][4]['valores']
        self.assertEqual(neta, [400.0, 150.0, 550.0])  # acumulado, mes, total
        self.assertAlmostEqual(res['utilidad_neta'], 550.0)
        self.assertAlmostEqual(res['total_costos'], 800.0)
        cel = er.celdas(neta, res['columnas'], res['ingresos_col'])
        self.assertAlmostEqual(cel[2]['v'], 30.0)   # 150 / 500
        self.assertTrue(cel[2]['pct'])

    def test_detalle_por_seccion_sin_niveles(self):
        res = er.construir(CUENTAS, MOVS, 'normal', date(2026, 7, 1), date(2026, 8, 31))
        gastos = next(s for s in res['secciones'] if s['clave'] == 'gastos')
        self.assertEqual([f['codigo'] for f in gastos['filas']], ['6.2.01.12', '611510'])
        self.assertEqual(gastos['total'], [150.0])

    def test_formato(self):
        self.assertEqual(er.formato(-1234.5), '(1,234.50)')
        self.assertEqual(er.formato(-0.001), '0.00')
        self.assertEqual(er.formato(12.345, pct=True), '12.3')


BG_CUENTAS = {
    10: {'codigo': '1.1.01.01', 'nombre': 'Caja', 'account_type': 'asset_cash'},
    11: {'codigo': '2.1.01.01', 'nombre': 'Proveedores', 'account_type': 'liability_payable'},
    12: {'codigo': '3.1.01.01', 'nombre': 'Capital', 'account_type': 'equity'},
}


def bmov(cuenta, anio, mes, debe=0.0, haber=0.0):
    return {'account_id': cuenta, 'fecha': date(anio, mes, 1), 'debe': debe, 'haber': haber}


BG_MOVS = [
    bmov(10, 2025, 12, debe=1000), bmov(12, 2025, 12, haber=1000),   # aporte de capital
    bmov(10, 2026, 7, debe=300), bmov(11, 2026, 7, haber=300),       # compra a crédito
    bmov(10, 2026, 8, debe=150),                                     # utilidad de agosto
]


@tagged('post_install', '-at_install')
class TestBalanceGeneral(TransactionCase):

    def test_acumulativo(self):
        cols = bg.columnas('acumulativo', date(2026, 1, 1), date(2026, 8, 31))
        self.assertEqual([c['titulo'] for c in cols], ['Saldo anterior', 'Mes', 'Saldo al corte'])
        self.assertEqual(cols[0]['corte'], date(2026, 7, 31))
        res = bg.construir(BG_CUENTAS, BG_MOVS, [0.0, 150.0, 150.0], 'acumulativo',
                           date(2026, 1, 1), date(2026, 8, 31))
        activo = res['resumen'][0]['valores']
        self.assertEqual(activo, [1300.0, 150.0, 1450.0])
        diferencia = res['resumen'][4]['valores']
        self.assertEqual(diferencia, [0.0, 0.0, 0.0])

    def test_por_mes_saldos_al_cierre(self):
        res = bg.construir(BG_CUENTAS, BG_MOVS, [0.0, 150.0], 'por_mes',
                           date(2026, 7, 1), date(2026, 8, 20))
        self.assertEqual(res['encabezados'], ['JUL-2026', 'AGO-2026'])
        self.assertEqual(res['columnas'][1]['corte'], date(2026, 8, 20))
        self.assertEqual(res['resumen'][0]['valores'], [1300.0, 1450.0])
        self.assertAlmostEqual(res['cuadre'], 0.0)

    def test_utilidades_por_columna(self):
        res = er.construir(CUENTAS, MOVS, 'por_mes', date(2026, 7, 1), date(2026, 8, 31))
        self.assertEqual(bg.utilidades_por_columna('por_mes', res), [400.0, 550.0])
