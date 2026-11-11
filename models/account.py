# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.addons.l10n_gt_extra import a_letras
from odoo.release import version_info
from odoo.addons.l10n_gt_extra.report.fe_columnas import CLASES as CLASES_FLUJO

import datetime
import logging

class AccountMove(models.Model):
    _inherit = "account.move"

    tipo_gasto = fields.Selection([("mixto", "Mixto"), ("compra", "Compra/Bien"), ("servicio", "Servicio"), ("importacion", "Importación/Exportación"), ("combustible", "Combustible")], string="Tipo de Gasto", default="mixto")
    serie_rango = fields.Char(string="Serie Rango")
    inicial_rango = fields.Integer(string="Inicial Rango")
    final_rango = fields.Integer(string="Final Rango")
    diario_facturas_por_rangos = fields.Boolean(string="Las facturas se ingresan por rango", help="Cada factura realmente es un rango de factura y el rango se ingresa en Referencia/Descripción", related="journal_id.facturas_por_rangos")
    nota_debito = fields.Boolean(string="Nota de debito")
    numero_retencion = fields.Char(
        string='No. Constancia Retención',
        help='Número de la constancia de retención ISR o IVA emitida por el cliente/agente retenedor',
    )

    @api.constrains('inicial_rango', 'final_rango')
    def _validar_rango(self):
        for factura in self:
            if factura.diario_facturas_por_rangos:
                if int(factura.final_rango) < int(factura.inicial_rango):
                    raise ValidationError('El número inicial del rango es mayor que el final.')
                cruzados = factura.search([('serie_rango','=',factura.serie_rango), ('inicial_rango','<=',factura.inicial_rango), ('final_rango','>=',factura.inicial_rango)])
                if len(cruzados) > 1:
                    raise ValidationError('Ya existe otra factura con esta serie y en el mismo rango')
                cruzados = self.search([('serie_rango','=',factura.serie_rango), ('inicial_rango','<=',factura.final_rango), ('final_rango','>=',factura.final_rango)])
                if len(cruzados) > 1:
                    raise ValidationError('Ya existe otra factura con esta serie y en el mismo rango')
                cruzados = self.search([('serie_rango','=',factura.serie_rango), ('inicial_rango','>=',factura.inicial_rango), ('inicial_rango','<=',factura.final_rango)])
                if len(cruzados) > 1:
                    raise ValidationError('Ya existe otra factura con esta serie y en el mismo rango')

                self.name = "{}-{} al {}-{}".format(factura.serie_rango, factura.inicial_rango, factura.serie_rango, factura.final_rango)

    # Son tres los lugares desde donde se llama el calculo de impuestos (que yo sepa). Por lo cual es
    # necesario, en estos tres lugares, pasar los datos para obtener la tasa.
    def write(self, vals):
        for f in self:
            super(AccountMove, f.with_context(moneda_impuesto_id=f.currency_id, fecha_factura=f.invoice_date)).write(vals)
        return True

    # Son tres los lugares desde donde se llama el calculo de impuestos (que yo sepa). Por lo cual es
    # necesario, en estos tres lugares, pasar los datos para obtener la tasa.
    def _compute_tax_totals(self):
        for f in self:
            super(AccountMove, f.with_context(moneda_impuesto_id=f.currency_id, fecha_factura=f.invoice_date))._compute_tax_totals()

    def action_registrar_retencion(self):
        """Abre el asistente que registra una retención de IVA o ISR como pago."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registrar retención',
            'res_model': 'l10n_gt_extra.registrar_retencion.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }

class AccountAccount(models.Model):
    _inherit = "account.account"

    l10n_gt_flujo_clase = fields.Selection(
        CLASES_FLUJO,
        string="Clasificación en flujo de efectivo",
        help="Renglón del Estado de Flujo de Efectivo donde se muestra la variación de esta "
             "cuenta. Vacío: se decide por el tipo de cuenta (las cuentas transitorias de "
             "pagos y transferencias cuentan como efectivo).",
    )


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Conciliación bancaria (5.58): todo movimiento de banco se considera
    # cobrado, salvo los marcados en tránsito hasta su fecha de cobro.
    l10n_gt_en_transito = fields.Boolean(
        string="En tránsito", copy=False, index=True,
        help="Cheque, transferencia o depósito que el banco todavía no ha operado. "
             "Sale como pendiente en la conciliación bancaria hasta su fecha de cobro.",
    )
    l10n_gt_fecha_cobro = fields.Date(
        string="Fecha de cobro en banco", copy=False,
        help="Día en que el banco operó el movimiento. Desde esa fecha deja de salir "
             "pendiente en la conciliación.",
    )

    @api.constrains('l10n_gt_fecha_cobro', 'date')
    def _check_l10n_gt_fecha_cobro(self):
        for l in self:
            if l.l10n_gt_fecha_cobro and l.date and l.l10n_gt_fecha_cobro < l.date:
                raise ValidationError(
                    'La fecha de cobro en banco ({}) no puede ser anterior a la fecha del '
                    'movimiento {} ({}).'.format(
                        l.l10n_gt_fecha_cobro.strftime('%d/%m/%Y'), l.move_id.name,
                        l.date.strftime('%d/%m/%Y')))

    def write(self, vals):
        # Poner la fecha de cobro implica que estuvo en tránsito (también en la
        # edición masiva de la lista, donde no corren los onchange).
        if vals.get('l10n_gt_fecha_cobro') and 'l10n_gt_en_transito' not in vals:
            vals = dict(vals, l10n_gt_en_transito=True)
        return super().write(vals)

    # Son tres los lugares desde donde se llama el calculo de impuestos (que yo sepa). Por lo cual es
    # necesario, en estos tres lugares, pasar los datos para obtener la tasa.
    def _compute_totals(self):
        for l in self:
            super(AccountMoveLine, l.with_context(moneda_impuesto_id=l.move_id.currency_id, fecha_factura=l.invoice_date))._compute_totals()

class AccountPayment(models.Model):
    _inherit = "account.payment"

    descripcion = fields.Char(string="Descripción")
    nombre_impreso = fields.Char(string="Nombre Impreso")
    no_negociable = fields.Boolean(string="No Negociable", default=True)

    def a_letras(self, monto):
        return a_letras.num_a_letras(monto)

class AccountJournal(models.Model):
    _inherit = "account.journal"

    direccion = fields.Many2one('res.partner', string='Dirección')
    codigo_establecimiento = fields.Integer(string='Código de establecimiento')
    facturas_por_rangos = fields.Boolean(string='Las facturas se ingresan por rango', help='Cada factura realmente es un rango de factura y el rango se ingresa en Referencia/Descripción')
    usar_referencia = fields.Boolean(string='Usar referencia para libro de ventas', help='El número de la factua se ingresa en Referencia/Descripción')
    l10n_gt_retencion = fields.Selection(
        [('iva', 'Retención IVA'), ('isr', 'Retención ISR')],
        string='Diario de retención',
        help='Marca el diario (tipo banco o efectivo) que usa el botón «Retención» de las facturas. '
             'La cuenta de la retención es la de pagos pendientes del método de pago: '
             'pestaña «Pagos entrantes» para las retenciones que le hacen sus clientes (activo) y '
             '«Pagos salientes» para las que usted hace a sus proveedores (pasivo).',
    )

class AccountTax(models.Model):
    _inherit = "account.tax"

    moneda_id = fields.Many2one('res.currency', string='Moneda a Convertir')

    def _eval_tax_amount_formula(self, raw_base, evaluation_context):
        tasa = 1
        fecha_factura = self.env.context.get('fecha_factura')

        if self.moneda_id:
            tasa = self.env['res.currency']._get_conversion_rate(self.env.company.currency_id, self.moneda_id, date=fecha_factura)
        elif self.env.context.get('moneda_impuesto_id'):
            tasa = self.env['res.currency']._get_conversion_rate(self.env.company.currency_id, self.env.context.get('moneda_impuesto_id'), date=fecha_factura)

        if evaluation_context['product']:
            evaluation_context['product']['tasa_de_conversion'] = tasa
        return super()._eval_tax_amount_formula(raw_base, evaluation_context)
