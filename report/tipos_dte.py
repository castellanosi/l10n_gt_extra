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
