# -*- encoding: utf-8 -*-
# Catálogo de tipos de DTE de la SAT (Manual FEL, "Códigos tipos de DTE").
# Lo usan los libros de compras y ventas para mostrar el tipo de documento
# cuando la factura trae el código del integrador FEL (l10n_gt_fel_dte_code).
# Si el código no está en esta lista, el reporte usa la lógica anterior.

TIPOS_DTE = {
    'FACT': 'Factura',
    'FCAM': 'Factura Cambiaria',
    'FPEQ': 'Factura Pequeño Contribuyente',
    'FCAP': 'Factura Cambiaria Pequeño Contribuyente',
    'FESP': 'Factura Especial',
    'NABN': 'Nota de Abono',
    'RDON': 'Recibo por Donación',
    'RECI': 'Recibo',
    'NDEB': 'Nota de Débito',
    'NCRE': 'Nota de Crédito',
    'FACA': 'Factura Contribuyente Agropecuario',
    'FCCA': 'Factura Cambiaria Contribuyente Agropecuario',
    'FAPE': 'Factura Pequeño Contribuyente Régimen Electrónico',
    'FCPE': 'Factura Cambiaria Pequeño Contribuyente Régimen Electrónico',
    'FAAE': 'Factura Contribuyente Agropecuario Régimen Electrónico Especial',
    'FCAE': 'Factura Cambiaria Contribuyente Agropecuario Régimen Electrónico Especial',
    'CIVA': 'Constancia de Exención del IVA',
    'CAIS': 'Constancia de Adquisición de Insumos y Servicios',
}


# Campos donde otros módulos guardan el tipo de DTE, en orden de prioridad:
# - l10n_gt_fel_dte_code: odoo_fel_integrador (facturas emitidas por la tienda)
# - fel_tipo_documento: importador de XML (facturas cargadas desde el DTE)
CAMPOS_TIPO_DTE = ('l10n_gt_fel_dte_code', 'fel_tipo_documento')


def campos_tipo_dte(model):
    """Campos de tipo de DTE que existen en esta base (calcular una vez, fuera del bucle)."""
    return [c for c in CAMPOS_TIPO_DTE if c in model._fields]


def codigo_dte(move, campos):
    """Código de DTE del documento si está en el catálogo SAT; si no, None."""
    for c in campos:
        valor = (move[c] or '').strip().upper()
        if valor in TIPOS_DTE:
            return valor
    return None
