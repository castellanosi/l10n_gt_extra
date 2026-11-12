# -*- encoding: utf-8 -*-
"""Columna del libro por línea (report/tipos_dte.columna_linea).

Función pura: corre igual con o sin gt_xml_importer instalado.
"""

from odoo.tests import TransactionCase, tagged

from ..report.tipos_dte import columna_linea


@tagged('post_install', '-at_install')
class TestColumnaLinea(TransactionCase):

    def test_mixto_sin_producto_usa_bien_servicio(self):
        # DTE mezclado del importador: «(bienes)» B y «(servicios)» S
        self.assertEqual(columna_linea('mixto', False, 'B'), 'compra')
        self.assertEqual(columna_linea('mixto', False, 'S'), 'servicio')
        self.assertEqual(columna_linea(False, False, 'S'), 'servicio')

    def test_sin_importador_igual_que_antes(self):
        # Sin gt_bien_servicio: línea sin producto cae en Bienes, como siempre
        self.assertEqual(columna_linea('mixto', False, False), 'compra')
        self.assertEqual(columna_linea('mixto', 'service'), 'servicio')
        self.assertEqual(columna_linea('mixto', 'consu'), 'compra')

    def test_producto_manda(self):
        self.assertEqual(columna_linea('mixto', 'consu', 'S'), 'compra')
        self.assertEqual(columna_linea('mixto', 'service', 'B'), 'servicio')

    def test_tipo_gasto_fijo_no_cambia(self):
        for tipo in ('compra', 'servicio', 'combustible', 'importacion'):
            self.assertEqual(columna_linea(tipo, False, 'S'), tipo)
