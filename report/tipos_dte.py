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


# Campos donde otros módulos guardan el tipo REAL de cada DTE, en orden de prioridad.
# - l10n_gt_fel_dte_code: odoo_fel_integrador (tipo con el que se certificó el documento).
#
# NO usar fel_tipo_documento ni fel_afiliacion_iva (módulo l10n_gt_peq): son campos
# CALCULADOS desde el régimen de la EMPRESA, no del documento. En una empresa PEQ
# todas las compras salen FPEQ y una entidad que emite recibos por donación sale FACT.
# Comprobado en producción el 29/09/2026 (v18.0.5.51, revertido en 5.52).
#
# Cuando el importador de XML guarde el tipo real del DTE en un campo propio,
# agregarlo aquí.
CAMPOS_TIPO_DTE = ('l10n_gt_fel_dte_code',)


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
