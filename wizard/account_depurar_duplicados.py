# -*- encoding: utf-8 -*-
"""Asistente «Depurar documentos duplicados» (5.59).

Caso que lo originó (conta_gen, BH Inversión, 23/10/2026): la misma hoja de
la SAT se importó dos veces y quedaron 4,126 ventas publicadas en pares.

Procedimiento: Analizar → Eliminar duplicados (por lotes, se repite hasta que
no quede ninguno) → Renumerar por fecha (asistente nativo de Odoo).
La decisión de qué se borra está en duplicados_logica.py (pruebas incluidas).
"""

import logging
from html import escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import duplicados_logica as dl

_logger = logging.getLogger(__name__)

TIPOS = [
    ('out_invoice', 'Facturas de venta'),
    ('out_refund', 'Notas de crédito de venta'),
    ('in_invoice', 'Facturas de proveedor'),
    ('in_refund', 'Notas de crédito de proveedor'),
]
# (campo UUID, campo serie, campo número) de los dos integradores FEL
CAMPOS_DTE = [
    ('firma_fel', 'serie_fel', 'numero_fel'),
    ('l10n_gt_fel_uuid', 'l10n_gt_fel_serie', 'l10n_gt_fel_numero'),
]
COMMIT_CADA = 100
MAX_LISTA = 50  # documentos que se listan en el resumen


