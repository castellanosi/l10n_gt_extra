import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


def normalizar_cui(valor):
    """CUI sin espacios ni guiones. Vacío → False."""
    if not valor:
        return False
    return re.sub(r'[\s-]', '', str(valor)) or False


# Diarios de retención predeterminados (5.63). Se crean en cada empresa
# (al cargar el plan contable de Guatemala y por migración en las existentes),
# SIN cuentas de pagos entrantes/salientes: las define el contador.
CUENTA_TRANSITORIA_RET = ('1.0.01.90', 'Cuenta transitoria retenciones (no tocar)')
DIARIOS_RETENCION = (
    ('iva', 'RETENCION IVA', 'RIVA'),
    ('isr', 'RETENCION ISR', 'RISR'),
)


def codigo_libre(base, usados, largo_max=None):
    """Primer código libre: base, base2, base3… (o base+1 si es numérico con puntos)."""
    if base not in usados:
        return base
    if '.' in base:
        prefijo, ultimo = base.rsplit('.', 1)
        n = int(ultimo)
        while True:
            n += 1
            cand = '%s.%0*d' % (prefijo, len(ultimo), n)
            if cand not in usados:
                return cand
    n = 2
    while '%s%d' % (base, n) in usados:
        n += 1
    return '%s%d' % (base, n)


def cui_valido(valor):
    """Vacío es válido (el CUI es opcional); si hay valor, 13 dígitos."""
    cui = normalizar_cui(valor)
    return not cui or (len(cui) == 13 and cui.isdigit())


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_gt_cui = fields.Char(
        string='CUI',
        help='Código Único de Identificación (13 dígitos), opcional. Algunos proveedores facturan '
             'al CUI en lugar del NIT; el importador de XML lo acepta como receptor si está lleno.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'l10n_gt_cui' in vals:
                vals['l10n_gt_cui'] = normalizar_cui(vals['l10n_gt_cui'])
        return super().create(vals_list)

    def write(self, vals):
        if 'l10n_gt_cui' in vals:
            vals = dict(vals, l10n_gt_cui=normalizar_cui(vals['l10n_gt_cui']))
        return super().write(vals)

    @api.constrains('l10n_gt_cui')
    def _check_l10n_gt_cui(self):
        for company in self:
            if not cui_valido(company.l10n_gt_cui):
                raise ValidationError(_('El CUI debe tener 13 dígitos (sin contar espacios ni guiones).'))

    def update_gt_taxes(self):
        for company in self:
            Template = self.env['account.chart.template'].with_company(company)
            Template._load_data({'account.tax': Template._get_gt_extra_account_tax()})

    def _l10n_gt_crear_diarios_retencion(self):
        """
        Crea, si no existen, la cuenta transitoria de retenciones y los diarios
        RETENCION IVA / RETENCION ISR (tipo efectivo). Idempotente: si la
        empresa ya tiene un diario marcado de ese tipo, no crea otro.
        Las cuentas de «Pagos entrantes» y «Pagos salientes» quedan vacías:
        las define el contador (decisión del usuario, 16/11/2026).
        """
        for company in self:
            if not company.chart_template:
                continue   # sin plan contable no hay dónde crear la cuenta
            # Empresa activa fijada aquí (no depender de quien llama): sin
            # allowed_company_ids, Odoo 18 crea la cuenta sin empresa y la
            # rechaza (prueba del 17/11/2026; la migración sí lo pasaba).
            env = self.env(context=dict(self.env.context, allowed_company_ids=company.ids))
            Acc = env['account.account'].sudo().with_company(company)
            Jou = env['account.journal'].sudo().with_company(company)
            faltan = [d for d in DIARIOS_RETENCION if not Jou.search_count([
                ('company_id', '=', company.id), ('l10n_gt_retencion', '=', d[0])])]
            if not faltan:
                continue
            cuenta = Acc.search([('company_ids', 'in', company.ids),
                                 ('name', '=', CUENTA_TRANSITORIA_RET[1])], limit=1)
            if not cuenta:
                usados = set(Acc.search([('company_ids', 'in', company.ids)]).mapped('code'))
                cuenta = Acc.create({
                    'code': codigo_libre(CUENTA_TRANSITORIA_RET[0], usados),
                    'name': CUENTA_TRANSITORIA_RET[1],
                    'account_type': 'asset_cash',
                    # sin company_ids: with_company(empresa) la asigna. Con
                    # (6, 0, ids) Odoo 18 la rechazó (17/11/2026).
                })
            codigos = set(Jou.with_context(active_test=False).search(
                [('company_id', '=', company.id)]).mapped('code'))
            for tipo, nombre, codigo in faltan:
                codigo = codigo_libre(codigo, codigos)
                codigos.add(codigo)
                Jou.create({
                    'name': nombre,
                    'code': codigo,
                    'type': 'cash',
                    'company_id': company.id,
                    'default_account_id': cuenta.id,
                    'l10n_gt_retencion': tipo,
                })
