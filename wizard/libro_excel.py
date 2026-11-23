# -*- encoding: utf-8 -*-
"""Excel de los libros de compras y ventas (desde 5.66).

- Cada celda numérica se escribe redondeada a 2 decimales con formato
  #,##0.00 (antes salía 6579029.240000144).
- Se muestran TODAS las columnas: combustible en ventas, «Impuestos y
  contribuciones» en los dos libros.
- Si el contador marcó «Incluir control»: al final el bloque «Control» y,
  si hay documentos con diferencias, la hoja «Control» con el detalle.
"""

import io

import xlsxwriter

from ..report.libro_montos import a_float, sumar


def _imp(fila_o_totales, clave):
    return sumar([fila_o_totales[clave], fila_o_totales[clave + '_exento']])


# (encabezado, función que devuelve el monto de una fila)
COLUMNAS_FILA_VENTAS = [
    ('Ventas', lambda f: f['compra']),
    ('Ventas exento', lambda f: f['compra_exento']),
    ('Servicios', lambda f: f['servicio']),
    ('Servicios exento', lambda f: f['servicio_exento']),
    ('Combustible', lambda f: f['combustible']),
    ('Combustible exento', lambda f: f['combustible_exento']),
    ('Exportaciones', lambda f: _imp(f, 'importacion')),
    ('Impuestos y contribuciones', lambda f: f['otros']),
    ('IVA', lambda f: f['iva']),
    ('Total', lambda f: f['total']),
]

COLUMNAS_FILA_COMPRAS = [
    ('Compras', lambda f: f['compra']),
    ('Compras exento', lambda f: f['compra_exento']),
    ('Servicios', lambda f: f['servicio']),
    ('Servicios exento', lambda f: f['servicio_exento']),
    ('Combustible', lambda f: f['combustible']),
    ('Combustible exento', lambda f: f['combustible_exento']),
    ('Importaciones', lambda f: _imp(f, 'importacion')),
    ('Pequeños contribuyentes', lambda f: _imp(f, 'pequeño')),
    ('Impuestos y contribuciones', lambda f: f['otros']),
    ('IVA', lambda f: f['iva']),
    ('Total', lambda f: f['total']),
]


def _totales_fila(t, compras):
    """Fila «Totales», en el mismo orden que las columnas."""
    valores = [
        t['compra']['neto'],
        t['compra']['exento'],
        t['servicio']['neto'],
        t['servicio']['exento'],
        t['combustible']['neto'],
        t['combustible']['exento'],
        sumar([t['importacion']['neto'], t['importacion']['exento']]),
    ]
    if compras:
        valores.append(sumar([t['pequeño']['neto'], t['pequeño']['exento']]))
    valores += [t['otros']['total'], t['general']['iva'], t['general']['total']]
    return valores


