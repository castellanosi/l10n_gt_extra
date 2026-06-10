# -*- encoding: utf-8 -*-
{
    'name': 'Guatemala - reportes y funcionalidad extra',
    'version': '19.0.5.46',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
        Reportes requeridos por la SAT y otra funcionalidad extra para llevar
        la contabilidad en Guatemala. Compatible con Odoo 17, 18 y 19.

        Reportes incluidos:
        - Libro de Banco
        - Libro de Compras
        - Libro de Ventas
        - Libro Diario
        - Libro Mayor
        - Reporte de Inventario
        - Reporte de Partidas
        - ISR Retenciones
        - Balanza de Comprobación (Balance de Saldos)
        - Estado de Cuenta por Cliente / Proveedor
        - Facturas Electrónicas FEL
        - Conciliación Bancaria Cuadrática
        - Libro Pequeño Contribuyente (Compras/Ventas)
        - Estado de Resultados
        - Balance General
    """,
    'author': 'AI Guatemala',
    'website': '',
    'depends': ['l10n_gt', 'account_tax_python', 'product'],
    'data': [
        'views/account_views.xml',
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'views/product_views.xml',

        # Reportes existentes
        'report/report_views.xml',
        'report/reporte_banco_views.xml',
        'report/reporte_partida_views.xml',
        'report/reporte_compras_views.xml',
        'report/reporte_ventas_views.xml',
        'report/reporte_diario_views.xml',
        'report/reporte_mayor_views.xml',

        # Reportes nuevos
        'report/reporte_isr_views.xml',
        'report/reporte_balance_saldos_views.xml',
        'report/reporte_estado_cuenta_views.xml',
        'report/reporte_conciliacion_views.xml',
        'report/reporte_financiero_views.xml',
        'report/reporte_cuentas_cobrar_pagar_views.xml',

        # Wizards existentes
        'wizard/account_account_reporte_banco_views.xml',
        'wizard/account_journal_reporte_compras_views.xml',
        'wizard/account_account_reporte_diario_views.xml',
        'wizard/account_account_reporte_mayor_views.xml',
        'wizard/account_journal_reporte_ventas_views.xml',

        # Wizards nuevos
        'wizard/account_reporte_isr_views.xml',
        'wizard/account_reporte_balance_saldos_views.xml',
        'wizard/account_reporte_estado_cuenta_views.xml',
        'wizard/account_reporte_conciliacion_views.xml',
        'wizard/account_reporte_financiero_views.xml',
        'wizard/account_reporte_cuentas_cobrar_pagar_views.xml',

        'security/ir.model.access.csv',
    ],
    'demo': [],
    'installable': True,
    'license': 'Other OSI approved licence',
    'post_init_hook': '_update_gt_taxes',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
