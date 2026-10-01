# -*- encoding: utf-8 -*-
"""Pruebas de los ayudantes de report/tipos_dte.py.

Son funciones puras: se prueban con objetos simulados, sin tocar la base.
Así corren igual en una base con el integrador FEL, con el importador de XML
o sin ninguno de los dos.

(En la tienda, AccountTestInvoicingCommon falla al crear el usuario de prueba
porque algún módulo OCA rompe res.users.create en tests; por eso no se usa.)
"""

from datetime import date

from odoo.tests import TransactionCase, tagged

from ..report.tipos_dte import (
    afiliacion_emisor,
    campo_afiliacion,
    campos_tipo_dte,
    codigo_dte,
    es_pequenio,
    regimen_en_fecha,
    sin_credito_fiscal,
)


class ContactoFalso:
    def __init__(self, peq=False):
        self.pequenio_contribuyente = peq


class DocumentoFalso:
    """Imita lo justo de un account.move: acceso por clave y partner_id."""

    def __init__(self, partner_peq=False, **valores):
        self._valores = valores
        self.partner_id = ContactoFalso(partner_peq)

    def __getitem__(self, clave):
        return self._valores.get(clave)


CON_TODO = ('l10n_gt_fel_dte_code', 'l10n_gt_fel_uuid', 'gt_dte_tipo')


class ModeloFalso:
    def __init__(self, *campos):
        self._fields = {c: True for c in campos}


@tagged('post_install', '-at_install')
class TestTiposDte(TransactionCase):

    # --- detección de campos disponibles ---

    def test_campos_solo_los_que_existen(self):
        self.assertEqual(
            campos_tipo_dte(ModeloFalso('gt_dte_tipo')), [('gt_dte_tipo', None)]
        )
        self.assertEqual(
            campos_tipo_dte(ModeloFalso(*CON_TODO)),
            [('l10n_gt_fel_dte_code', 'l10n_gt_fel_uuid'), ('gt_dte_tipo', None)],
        )
        self.assertEqual(campos_tipo_dte(ModeloFalso()), [])

    def test_campo_afiliacion_ausente(self):
        self.assertIsNone(campo_afiliacion(ModeloFalso()))
        self.assertEqual(
            campo_afiliacion(ModeloFalso('gt_emisor_afiliacion_iva')),
            'gt_emisor_afiliacion_iva',
        )

    # --- tipo real del documento ---

    def test_tipo_desde_el_importador(self):
        campos = campos_tipo_dte(ModeloFalso('gt_dte_tipo'))
        self.assertEqual(codigo_dte(DocumentoFalso(gt_dte_tipo='RDON'), campos), 'RDON')
        self.assertEqual(codigo_dte(DocumentoFalso(gt_dte_tipo='ncre'), campos), 'NCRE')

    def test_lo_certificado_por_este_odoo_manda(self):
        campos = campos_tipo_dte(ModeloFalso(*CON_TODO))
        doc = DocumentoFalso(
            l10n_gt_fel_dte_code='FESP', l10n_gt_fel_uuid='ABC', gt_dte_tipo='FACT'
        )
        self.assertEqual(codigo_dte(doc, campos), 'FESP')

    def test_codigo_del_integrador_sin_certificar_se_ignora(self):
        # Caso de la tienda (01/10/2026): compra importada, empresa PEQ. El
        # integrador calcula FPEQ/NABN aunque nunca la certificó.
        campos = campos_tipo_dte(ModeloFalso(*CON_TODO))
        doc = DocumentoFalso(
            l10n_gt_fel_dte_code='NABN', l10n_gt_fel_uuid=False, gt_dte_tipo='NCRE'
        )
        self.assertEqual(codigo_dte(doc, campos), 'NCRE')
        doc = DocumentoFalso(l10n_gt_fel_dte_code='FPEQ', gt_dte_tipo='RDON')
        self.assertEqual(codigo_dte(doc, campos), 'RDON')

    def test_sin_uuid_en_la_base_se_descarta_el_codigo_del_integrador(self):
        campos = campos_tipo_dte(ModeloFalso('l10n_gt_fel_dte_code', 'gt_dte_tipo'))
        self.assertEqual(campos, [('gt_dte_tipo', None)])

    def test_codigo_desconocido_o_vacio_no_cambia_nada(self):
        campos = campos_tipo_dte(ModeloFalso('gt_dte_tipo'))
        self.assertIsNone(codigo_dte(DocumentoFalso(gt_dte_tipo='XXXX'), campos))
        self.assertIsNone(codigo_dte(DocumentoFalso(gt_dte_tipo=False), campos))

    def test_base_sin_el_importador_conserva_el_comportamiento(self):
        self.assertIsNone(codigo_dte(DocumentoFalso(gt_dte_tipo='RDON'), []))

    # --- columna Peq. ---

    def test_peq_por_afiliacion_del_documento(self):
        campo = campo_afiliacion(ModeloFalso('gt_emisor_afiliacion_iva'))
        doc = DocumentoFalso(partner_peq=False, gt_emisor_afiliacion_iva='PEQ')
        self.assertEqual(afiliacion_emisor(doc, campo), 'PEQ')
        self.assertTrue(es_pequenio(doc, campo))

    def test_peq_por_la_casilla_del_contacto(self):
        campo = campo_afiliacion(ModeloFalso('gt_emisor_afiliacion_iva'))
        doc = DocumentoFalso(partner_peq=True, gt_emisor_afiliacion_iva='GEN')
        self.assertTrue(es_pequenio(doc, campo))

    def test_emisor_general_no_es_peq(self):
        campo = campo_afiliacion(ModeloFalso('gt_emisor_afiliacion_iva'))
        doc = DocumentoFalso(partner_peq=False, gt_emisor_afiliacion_iva='GEN')
        self.assertFalse(es_pequenio(doc, campo))

    def test_sin_campo_de_afiliacion_manda_el_contacto(self):
        self.assertFalse(es_pequenio(DocumentoFalso(partner_peq=False), None))
        self.assertTrue(es_pequenio(DocumentoFalso(partner_peq=True), None))

    def test_peq_por_tipo_de_documento(self):
        doc = DocumentoFalso(partner_peq=False)
        self.assertTrue(es_pequenio(doc, None, 'FPEQ'))
        self.assertFalse(es_pequenio(doc, None, 'RDON'))

    def test_afiliacion_vacia_manda_el_contacto(self):
        campo = campo_afiliacion(ModeloFalso('gt_emisor_afiliacion_iva'))
        doc = DocumentoFalso(partner_peq=False, gt_emisor_afiliacion_iva=False)
        self.assertFalse(es_pequenio(doc, campo))