def generar_excel(empresa, fecha_desde, fecha_hasta, res, compras):
    """Devuelve los bytes del .xlsx del libro."""
    lineas = res['lineas']
    totales = res['totales']
    control = res.get('control')
    columnas = COLUMNAS_FILA_COMPRAS if compras else COLUMNAS_FILA_VENTAS

    f = io.BytesIO()
    libro = xlsxwriter.Workbook(f)
    hoja = libro.add_worksheet('Reporte')
    formato_fecha = libro.add_format({'num_format': 'dd/mm/yy'})
    formato_numero = libro.add_format({'num_format': '#,##0.00'})
    formato_titulo = libro.add_format({'bold': True})
    formato_rojo = libro.add_format({'num_format': '#,##0.00', 'font_color': 'red'})

    def numero(y, x, valor, formato=formato_numero):
        hoja.write_number(y, x, a_float(valor), formato)

    partner = empresa.partner_id
    hoja.write(
        0,
        0,
        'LIBRO DE COMPRAS Y SERVICIOS' if compras else 'LIBRO DE VENTAS Y SERVICIOS',
        formato_titulo,
    )
    hoja.write(2, 0, 'NUMERO DE IDENTIFICACION TRIBUTARIA')
    hoja.write(2, 1, partner.vat or '')
    hoja.write(3, 0, 'NOMBRE COMERCIAL')
    hoja.write(3, 1, partner.name or '')
    hoja.write(2, 3, 'DOMICILIO FISCAL')
    hoja.write(2, 4, partner.street or '')
    hoja.write(3, 3, 'REGISTRO DEL')
    hoja.write(3, 4, fecha_desde, formato_fecha)
    hoja.write(3, 5, 'AL')
    hoja.write(3, 6, fecha_hasta, formato_fecha)

    y = 5
    encabezados = ['Tipo', 'Fecha', 'Doc', 'Proveedor' if compras else 'Cliente', 'NIT']
    encabezados += [c[0] for c in columnas]
    for x, texto in enumerate(encabezados):
        hoja.write(y, x, texto, formato_titulo)

    for linea in lineas:
        y += 1
        hoja.write(y, 0, linea['tipo'])
        hoja.write(y, 1, linea['fecha'], formato_fecha)
        hoja.write(y, 2, linea['numero'])
        if compras:
            proveedor = linea['proveedor']
            hoja.write(y, 3, proveedor['name'] or '')
            hoja.write(y, 4, proveedor['vat'] or '')
        else:
            hoja.write(y, 3, linea['cliente'] or '')
            hoja.write(y, 4, linea['nit'] or '')
        for x, (_texto, valor) in enumerate(columnas, start=5):
            numero(y, x, valor(linea))

    y += 1
    hoja.write(y, 3, 'Totales', formato_titulo)
    for x, valor in enumerate(_totales_fila(totales, compras), start=5):
        numero(y, x, valor)

    y += 2
    hoja.write(y, 0, 'Cantidad de facturas')
    hoja.write(y, 1, totales['num_facturas'])
    y += 1
    hoja.write(y, 0, 'Total crédito fiscal' if compras else 'Total débito fiscal')
    numero(y, 1, totales['general']['iva'])

    # Resumen por tipo
    y += 2
    for x, texto in enumerate(['EXENTO', 'NETO', 'IVA', 'TOTAL'], start=3):
        hoja.write(y, x, texto, formato_titulo)
    resumen = [
        ('COMPRAS' if compras else 'BIENES', 'compra'),
        ('SERVICIOS', 'servicio'),
        ('COMBUSTIBLES', 'combustible'),
        ('IMPORTACIONES' if compras else 'EXPORTACIONES', 'importacion'),
    ]
    if compras:
        resumen.append(('PEQUEÑOS CONTRIBUYENTES', 'pequeño'))
    for texto, clave in resumen:
        y += 1
        hoja.write(y, 1, texto)
        for x, campo in enumerate(['exento', 'neto', 'iva', 'total'], start=3):
            numero(y, x, totales[clave][campo])
    y += 1
    hoja.write(y, 1, 'IMPUESTOS Y CONTRIBUCIONES')
    numero(y, 6, totales['otros']['total'])
    y += 1
    hoja.write(y, 1, 'TOTALES', formato_titulo)
    for x, campo in enumerate(['exento', 'neto', 'iva', 'total'], start=3):
        numero(y, x, totales['general'][campo])

    # Pie de control (informativo)
    if control:
        y += 2
        hoja.write(y, 0, 'CONTROL', formato_titulo)
        y += 1
        hoja.write(y, 0, 'IVA del libro (IVA de los DTE)')
        numero(y, 1, control['iva_libro'])
        y += 1
        hoja.write(y, 0, 'IVA contable de las mismas facturas')
        numero(y, 1, control['iva_contable'])
        y += 1
        hoja.write(y, 0, 'Diferencia')
        numero(y, 1, control['diferencia'])
        y += 1
        hoja.write(y, 0, '   Por redondeo del IVA de los DTE (se ajusta en la liquidación de IVA)')
        numero(y, 1, control['redondeo_dte'])
        y += 1
        hoja.write(y, 0, '   Otras diferencias (revisar antes de declarar)')
        numero(
            y,
            1,
            control['otras_diferencias'],
            formato_rojo if control['otras_diferencias'] else formato_numero,
        )
        y += 1
        hoja.write(y, 0, 'Documentos con IVA del DTE')
        hoja.write(y, 1, control['dte_usados'])
        for mensaje in control.get('mensajes', []):
            y += 1
            hoja.write(y, 0, mensaje)

        if control['documentos'] or control['hallazgos']:
            detalle = libro.add_worksheet('Control')
            fila = 0
            if control['documentos']:
                detalle.write(
                    fila,
                    0,
                    'Documentos cuyo IVA en el libro no es igual al de su asiento',
                    formato_titulo,
                )
                fila += 1
                for x, texto in enumerate(['Documento', 'IVA libro', 'IVA contable', 'Diferencia']):
                    detalle.write(fila, x, texto, formato_titulo)
                for d in control['documentos']:
                    fila += 1
                    detalle.write(fila, 0, d['numero'])
                    detalle.write_number(fila, 1, a_float(d['iva_libro']), formato_numero)
                    detalle.write_number(fila, 2, a_float(d['iva_contable']), formato_numero)
                    detalle.write_number(
                        fila, 3, a_float(sumar([d['iva_libro'], -d['iva_contable']])), formato_rojo
                    )
                fila += 2
            if control['hallazgos']:
                detalle.write(
                    fila,
                    0,
                    'Documentos con datos del DTE que no cuadran (se dejaron como se calcularon)',
                    formato_titulo,
                )
                fila += 1
                detalle.write(fila, 0, 'Documento', formato_titulo)
                detalle.write(fila, 1, 'Motivo', formato_titulo)
                for h in control['hallazgos']:
                    fila += 1
                    detalle.write(fila, 0, h['numero'])
                    detalle.write(fila, 1, h['motivo'])
            detalle.set_column(0, 0, 30)
            detalle.set_column(1, 3, 14)

    hoja.set_column(5, 5 + len(columnas), 14)
    libro.close()
    return f.getvalue()
