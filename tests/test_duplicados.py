# -*- encoding: utf-8 -*-
"""Pruebas de wizard/duplicados_logica.py y de la validación del CUI.

Funciones puras: se prueban con diccionarios, sin tocar la base.
"""

from odoo.tests import TransactionCase, tagged

from ..models.res_company import cui_valido, normalizar_cui
from ..wizard import duplicados_logica as dl


def doc(i, uuid='U1', total=10.0, partner=1, state='posted', pagos=False, hash_=False,
        bloqueado=False, serie='', numero='', nit='CF', tipo='out_invoice', cia=1):
    return {'id': i, 'company_id': cia, 'move_type': tipo, 'state': state, 'partner_id': partner,
            'nit': nit, 'uuid': uuid, 'serie': serie, 'numero': numero, 'total': total,
            'con_pagos': pagos, 'con_hash': hash_, 'bloqueado': bloqueado}


@tagged('post_install', '-at_install')
class TestDuplicados(TransactionCase):

    def test_par_simple_conserva_el_mas_antiguo(self):
        res = dl.clasificar([doc(5), doc(9), doc(7, uuid='U2')])
        self.assertEqual(res['grupos'], 1)
        self.assertEqual(res['conservar'], [5])
        self.assertEqual(res['borrar'], [9])
        self.assertEqual(res['revisar'], [])

    def test_uuid_ignora_mayusculas_y_guiones(self):
        res = dl.clasificar([doc(1, uuid='ab-cd'), doc(2, uuid='ABCD')])
        self.assertEqual(res['borrar'], [2])

    def test_no_mezcla_tipo_ni_compania(self):
        res = dl.clasificar([doc(1), doc(2, tipo='out_refund'), doc(3, cia=2)])
        self.assertEqual(res['grupos'], 0)

    def test_respaldo_serie_numero_nit(self):
        a = doc(1, uuid='', serie='A', numero='10', nit='123')
        b = doc(2, uuid='', serie='A', numero='10', nit='123')
        c = doc(3, uuid='', serie='A', numero='10', nit='999')
        res = dl.clasificar([a, b, c])
        self.assertEqual(res['borrar'], [2])

    def test_sin_clave_no_se_analiza(self):
        res = dl.clasificar([doc(1, uuid=''), doc(2, uuid='')])
        self.assertEqual(res['sin_clave'], 2)
        self.assertEqual(res['borrar'], [])

    def test_conserva_la_copia_con_pagos(self):
        res = dl.clasificar([doc(1), doc(2, pagos=True)])
        self.assertEqual(res['conservar'], [2])
        self.assertEqual(res['borrar'], [1])

    def test_nunca_borra_con_pagos_si_hay_dos(self):
        res = dl.clasificar([doc(1, pagos=True), doc(2, pagos=True)])
        self.assertEqual(res['borrar'], [])
        self.assertEqual(res['revisar'], [([1, 2], dl.M_VARIOS_PAGOS)])

    def test_distinto_total_o_cliente_se_revisa(self):
        self.assertEqual(dl.clasificar([doc(1), doc(2, total=11.0)])['revisar'][0][1], dl.M_DISTINTOS)
        self.assertEqual(dl.clasificar([doc(1), doc(2, partner=2)])['revisar'][0][1], dl.M_DISTINTOS)

    def test_hash_y_bloqueo_no_se_borran(self):
        res = dl.clasificar([doc(1), doc(2, hash_=True), doc(3, bloqueado=True)])
        self.assertEqual(res['borrar'], [])
        self.assertEqual([m for _ids, m in res['revisar']], [dl.M_HASH, dl.M_BLOQUEO])

    def test_prefiere_publicada_sobre_cancelada(self):
        res = dl.clasificar([doc(1, state='cancel'), doc(2)])
        self.assertEqual(res['conservar'], [2])
        self.assertEqual(res['borrar'], [1])

    def test_tres_copias(self):
        res = dl.clasificar([doc(3), doc(1), doc(2)])
        self.assertEqual(res['conservar'], [1])
        self.assertEqual(res['borrar'], [2, 3])

    def test_cui(self):
        self.assertEqual(normalizar_cui(' 2345 67890 0101 '), '2345678900101')
        self.assertEqual(normalizar_cui('2345-67890-0101'), '2345678900101')
        self.assertFalse(normalizar_cui(''))
        self.assertTrue(cui_valido(False))
        self.assertTrue(cui_valido('2345 67890 0101'))
        self.assertFalse(cui_valido('12345'))
        self.assertFalse(cui_valido('23456789001AB'))