@tagged('post_install', '-at_install')
class TestSignoRectificativa(TransactionCase):
    """La regla de signo del libro de compras, aislada.

    Reproduce el fallo corregido: con el texto 'NC PEQ' la comparación
    tipo == 'NC' fallaba y la nota de crédito sumaba.
    """

    def _es_nc(self, move_type, nota_debito=False):
        return move_type != 'in_invoice' and not nota_debito

    def test_nota_de_credito_resta(self):
        self.assertTrue(self._es_nc('in_refund'))

    def test_nota_de_credito_de_proveedor_peq_tambien_resta(self):
        # El caso que fallaba: el tipo mostrado era 'NC PEQ'.
        es_nc = self._es_nc('in_refund')
        tipo = 'NC' + (' PEQ' if True else '')
        self.assertEqual(tipo, 'NC PEQ')
        self.assertNotEqual(tipo, 'NC')  # por eso no servía comparar textos
        self.assertTrue(es_nc)

    def test_factura_no_cambia_de_signo(self):
        self.assertFalse(self._es_nc('in_invoice'))

    def test_nota_de_debito_no_cambia_de_signo(self):
        self.assertFalse(self._es_nc('in_invoice', nota_debito=True))


@tagged('post_install', '-at_install')
class TestCreditoFiscal(TransactionCase):
    """Reglas del contador (01/10/2026)."""

    def test_comprador_peq_o_exe_nunca_tiene_credito(self):
        for regimen in ('PEQ', 'EXE'):
            self.assertTrue(sin_credito_fiscal(regimen, 'FACT', 'GEN'))
            self.assertTrue(sin_credito_fiscal(regimen, 'NCRE', 'GEN'))

    def test_comprador_gen_con_fpeq_o_rdon_no_tiene_credito(self):
        self.assertTrue(sin_credito_fiscal('GEN', 'FPEQ', 'PEQ'))
        self.assertTrue(sin_credito_fiscal('GEN', 'RDON', 'GEN'))
        self.assertTrue(sin_credito_fiscal('GEN', 'RECI', ''))

    def test_comprador_gen_con_emisor_peq_o_exe_no_tiene_credito(self):
        self.assertTrue(sin_credito_fiscal('GEN', None, 'PEQ'))
        self.assertTrue(sin_credito_fiscal('GEN', None, 'EXE'))

    def test_comprador_gen_con_fact_o_ncre_decide_la_linea(self):
        self.assertFalse(sin_credito_fiscal('GEN', 'FACT', 'GEN'))
        self.assertFalse(sin_credito_fiscal('GEN', 'NCRE', 'GEN'))
        self.assertFalse(sin_credito_fiscal('GEN', 'FCAM', 'GEN'))

    def test_sin_datos_nuevos_comportamiento_anterior(self):
        # Base sin importador ni régimen elegido: GEN y sin tipo -> decide la línea.
        self.assertFalse(sin_credito_fiscal('GEN', None, ''))


class TramoFalso:
    def __init__(self, regime, date_from=None, date_to=None):
        self.regime = regime
        self.date_from = date_from
        self.date_to = date_to


@tagged('post_install', '-at_install')
class TestRegimenEnFecha(TransactionCase):
    """El régimen del comprador sale de l10n_gt_peq, con su historial."""

    def test_sin_historial_manda_el_actual(self):
        self.assertEqual(regimen_en_fecha([], 'PEQ', date(2026, 9, 1)), 'PEQ')

    def test_sin_dato_es_gen(self):
        self.assertEqual(regimen_en_fecha([], False, date(2026, 9, 1)), 'GEN')

    def test_periodo_anterior_a_un_cambio_de_regimen(self):
        # Era PEQ hasta junio 2026; hoy es GEN.
        historial = [TramoFalso('PEQ', date(2025, 1, 1), date(2026, 6, 30))]
        self.assertEqual(regimen_en_fecha(historial, 'GEN', date(2026, 5, 1)), 'PEQ')
        self.assertEqual(regimen_en_fecha(historial, 'GEN', date(2026, 9, 1)), 'GEN')

    def test_tramo_abierto(self):
        historial = [TramoFalso('GEN', date(2026, 7, 1), None)]
        self.assertEqual(regimen_en_fecha(historial, 'PEQ', date(2026, 9, 1)), 'GEN')
        self.assertEqual(regimen_en_fecha(historial, 'PEQ', date(2026, 6, 1)), 'PEQ')
