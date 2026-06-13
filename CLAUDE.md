# CLAUDE.md — castellanosi/l10n_gt_extra

> Contexto específico de este módulo para Claude Code.
> Colocar en la raíz del repo: `/opt/odoo-docker/addons/l10n_gt_extra/CLAUDE.md`

---

## Qué es este módulo

Extensión de la localización oficial de Guatemala (`l10n_gt`) para Odoo 18/19 CE.
Agrega reportes SAT, ajustes contables y funcionalidades específicas del mercado guatemalteco.

- **Versión actual:** 5.48
- **Ramas activas:** `18.0` y `19.0`
- **Depende de:** `l10n_gt` (oficial Odoo), `account`
- **NO debe depender de:** `l10n_gt_peq`, `gt_tax_regime` ni ningún módulo hijo

## Regla de independencia — CRÍTICA

`l10n_gt_extra` debe funcionar instalado solo, sin `l10n_gt_peq`.
Si necesitas acceder a `company.gt_tax_regime` u otros campos definidos en `l10n_gt_peq`,
usa `hasattr()` o `fields.Many2one` con `check_company` pero nunca `depends=['l10n_gt_peq']`.

En versiones anteriores se rompió esta regla accidentalmente al añadir referencias
al campo `gt_tax_regime`. Esto se corrigió en v5.46. No repetir.

---

## Qué contiene (estado actual)

### Reportes activos (14+)
Todos tienen botón `👁 Previsualizar` (preview HTML) además del PDF.

- Libro de ventas
- Libro de compras
- Retenciones ISR (clientes y proveedores)
- Retenciones IVA (clientes y proveedores)
- Estado de cuenta por cliente/proveedor
- Conciliación bancaria
- (y otros reportes SAT)

### Retenciones
- Sistema completo para retenciones ISR e IVA en ambas direcciones (cliente y proveedor)
- Campo `numero_retencion` en `account.move` para número de constancia SAT
- Cuentas de retención separadas — nunca tocar CxC/CxP directamente:
  - `1.1.03.02`, `1.1.03.03` → retenciones por cobrar
  - `2.1.02.01`, `2.1.02.02`, `2.1.02.03` → retenciones por pagar

### Conciliación bancaria
- Usa `account_bank_statement_line.is_reconciled` (NO `account_move_line.reconciled`)
- Requiere OCA `account_reconciliation_widget` (rama 18.0) — es Enterprise-only en core CE
- Wizard incluye campo `fecha_desde`
- Cuentas de retención tienen "Permitir conciliación" desactivado en la UI
  (no en código — es configuración de datos)

### Estado de cuenta
- Sub-filas de retenciones y pagos bajo cada factura
- Lógica Debe/Haber/Saldo correcta
- `amount_total` ya es post-retención → reconstruir bruto como `neto_CxC + Σretenciones`

---

## Trampas conocidas en este módulo

- **`&nbsp;` en XML:** inválido en templates Odoo → usar `&#160;`
- **Campos traducidos:** `Char(translate=True)` se guarda como `jsonb` en PostgreSQL
  → para LIKE/LOWER usar `campo::text`
- **Asientos publicados:** bloquean ORM → llamar `button_draft()` antes de modificar
- **Reportes eliminados:** se quitaron 3 reportes obsoletos en v5.45 — no restaurar
- **Nombres de tablas de acciones:**
  - `ir.actions.act_window` → tabla `ir_act_window`
  - `ir.actions.report` → tabla `ir_act_report_xml`

## Combustible (facturas con IDP)

Estructura específica de Guatemala para facturas de combustible:
```
Base combustible  → cuenta de gasto
IVA crédito fiscal → cuenta de activo (1.1.05.x)
IDP/Petróleo      → cuenta de gasto separada
= Total CxP
```
El IVA de combustible SÍ es crédito fiscal válido para régimen GEN.

---

## Workflow de cambios

```bash
# 1. Editar en addons/ (git-tracked)
#    NUNCA editar en custom_addons/ (son symlinks)

# 2. Validar Python antes de reiniciar
python3 -c "import ast; ast.parse(open('models/mi_archivo.py').read())"

# 3. Reiniciar y actualizar
cd /opt/odoo-docker
docker compose restart odoo
# Si hay campos nuevos:
docker compose exec odoo odoo -d odoo_conta -u l10n_gt_extra --stop-after-init \
  -p 8069 --db_password=$(grep DB_PASSWORD .env | cut -d= -f2)

# 4. Verificar en logs
docker compose logs -f --tail=30 odoo | grep -E "ERROR|WARNING|l10n_gt_extra"

# 5. Bump de versión en __manifest__.py (18.0.5.X → 18.0.5.X+1)

# 6. Push a GitHub (ambas ramas: 18.0 y 19.0)
#    En 19.0: ajustar version string de 18.0.x a 19.0.x
```

---

## Historial de versiones clave

| Versión | Cambio principal |
|---------|-----------------|
| 5.48 | Versión actual estable |
| 5.46–5.48 | Corrección conciliación bancaria; eliminación dependencia `gt_tax_regime` |
| 5.45 | Eliminación 3 reportes obsoletos; botón Preview en todos los wizards |
| 5.44 | `numero_retencion`; Estado de cuenta con sub-filas retenciones/pagos |