class AsistenteDepurarDuplicados(models.TransientModel):
    _name = 'l10n_gt_extra.depurar_duplicados.wizard'
    _description = 'Depurar documentos duplicados'

    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True, readonly=True,
        default=lambda self: self.env.company,
    )
    tipo = fields.Selection(TIPOS, string='Tipo de documento', required=True, default='out_invoice')
    diario_id = fields.Many2one(
        'account.journal', string='Diario',
        domain="[('company_id', '=', company_id), ('type', 'in', ('sale', 'purchase'))]",
        help='Opcional. Necesario para renumerar si el tipo de documento usa varios diarios.',
    )
    fecha_desde = fields.Date(string='Desde')
    fecha_hasta = fields.Date(string='Hasta')
    lote = fields.Integer(
        string='Máximo por lote', default=500, required=True,
        help='Cuántas copias se eliminan con cada clic. Con lotes pequeños el navegador '
             'no se cuelga; se repite el botón hasta que no quede ninguna.',
    )
    analizado = fields.Boolean(readonly=True)
    num_borrar = fields.Integer(string='Copias a eliminar', readonly=True)
    eliminadas = fields.Integer(string='Eliminadas en esta sesión', readonly=True)
    resumen = fields.Html(string='Resultado', readonly=True, sanitize=False)

    # ------------------------------------------------------------------ datos

    def _dominio(self):
        self.ensure_one()
        dom = [('company_id', '=', self.company_id.id), ('move_type', '=', self.tipo)]
        if self.diario_id:
            dom.append(('journal_id', '=', self.diario_id.id))
        if self.fecha_desde:
            dom.append(('date', '>=', self.fecha_desde))
        if self.fecha_hasta:
            dom.append(('date', '<=', self.fecha_hasta))
        return dom

    def _fecha_bloqueo(self):
        """Fecha de bloqueo más reciente que aplica a este tipo de documento."""
        cia = self.company_id
        nombres = ['fiscalyear_lock_date', 'hard_lock_date']
        nombres.append('sale_lock_date' if self.tipo.startswith('out_') else 'purchase_lock_date')
        fechas = [cia[n] for n in nombres if n in cia._fields and cia[n]]
        return max(fechas) if fechas else None

    def _leer_documentos(self):
        """Lee los documentos del filtro como diccionarios para la lógica pura."""
        Move = self.env['account.move'].with_context(active_test=False)
        campos_dte = [c for c in CAMPOS_DTE if c[0] in Move._fields]
        con_hash = 'inalterable_hash' in Move._fields
        leer = ['id', 'company_id', 'move_type', 'state', 'partner_id', 'amount_total',
                'payment_state', 'date']
        for trio in campos_dte:
            leer += [c for c in trio if c in Move._fields]
        if con_hash:
            leer.append('inalterable_hash')

        filas = Move.search_read(self._dominio(), leer, order='id')
        socios = {p['id']: p['vat'] for p in self.env['res.partner'].with_context(active_test=False).search_read(
            [('id', 'in', list({f['partner_id'][0] for f in filas if f['partner_id']}))], ['vat'])}
        bloqueo = self._fecha_bloqueo()

        docs = []
        for f in filas:
            uuid = serie = numero = ''
            for c_uuid, c_serie, c_numero in campos_dte:
                uuid = uuid or f.get(c_uuid) or ''
                serie = serie or f.get(c_serie) or ''
                numero = numero or f.get(c_numero) or ''
            socio = f['partner_id'][0] if f['partner_id'] else False
            docs.append({
                'id': f['id'],
                'company_id': f['company_id'][0],
                'move_type': f['move_type'],
                'state': f['state'],
                'partner_id': socio,
                'nit': socios.get(socio) or '',
                'uuid': uuid, 'serie': serie, 'numero': numero,
                'total': f['amount_total'],
                'con_pagos': f['payment_state'] not in ('not_paid', 'invoicing_legacy', False),
                'con_hash': bool(con_hash and f.get('inalterable_hash')),
                'bloqueado': bool(bloqueo and f['date'] and f['date'] <= bloqueo),
            })
        return docs

    # ----------------------------------------------------------- presentación

    def _nombres(self, ids):
        movs = self.env['account.move'].browse(ids[:MAX_LISTA]).exists()
        texto = ', '.join(escape(m.name or str(m.id)) for m in movs)
        if len(ids) > MAX_LISTA:
            texto += ' … y %s más' % (len(ids) - MAX_LISTA)
        return texto

    def _html_resumen(self, res, extra=''):
        filas = [
            ('Documentos con copia (grupos)', res['grupos']),
            ('Se conservan', len(res['conservar'])),
            ('Copias que se pueden eliminar', len(res['borrar'])),
            ('A revisar a mano (no se tocan)', len(res['revisar'])),
            ('Sin UUID ni serie-número (no se analizan)', res['sin_clave']),
        ]
        html = extra + '<table class="table table-sm o_l10n_gt_tabla"><tbody>'
        html += ''.join('<tr><td>%s</td><td class="text-end"><b>%s</b></td></tr>' % (t, v) for t, v in filas)
        html += '</tbody></table>'
        if res['revisar']:
            html += '<p><b>A revisar a mano:</b></p><ul>'
            for ids, motivo in res['revisar'][:MAX_LISTA]:
                html += '<li>%s — %s</li>' % (self._nombres(ids), escape(motivo))
            if len(res['revisar']) > MAX_LISTA:
                html += '<li>… y %s más</li>' % (len(res['revisar']) - MAX_LISTA)
            html += '</ul>'
        if res['borrar']:
            html += '<p><b>Primeras copias que se eliminarán:</b> %s</p>' % self._nombres(res['borrar'])
        elif res['grupos'] or self.eliminadas:
            html += (
                '<div class="alert alert-warning" role="alert"><b>Siguiente paso: renumerar por fecha.</b> '
                'Ya no quedan copias por eliminar. Para que los documentos queden en orden cronológico '
                '(el primero del mes con el primer número y el último con el último), pulse '
                '<b>Renumerar por fecha</b> y en el asistente de Odoo deje «Reordenar por fecha contable» '
                'y confirme. Solo cambia el correlativo interno (INV/…); la serie y el número FEL no cambian.</div>'
            )
        return html

    def _reabrir(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': _('Depurar documentos duplicados'),
        }

    # --------------------------------------------------------------- botones

    def action_analizar(self):
        self.ensure_one()
        res = dl.clasificar(self._leer_documentos())
        self.write({
            'analizado': True,
            'num_borrar': len(res['borrar']),
            'resumen': self._html_resumen(res),
        })
        return self._reabrir()

    def _eliminar_uno(self, move, conservada):
        """Regresa a borrador y elimina una copia. Devuelve None o el motivo del fallo."""
        try:
            with self.env.cr.savepoint():
                nombre = move.name
                if move.state != 'draft':
                    move.button_draft()
                # Vaciar el número deja borrar aunque no sea el último de la secuencia
                # (lo que indica Odoo); después se renumera por fecha.
                move.write({'name': '/'})
                move.with_context(force_delete=True).unlink()
            if conservada:
                try:
                    # _message_log no envía correo ni exige correo del remitente
                    # (message_post falló en producción por eso, 09/11/2026).
                    conservada._message_log(body=_('Se eliminó la copia duplicada %s (id %s).') % (nombre, move.id))
                except Exception:  # noqa: BLE001 - la nota nunca debe contar como fallo
                    _logger.warning('Depurar duplicados: no se pudo anotar en id %s', conservada.id)
            _logger.info('Depurar duplicados: eliminada %s (id %s), se conserva id %s',
                         nombre, move.id, conservada.id if conservada else '-')
            return None
        except Exception as e:  # noqa: BLE001 - se informa el motivo al usuario
            return str(e).splitlines()[0][:200] if str(e) else e.__class__.__name__

    def action_eliminar(self):
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('Solo un administrador de contabilidad puede eliminar duplicados.'))
        # Se vuelve a analizar justo antes: nunca se borra con datos viejos.
        docs = self._leer_documentos()
        res = dl.clasificar(docs)
        if not res['borrar']:
            self.write({'num_borrar': 0, 'resumen': self._html_resumen(res)})
            return self._reabrir()

        # Copia que se conserva de cada grupo, para dejar nota en su historial.
        por_clave = {}
        for d in docs:
            k = dl.clave(d)
            if k and d['id'] in res['conservar']:
                por_clave[k] = d['id']
        conservar_de = {d['id']: por_clave.get(dl.clave(d)) for d in docs if d['id'] in res['borrar']}

        Move = self.env['account.move']
        ids = res['borrar'][:max(self.lote, 1)]
        ok, fallos = 0, []
        for i, mid in enumerate(ids, 1):
            move = Move.browse(mid).exists()
            if not move:
                continue
            motivo = self._eliminar_uno(move, Move.browse(conservar_de.get(mid)).exists())
            if motivo:
                fallos.append(([mid], motivo))
            else:
                ok += 1
            if i % COMMIT_CADA == 0 and not self.env.registry.in_test_mode():
                self.env.cr.commit()  # pylint: disable=invalid-commit

        total_eliminadas = self.eliminadas + ok
        res = dl.clasificar(self._leer_documentos())
        res['revisar'] = fallos + res['revisar']
        aviso = '<div class="alert alert-success" role="status">Se eliminaron <b>%s</b> copias en este lote' % ok
        if res['borrar']:
            aviso += '; quedan <b>%s</b>. Pulse otra vez «Eliminar duplicados».' % len(res['borrar'])
        aviso += '</div>'
        self.write({
            'eliminadas': total_eliminadas,
            'num_borrar': len(res['borrar']),
            'resumen': self._html_resumen(res, aviso),
        })
        return self._reabrir()

    def action_renumerar(self):
        """Abre el asistente nativo «Resecuenciar» de Odoo, con «por fecha contable»."""
        self.ensure_one()
        movs = self.env['account.move'].search(self._dominio() + [('state', '!=', 'draft')], order='date, id')
        if not movs:
            raise UserError(_('No hay documentos publicados en el filtro.'))
        if len(movs.journal_id) > 1:
            raise UserError(_(
                'Estos documentos están en varios diarios (%s). Elija uno en «Diario» y vuelva a pulsar '
                '«Renumerar por fecha»; repita con cada diario.') % ', '.join(movs.journal_id.mapped('name')))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.resequence.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': _('Renumerar por fecha'),
            'context': {
                'active_model': 'account.move',
                'active_ids': movs.ids,
                'default_ordering': 'date',
            },
        }

    @api.onchange('tipo', 'diario_id', 'fecha_desde', 'fecha_hasta')
    def _onchange_filtro(self):
        self.analizado = False
        self.num_borrar = 0
        self.resumen = False
