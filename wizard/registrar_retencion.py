# -*- encoding: utf-8 -*-
"""Asistente «Registrar retención» (5.62).

La retención de IVA o ISR se registra como un PAGO PARCIAL de la factura,
desde un diario de retención (banco/efectivo marcado en la pestaña Extra).
No toca la factura ni el DTE: baja el saldo de CxC/CxP igual que un pago,
y sale como pago en el estado de cuenta.

El usuario elige el diario (salen todos los de retención) y escribe el
monto de la constancia: el sistema no calcula nada (decisión del usuario,
10/11/2026: los porcentajes varían según quién retiene).

- Factura de cliente  → pago entrante → cuenta de «Pagos entrantes» del
  diario (activo: retenciones que le hicieron).
- Factura de proveedor → pago saliente → cuenta de «Pagos salientes» del
  diario (pasivo: retenciones que usted debe enterar a la SAT).
"""

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

TIPOS_FACTURA = ('out_invoice', 'in_invoice')
UMBRAL_IVA = 2500.0
NOMBRE_TIPO = {'iva': 'IVA', 'isr': 'ISR'}


def texto_aviso(tipo, total):
    """Advertencia que no bloquea: el contador decide."""
    if tipo == 'iva' and 0 < total < UMBRAL_IVA:
        return ('La factura es menor de Q2,500.00: normalmente no lleva retención '
                'de IVA. Verifique antes de registrarla.')
    return ''


def texto_memo(tipo, constancia, factura):
    """Referencia del pago: «Retención IVA · constancia N · INV/…»."""
    partes = ['Retención %s' % NOMBRE_TIPO.get(tipo, '')]
    if constancia:
        partes.append('constancia %s' % constancia)
    if factura:
        partes.append(factura)
    return ' · '.join(p.strip() for p in partes)


class RegistrarRetencionWizard(models.TransientModel):
    _name = 'l10n_gt_extra.registrar_retencion.wizard'
    _description = 'Registrar retención de IVA o ISR'

    move_id = fields.Many2one('account.move', string='Factura', required=True, readonly=True)
    company_id = fields.Many2one(related='move_id.company_id')
    currency_id = fields.Many2one(related='move_id.currency_id')
    partner_id = fields.Many2one(related='move_id.partner_id', string='Cliente / proveedor')
    es_venta = fields.Boolean(compute='_compute_es_venta')
    total_factura = fields.Monetary(related='move_id.amount_total', string='Total de la factura')
    saldo_pendiente = fields.Monetary(related='move_id.amount_residual', string='Saldo pendiente')

    journal_id = fields.Many2one(
        'account.journal', string='Diario de retención',
        domain="[('l10n_gt_retencion', '!=', False), ('type', 'in', ('bank', 'cash')),"
               " ('company_id', '=', company_id)]")
    payment_method_line_id = fields.Many2one(
        'account.payment.method.line', compute='_compute_cuenta')
    cuenta_id = fields.Many2one(
        'account.account', string='Cuenta', compute='_compute_cuenta',
        help='Cuenta de pagos pendientes del diario: «Pagos entrantes» en ventas, '
             '«Pagos salientes» en compras. Se cambia en la configuración del diario.')
    monto = fields.Monetary(
        string='Monto retenido',
        help='El monto que dice la constancia de retención.')
    fecha = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    numero_constancia = fields.Char(string='No. constancia')
    aviso = fields.Char(compute='_compute_aviso')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'journal_id' in fields_list and not res.get('journal_id') and res.get('move_id'):
            mov = self.env['account.move'].browse(res['move_id'])
            diarios = self.env['account.journal'].search([
                ('l10n_gt_retencion', '!=', False),
                ('type', 'in', ('bank', 'cash')),
                ('company_id', '=', mov.company_id.id),
            ])
            if len(diarios) == 1:   # con varios, que el usuario elija
                res['journal_id'] = diarios.id
        return res

    @api.depends('move_id.move_type')
    def _compute_es_venta(self):
        for w in self:
            w.es_venta = w.move_id.move_type == 'out_invoice'

    @api.depends('journal_id', 'move_id.move_type')
    def _compute_cuenta(self):
        for w in self:
            linea = self.env['account.payment.method.line']
            if w.journal_id:
                sentido = 'inbound' if w.move_id.move_type == 'out_invoice' else 'outbound'
                linea = w.journal_id._get_available_payment_method_lines(sentido)[:1]
            w.payment_method_line_id = linea
            w.cuenta_id = linea.payment_account_id

    @api.depends('journal_id', 'move_id')
    def _compute_aviso(self):
        for w in self:
            w.aviso = texto_aviso(w.journal_id.l10n_gt_retencion, w.move_id.amount_total)

    def _validar(self):
        self.ensure_one()
        mov = self.move_id
        moneda = mov.currency_id
        if mov.state != 'posted' or mov.move_type not in TIPOS_FACTURA:
            raise UserError('La retención solo se registra en facturas de cliente o de '
                            'proveedor ya publicadas.')
        if not self.journal_id:
            raise UserError(
                'Elija el diario de retención.\n\nSi no aparece ninguno: Contabilidad → '
                'Configuración → Diarios → el diario de retención → pestaña Extra → '
                '«Diario de retención».')
        if not self.payment_method_line_id or not self.cuenta_id:
            raise UserError(
                'El diario «%s» no tiene cuenta para %s.\n\n'
                'Abra el diario → pestaña «%s» → en la línea del método de pago, columna '
                '«Cuenta de pagos pendientes», elija la cuenta de la retención.' % (
                    self.journal_id.name,
                    'retenciones de clientes' if self.es_venta else 'retenciones a proveedores',
                    'Pagos entrantes' if self.es_venta else 'Pagos salientes'))
        if float_compare(self.monto, 0.0, precision_rounding=moneda.rounding) <= 0:
            raise UserError('Escriba el monto retenido (el de la constancia).')
        if float_compare(self.monto, mov.amount_residual, precision_rounding=moneda.rounding) > 0:
            raise UserError('El monto retenido (%s) es mayor que el saldo pendiente de la '
                            'factura (%s).' % (self.monto, mov.amount_residual))

    def action_confirmar(self):
        self._validar()
        mov = self.move_id
        tipo = self.journal_id.l10n_gt_retencion
        registro = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=mov.ids,
        ).create({
            'journal_id': self.journal_id.id,
            'payment_method_line_id': self.payment_method_line_id.id,
            'amount': self.monto,
            'payment_date': self.fecha,
            'communication': texto_memo(tipo, self.numero_constancia, mov.name),
            'payment_difference_handling': 'open',
        })
        pagos = registro._create_payments()

        if self.numero_constancia:
            actuales = [n.strip() for n in (mov.numero_retencion or '').split(',') if n.strip()]
            if self.numero_constancia not in actuales:
                actuales.append(self.numero_constancia)
                mov.numero_retencion = ', '.join(actuales)

        mov.message_post(body='Retención %s registrada como pago: %s %s (%s).' % (
            NOMBRE_TIPO.get(tipo, ''), mov.currency_id.symbol or '',
            '{:,.2f}'.format(self.monto), ', '.join(pagos.mapped('name'))))
        return {'type': 'ir.actions.act_window_close'}
