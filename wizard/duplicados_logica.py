# -*- encoding: utf-8 -*-
"""Lógica pura del asistente «Depurar documentos duplicados».

No toca la base: recibe una lista de diccionarios (uno por documento) y
decide qué se conserva, qué se borra y qué debe revisarse a mano. Así se
prueba con datos simulados (tests/test_duplicados.py).

Cada documento es un dict con:
    id, company_id, move_type, state ('draft' / 'posted' / 'cancel'),
    partner_id, nit, uuid, serie, numero, total,
    con_pagos (bool), con_hash (bool), bloqueado (bool: fecha de bloqueo)
"""

# Motivos (se muestran tal cual al usuario)
M_DISTINTOS = 'Mismo DTE con distinto NIT o total'
M_VARIOS_PAGOS = 'Más de una copia tiene pagos'
M_PAGOS = 'Tiene pagos o conciliación'
M_HASH = 'Asiento inalterable (hash)'
M_BLOQUEO = 'Fecha dentro del período bloqueado'

_ORDEN_ESTADO = {'posted': 0, 'draft': 1, 'cancel': 2}


def _txt(valor):
    """Texto normalizado: mayúsculas, sin espacios ni guiones."""
    if not valor:
        return ''
    return str(valor).upper().replace(' ', '').replace('-', '').strip()


def clave(doc):
    """Clave que identifica el DTE, o None si no se puede identificar.

    1) UUID (número de autorización), que es único ante la SAT.
    2) Si no hay UUID: serie + número + NIT de la contraparte.
    Siempre dentro de la misma compañía y el mismo tipo de documento.
    """
    base = (doc['company_id'], doc['move_type'])
    uuid = _txt(doc.get('uuid'))
    if uuid:
        return base + ('UUID', uuid)
    serie, numero = _txt(doc.get('serie')), _txt(doc.get('numero'))
    if serie and numero:
        return base + ('SERIE', serie, numero, _txt(doc.get('nit')))
    return None


def _a_conservar(grupo):
    """La copia con pagos; si no hay, la publicada más antigua (id más bajo)."""
    return min(
        grupo,
        key=lambda d: (not d['con_pagos'], _ORDEN_ESTADO.get(d['state'], 9), d['id']),
    )


def clasificar(docs):
    """Agrupa los documentos por DTE y decide qué hacer con cada copia.

    Devuelve un dict:
        grupos:    número de DTE con más de una copia
        conservar: ids que se quedan (uno por grupo resuelto)
        borrar:    ids de las copias que se pueden eliminar
        revisar:   lista de (ids del grupo o del documento, motivo)
        sin_clave: documentos que no tienen UUID ni serie-número
    """
    grupos = {}
    sin_clave = 0
    for doc in docs:
        k = clave(doc)
        if k is None:
            sin_clave += 1
            continue
        grupos.setdefault(k, []).append(doc)

    res = {'grupos': 0, 'conservar': [], 'borrar': [], 'revisar': [], 'sin_clave': sin_clave}
    for grupo in grupos.values():
        if len(grupo) < 2:
            continue
        res['grupos'] += 1
        ids = sorted(d['id'] for d in grupo)

        # Las copias deben ser iguales en NIT y total. Se compara el NIT y no el
        # contacto: una carga doble puede crear dos contactos con el mismo NIT
        # (conta_gen, 350 pares, 09/11/2026).
        if len({_txt(d.get('nit')) for d in grupo}) > 1 or len({round(d['total'] or 0.0, 2) for d in grupo}) > 1:
            res['revisar'].append((ids, M_DISTINTOS))
            continue
        if sum(1 for d in grupo if d['con_pagos']) > 1:
            res['revisar'].append((ids, M_VARIOS_PAGOS))
            continue

        queda = _a_conservar(grupo)
        res['conservar'].append(queda['id'])
        for doc in sorted(grupo, key=lambda d: d['id']):
            if doc is queda:
                continue
            if doc['con_pagos']:
                res['revisar'].append(([doc['id']], M_PAGOS))
            elif doc['con_hash']:
                res['revisar'].append(([doc['id']], M_HASH))
            elif doc['bloqueado']:
                res['revisar'].append(([doc['id']], M_BLOQUEO))
            else:
                res['borrar'].append(doc['id'])
    res['borrar'].sort()
    res['conservar'].sort()
    return res
