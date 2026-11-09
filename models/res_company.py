import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


def normalizar_cui(valor):
    """CUI sin espacios ni guiones. Vacío → False."""
    if not valor:
        return False
    return re.sub(r'[\s-]', '', str(valor)) or False


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
