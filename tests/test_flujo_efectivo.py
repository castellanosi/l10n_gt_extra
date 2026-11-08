# -*- encoding: utf-8 -*-
"""Pruebas de report/fe_columnas.py (estado de flujo de efectivo).

Funciones puras: se prueban con diccionarios, sin tocar la base.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged

from ..report import er_columnas as er
from ..report import fe_columnas as fe


def cta(codigo, tipo, clase=False, transitoria=False):
    return {'codigo': codigo, 'nombre': codigo, 'account_type': tipo,
            'clase': clase, 'transitoria': transitoria}


CUENTAS = {
    1: cta('1.1.01.01', 'asset_cash'),                         # Banco
    2: cta('1.0.01.03', 'asset_current', transitoria=True),    # Recibos pendientes
    3: cta('4.1.01.01', 'income'),
    4: cta('6.2.01.01', 'expense'),                            # Gasto depreciación
    5: cta('1.2.01.04', 'asset_current', clase='inversion'),   # Vehículo (tipo mal puesto)
    6: cta('1.2.02.04', 'asset_current', clase='depreciacion'),
    7: cta('2.3.01.03', 'liability_non_current'),              # Préstamo
    8: cta('1.1.02.01', 'asset_receivable'),
    9: cta('3.1.01.03', 'equity', clase='excluir'),            # Utilidades retenidas
}


def mov(cuenta, mes, debe=0.0, haber=0.0):
    return {'account_id': cuenta, 'mes': date(2026, mes, 1), 'debe': debe, 'haber': haber}


MOVS = [
    # Julio: venta al contado (pasa por recibos pendientes) y compra de vehículo
    mov(2, 7, debe=500), mov(3, 7, haber=500),
    mov(1, 7, debe=500), mov(2, 7, haber=500),
    mov(5, 7, debe=300), mov(1, 7, haber=300),
    # Agosto: depreciación, préstamo recibido y venta al crédito
    mov(4, 8, debe=50), mov(6, 8, haber=50),
    mov(1, 8, debe=200), mov(7, 8, haber=200),
    mov(8, 8, debe=100), mov(3, 8, haber=100),
]
INICIAL = 1000.0


def renglon(res, clave):
    for sec in res['secciones']:
        for r in sec['renglones']:
            if r['clave'] == clave:
                return r
    return None


@tagged('post_install', '-at_install')
class TestFlujoEfectivo(TransactionCase):

    def test_clasificacion_por_omision(self):
        self.assertEqual(fe.clase_cuenta('asset_cash'), 'efectivo')
        self.assertEqual(fe.clase_cuenta('asset_current', es_transitoria=True), 'efectivo')
        self.assertEqual(fe.clase_cuenta('asset_current', 'inversion', True), 'inversion')
        self.assertEqual(fe.clase_cuenta('asset_fixed'), 'inversion')
        self.assertEqual(fe.clase_cuenta('liability_non_current'), 'fin_pasivo')
        self.assertEqual(fe.clase_cuenta('equity_unaffected'), 'excluir')
        self.assertFalse(fe.clase_cuenta('income', 'inversion'))

    def test_cuadre_en_los_tres_modos(self):
        for modo in ('normal', 'por_mes', 'acumulativo'):
            res = fe.construir(CUENTAS, MOVS, INICIAL, modo, date(2026, 7, 1), date(2026, 8, 31))
            self.assertEqual(res['diferencia'], [0.0] * len(res['columnas']), modo)
            self.assertAlmostEqual(res['final'][-1], 1400.0)

    def test_renglones(self):
        res = fe.construir(CUENTAS, MOVS, INICIAL, 'normal', date(2026, 7, 1), date(2026, 8, 31))
        self.assertEqual(renglon(res, 'utilidad')['valores'], [550.0])
        self.assertEqual(renglon(res, 'depreciacion')['valores'], [50.0])
        self.assertEqual(renglon(res, 'op_cobrar')['valores'], [-100.0])
        self.assertEqual(renglon(res, 'inversion')['valores'], [-300.0])
        self.assertEqual(renglon(res, 'fin_pasivo')['valores'], [200.0])
        self.assertEqual(res['neto'], [400.0])
        # Detalle por cuenta dentro del renglón
        self.assertEqual([c['codigo'] for c in renglon(res, 'inversion')['cuentas']], ['1.2.01.04'])

    def test_utilidad_igual_al_estado_de_resultados(self):
        res = fe.construir(CUENTAS, MOVS, INICIAL, 'por_mes', date(2026, 7, 1), date(2026, 8, 31))
        er_movs = [dict(m) for m in MOVS]
        er_res = er.construir(CUENTAS, er_movs, 'por_mes', date(2026, 7, 1), date(2026, 8, 31))
        self.assertEqual(res['utilidad'], er_res['resumen'][4]['valores'])

    def test_por_mes_inicio_y_final_del_total(self):
        res = fe.construir(CUENTAS, MOVS, INICIAL, 'por_mes', date(2026, 7, 1), date(2026, 8, 31))
        self.assertEqual(res['encabezados'], ['JUL-2026', 'AGO-2026', 'Total'])
        self.assertEqual(res['inicio'], [1000.0, 1200.0, 1000.0])
        self.assertEqual(res['final'], [1200.0, 1400.0, 1400.0])
        self.assertEqual(res['neto'], [200.0, 200.0, 400.0])

    def test_acumulativo_de_un_solo_mes(self):
        res = fe.construir(CUENTAS, MOVS, INICIAL, 'acumulativo', date(2026, 8, 1), date(2026, 8, 31))
        self.assertEqual(res['encabezados'], ['Acumulado', 'Mes', 'Total'])
        self.assertEqual(res['neto'][0], 0.0)
        self.assertEqual(res['diferencia'], [0.0, 0.0, 0.0])

    def test_cuenta_excluida_sin_efecto(self):
        # Asiento de cierre: la utilidad pasa a utilidades retenidas.
        movs = MOVS + [mov(3, 8, debe=100), mov(9, 8, haber=100)]
        res = fe.construir(CUENTAS, movs, INICIAL, 'normal', date(2026, 7, 1), date(2026, 8, 31))
        codigos = [c['codigo'] for s in res['secciones'] for r in s['renglones'] for c in r['cuentas']]
        self.assertNotIn('3.1.01.03', codigos)
        # La Diferencia avisa que la utilidad del período quedó incompleta
        self.assertEqual(res['diferencia'], [-100.0])

    def test_cuenta_mal_clasificada_da_diferencia(self):
        cuentas = dict(CUENTAS)
        cuentas[7] = cta('2.3.01.03', 'liability_non_current', clase='excluir')
        res = fe.construir(cuentas, MOVS, INICIAL, 'normal', date(2026, 7, 1), date(2026, 8, 31))
        self.assertEqual(res['diferencia'], [-200.0])

    def test_filas_planas(self):
        res = fe.construir(CUENTAS, MOVS, INICIAL, 'normal', date(2026, 7, 1), date(2026, 8, 31))
        con = fe.filas_planas(res, True)
        sin = fe.filas_planas(res, False)
        self.assertTrue(any(f['tipo'] == 'cuenta' for f in con))
        self.assertFalse(any(f['tipo'] == 'cuenta' for f in sin))
        self.assertEqual(con[-1]['etiqueta'], 'Diferencia (debe ser 0.00)')
