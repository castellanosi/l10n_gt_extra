# -*- encoding: utf-8 -*-
"""Montos de las filas de los libros (report/libro_montos.py, desde 5.66).

Funciones puras: corren igual con o sin el importador instalado.
Casos tomados de datos reales (Exlin sep. 2026, EEGSA, compras en USD).
"""

from decimal import Decimal

from odoo.tests import TransactionCase, tagged

from ..report import libro_montos as lm

D = Decimal
VENTAS = lm.COLUMNAS_VENTAS
COMPRAS = lm.COLUMNAS_COMPRAS


def fila(columnas, **montos):
    """Fila calculada como hoy: claves de columna, '<col>_exento', 'otros',
    e 'iva_<col>' para el IVA de esa columna."""
    f = lm.fila_vacia(columnas)
    for clave, valor in montos.items():
        if clave.startswith('iva_'):
            f['iva_col'][clave[4:]] = D(valor)
        else:
            f[clave] = D(valor)
    return lm.redondear_fila(f, columnas)


@tagged('post_install', '-at_install')
class TestLibroMontos(TransactionCase):

    # 1. IVA del DTE, todo en Bienes (DTE 8D09FF63 de Exlin)
    def test_iva_dte_todo_bienes(self):
        f = fila(VENTAS, compra='244.46', iva_compra='29.34')
        self.assertIsNone(lm.aplicar_dte(f, VENTAS, D('273.80'), D('29.35')))
        self.assertEqual(f['compra'], D('244.45'))
        self.assertEqual(f['iva'], D('29.35'))
        self.assertEqual(f['iva_col']['compra'], D('29.35'))
        self.assertEqual(f['total'], D('273.80'))

    # 2. Mismo IVA que el DTE: la fila no cambia
    def test_mismo_iva_no_cambia(self):
        f = fila(VENTAS, compra='48.82', iva_compra='5.86')
        self.assertIsNone(lm.aplicar_dte(f, VENTAS, D('54.68'), D('5.86')))
        self.assertEqual((f['compra'], f['iva'], f['total']), (D('48.82'), D('5.86'), D('54.68')))

    # 3. Repartición mixta: la diferencia va a la columna gravada mayor
    def test_mixta_bienes_servicios(self):
        f = fila(VENTAS, compra='100.00', servicio='50.00', iva_compra='12.00', iva_servicio='6.00')
        self.assertIsNone(lm.aplicar_dte(f, VENTAS, D('168.00'), D('18.01')))
        self.assertEqual(f['compra'], D('99.99'))
        self.assertEqual(f['servicio'], D('50.00'))
        self.assertEqual(f['iva'], D('18.01'))
        self.assertEqual(f['total'], D('168.00'))

    # 4. Nota de crédito: mismos montos con signo negativo
    def test_nota_credito(self):
        f = fila(VENTAS, compra='-244.46', iva_compra='-29.34')
        total = lm.monto_dte(273.80, 1, -1)
        iva = lm.monto_dte(29.35, 1, -1)
        self.assertIsNone(lm.aplicar_dte(f, VENTAS, total, iva))
        self.assertEqual(
            (f['compra'], f['iva'], f['total']), (D('-244.45'), D('-29.35'), D('-273.80'))
        )

    # Total del DTE distinto: la fila queda como se calculó
    def test_total_distinto_no_toca(self):
        f = fila(VENTAS, compra='244.46', iva_compra='29.34')
        self.assertEqual(lm.aplicar_dte(f, VENTAS, D('273.81'), D('29.35')), 'total_distinto')
        self.assertEqual((f['compra'], f['iva']), (D('244.46'), D('29.34')))

    def test_diferencia_grande_no_toca(self):
        # Importado antes de 1.9.0: tasa municipal dentro de la línea gravada
        f = fila(COMPRAS, servicio='1007.92', iva_servicio='120.95')
        self.assertEqual(lm.aplicar_dte(f, COMPRAS, D('1128.87'), D('107.51')), 'iva_grande')
        self.assertEqual(f['iva'], D('120.95'))

    # Otros impuestos (EEGSA 6EB3F1A3): de exento a «Impuestos y contribuciones»
    def test_otros_impuestos_eegsa(self):
        f = fila(COMPRAS, servicio='895.93', iva_servicio='107.51', servicio_exento='125.43')
        self.assertIsNone(lm.aplicar_dte(f, COMPRAS, D('1128.87'), D('107.51'), D('125.43')))
        self.assertEqual(f['servicio'], D('895.93'))
        self.assertEqual(f['servicio_exento'], D('0.00'))
        self.assertEqual(f['otros'], D('125.43'))
        self.assertEqual(f['iva'], D('107.51'))
        self.assertEqual(f['total'], D('1128.87'))

    def test_otros_sin_linea_exenta(self):
        f = fila(COMPRAS, servicio='1007.92', iva_servicio='120.95')
        self.assertEqual(
            lm.aplicar_dte(f, COMPRAS, D('1128.87'), D('107.51'), D('125.43')),
            'otros_sin_linea',
        )
        self.assertEqual(f['otros'], D('0.00'))

    def test_otros_ya_en_odoo_no_duplica(self):
        # El IDP ya viene como impuesto de Odoo (columna 'otros'): no se toma de exento
        f = fila(
            COMPRAS,
            combustible='100.00',
            iva_combustible='12.00',
            otros='4.70',
            combustible_exento='3.00',
        )
        self.assertIsNone(lm.aplicar_dte(f, COMPRAS, D('119.70'), D('12.00'), D('4.70')))
        self.assertEqual(f['combustible_exento'], D('3.00'))
        self.assertEqual(f['otros'], D('4.70'))

    # Moneda extranjera: tipo de cambio del propio asiento
    def test_usd_tipo_cambio_del_asiento(self):
        tc = lm.tipo_cambio_documento(-321048.00, 41160.00)
        self.assertEqual(lm.monto_dte(41160.00, tc, 1), D('321048.00'))
        self.assertEqual(lm.monto_dte(4410.00, tc, 1), D('34398.00'))
        tc = lm.tipo_cambio_documento(-868.00, 112.00)
        self.assertEqual(lm.monto_dte(112.00, tc, 1), D('868.00'))
        self.assertEqual(lm.monto_dte(12.00, tc, 1), D('93.00'))

    # 5. Decimales: nada con más de 2 decimales
    def test_decimales(self):
        self.assertEqual(lm.dec(58.1), D('58.1'))
        self.assertEqual(lm.r2(0.125), D('0.13'))
        self.assertEqual(lm.sumar([0.1, 0.1, 0.1]), D('0.30'))
        self.assertEqual(lm.a_float(6579029.240000144), 6579029.24)
        f = fila(VENTAS, compra='220.0857', iva_compra='26.41027')
        lm.a_float_fila(f, VENTAS)
        for clave, valor in f.items():
            if isinstance(valor, float):
                self.assertEqual(valor, round(valor, 2), clave)
        self.assertNotIn('iva_col', f)

    def test_totales_suman_filas(self):
        totales = lm.totales_vacios(VENTAS)
        for _i in range(3):
            f = fila(VENTAS, compra='0.1', iva_compra='0.01', servicio_exento='0.2', otros='0.05')
            lm.acumular_totales(totales, f, VENTAS)
        self.assertEqual(totales['compra']['neto'], D('0.30'))
        self.assertEqual(totales['compra']['iva'], D('0.03'))
        self.assertEqual(totales['servicio']['exento'], D('0.60'))
        self.assertEqual(totales['otros']['total'], D('0.15'))
        self.assertEqual(totales['general']['total'], D('1.08'))
