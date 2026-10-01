# -*- encoding: utf-8 -*-
# Catálogo de tipos de DTE de la SAT (Manual FEL, "Códigos tipos de DTE").
# Lo usan los libros de compras y ventas para mostrar el tipo real de cada
# documento. Si el documento no trae un código conocido, el reporte usa la
# lógica anterior (FACT / NC / ND).

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


# Campos donde otros módulos guardan el tipo REAL de cada DTE, en orden de
# prioridad. Cada entrada es (campo, requisito): el campo solo cuenta si el
# documento tiene un valor en el campo requisito.
# - l10n_gt_fel_dte_code (odoo_fel_integrador): SOLO si el documento tiene
#   l10n_gt_fel_uuid, es decir, si ESTE Odoo lo certificó (ventas, o una
#   factura especial FESP en compras). El integrador también calcula el campo
#   en facturas de proveedor según el régimen de la EMPRESA (empresa PEQ ->
#   FPEQ, rectificativa -> NABN) aunque nunca las certificó: sin el requisito,
#   el libro de compras salía todo FPEQ/NABN (tienda, 01/10/2026, v5.54).
# - gt_dte_tipo (gt_xml_importer >= 18.0.1.2.0): campo ALMACENADO, no
#   calculado, tomado del XML (dte:DatosGenerales/@Tipo) o de la columna
#   "Tipo" del Excel. Es el tipo del documento recibido.
#
# NO usar fel_tipo_documento ni fel_afiliacion_iva (módulo l10n_gt_peq): son
# campos CALCULADOS desde el régimen de la EMPRESA, no del documento.
# Comprobado en producción el 29/09/2026 (v18.0.5.51, revertido en 5.52).
CAMPOS_TIPO_DTE = (
    ('l10n_gt_fel_dte_code', 'l10n_gt_fel_uuid'),
    ('gt_dte_tipo', None),
)

# Documentos emitidos por pequeños contribuyentes (van a la columna Peq.).
TIPOS_PEQ = {'FPEQ', 'FCAP', 'FAPE', 'FCPE'}

# Documentos que NO dan crédito fiscal a quien los recibe, aunque la línea en
# Odoo traiga IVA: los de pequeño contribuyente y los recibos (RDON, RECI).
TIPOS_SIN_CREDITO = TIPOS_PEQ | {'RDON', 'RECI'}

# Regímenes de IVA, con las MISMAS claves que res.company.gt_tax_regime de
# l10n_gt_peq (la única fuente del régimen; aquí no se guarda). Una empresa PEQ
# o EXE no recibe crédito fiscal: todas sus compras van a columnas exentas. Un
# emisor PEQ o EXE no genera crédito.
REGIMENES_IVA = [
    ('GEN', 'General'),
    ('PEQ', 'Pequeño contribuyente'),
    ('EXE', 'Exento'),
]
REGIMENES_SIN_CREDITO = ('PEQ', 'EXE')

# Campo con la afiliación de IVA de QUIEN EMITIÓ el documento (el proveedor en
# compras, la propia empresa en ventas). Lo guarda gt_xml_importer desde el XML
# (dte:Emisor/@AfiliacionIVA) o la columna "Regimen" del Excel.
# Valores: GEN, PEQ, EXE, AGR.
CAMPO_AFILIACION = 'gt_emisor_afiliacion_iva'


def campos_tipo_dte(model):
    """Campos de tipo de DTE que existen en esta base (calcular una vez, fuera del bucle).

    Devuelve pares (campo, requisito). Si el requisito no existe en la base,
    el campo se descarta.
    """
    return [
        (c, req) for c, req in CAMPOS_TIPO_DTE
        if c in model._fields and (req is None or req in model._fields)
    ]


def campo_afiliacion(model):
    """Nombre del campo de afiliación si existe en esta base; si no, None.

    Calcular UNA vez, fuera del bucle, igual que campos_tipo_dte().
    """
    return CAMPO_AFILIACION if CAMPO_AFILIACION in model._fields else None


def codigo_dte(move, campos):
    """Código de DTE del documento si está en el catálogo SAT; si no, None."""
    for c, req in campos:
        if req and not move[req]:
            continue
        valor = (move[c] or '').strip().upper()
        if valor in TIPOS_DTE:
            return valor
    return None


def afiliacion_emisor(move, campo):
    """Afiliación de IVA del emisor del documento ('GEN', 'PEQ', ...) o ''."""
    if not campo:
        return ''
    return (move[campo] or '').strip().upper()


def es_pequenio(move, campo, codigo=None):
    """True si el documento va en la columna de pequeño contribuyente.

    Fuentes, en este orden:
    1. El tipo de DTE del documento (FPEQ, FCAP, FAPE, FCPE).
    2. La afiliación del emisor del propio documento (dato del DTE).
    3. La casilla "Pequeño Contribuyente" del contacto (comportamiento anterior).

    Sin tipo ni afiliación queda exactamente el comportamiento anterior.
    """
    if codigo in TIPOS_PEQ:
        return True
    if afiliacion_emisor(move, campo) == 'PEQ':
        return True
    return bool(move.partner_id.pequenio_contribuyente)


def sin_credito_fiscal(regimen_comprador, codigo, afiliacion):
    """True si la compra NO da crédito fiscal: todo el monto va a exento, IVA 0.

    - La empresa que compra es PEQ o EXE: nunca recibe crédito.
    - El documento es de los que no dan crédito (FPEQ, RDON...).
    - Quien lo emitió es PEQ o EXE.
    Con comprador GEN y documento que sí da crédito (FACT, NCRE...), decide el
    impuesto de cada línea, como antes.
    """
    if regimen_comprador in REGIMENES_SIN_CREDITO:
        return True
    if codigo in TIPOS_SIN_CREDITO:
        return True
    return afiliacion in REGIMENES_SIN_CREDITO


def regimen_en_fecha(historial, regimen_actual, fecha):
    """Régimen de la empresa en una fecha.

    historial: registros con regime, date_from, date_to (company.regime.history
    de l10n_gt_peq). Si un tramo cubre la fecha, manda ese tramo; si no, el
    régimen actual. Sin dato de ninguno: GEN.
    """
    if fecha:
        for h in historial:
            if h.date_from and h.date_from > fecha:
                continue
            if h.date_to and h.date_to < fecha:
                continue
            if h.regime:
                return h.regime
    return regimen_actual or 'GEN'
