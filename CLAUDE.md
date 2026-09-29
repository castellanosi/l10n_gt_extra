# CLAUDE.md — castellanosi/l10n_gt_extra

> Contexto de este módulo para el asistente. Raíz del repo:
> `/opt/odoo-docker/addons/l10n_gt_extra/CLAUDE.md`.
> Se trabaja junto con `PROTOCOLO-ENTREGAS.md` (cómo se entregan,
> aplican, prueban y suben los cambios).

---

## 0. Qué es y regla que manda sobre todo

Extensión de la localización oficial de Guatemala (`l10n_gt`) para
Odoo 18/19 CE: reportes SAT (libros), estados financieros, CxC/CxP,
estado de cuenta, retenciones y conciliación bancaria.

- **Versión:** `18.0.5.50` (sep. 2026).
- **Ramas:** `18.0` (estable), `test` (pruebas), `19.0`. Flujo:
  `feature/* → test → 18.0`, con tag de versión al llevar a `18.0`.
- **Depende de:** `l10n_gt`, `account`.

**Este módulo está instalado en varios servidores de producción, con
empresas en régimen general y en pequeño contribuyente, con y sin
integrador FEL.** Por eso:

- **No añadir dependencias** en `__manifest__.py`: ni `l10n_gt_peq`,
  ni `gt_tax_regime`, ni `solucloud-odoo`, ni `odoo_fel_integrador`,
  ni `l10n_gt_fel_*`.
- Campos de otros módulos se leen **solo si existen**:
  `'campo' in Model._fields`, calculado **una vez** antes del bucle.
  Nunca `fields_get()` dentro de un bucle (fue la causa de la lentitud).
- Sin el integrador FEL, cada reporte debe dar **el mismo resultado**
  que antes de estos cambios.

(En v5.46 se rompió la independencia con `gt_tax_regime`; no repetir.)

---

## 1. Compatibilidad con los dos integradores FEL

| Dato | Integrador antiguo | `odoo_fel_integrador` |
|---|---|---|
| Firmado | `firma_fel` | `l10n_gt_fel_uuid` |
| Serie / número | `serie_fel` / `numero_fel` | `l10n_gt_fel_serie` / `l10n_gt_fel_numero` |
| Tipo de DTE | — | `l10n_gt_fel_dte_code` |
| Estado FEL | — | `l10n_gt_fel_state` (`borrador`, `enviando`, `certificado`, `error`, `anulado`) |

Los reportes entienden los dos, sin depender de ninguno.

`report/tipos_dte.py` tiene el catálogo de los 18 tipos de DTE del
manual FEL de la SAT (FACT, FCAM, FPEQ, FCAP, FESP, NABN, RDON, RECI,
NDEB, NCRE, FACA, FCCA, FAPE, FCPE, FAAE, FCAE, CIVA, CAIS). Un código
fuera de la lista se ignora y se usa la lógica anterior.

---

## 2. Estado actual de los reportes (v5.50)

### Libros de ventas y compras
- **Tipo:** el código de DTE (`FPEQ`, `NCRE`…) si la factura lo tiene;
  si no, la lógica anterior (`FACT`/`NC`/`ND`). Hay dos variables:
  `tipo` (interna, decide el signo de las NC) y `tipo_mostrar` (lo que
  se imprime). **No mezclarlas.**
- **Doc:** `serie-número` del DTE; si no, las ramas de siempre
  (rangos, referencia, gface, `firma_fel`, tickets con resolución).
- **Anuladas:** si `state == 'cancel'` **o** `l10n_gt_fel_state ==
  'anulado'`, la línea aparece con fecha, tipo y serie-número, montos
  en cero y `(ANULADA)` en la columna Doc. Compras ahora incluye las
  canceladas (antes las omitía).
- **Gravado/exento:** depende del impuesto elegido en el asistente. Para
  pequeño contribuyente se usa un impuesto «PEQ» de 0 %; seleccionando
  PEQ salen en «VENT.» con IVA 0. Aprobado por el usuario; no cambiar.
- Precálculo: campos opcionales, conjunto de ids de impuestos y tasa de
  cambio por compañía. Medido: 0.94 s → 0.05 s con 12 facturas.

### Cuentas por cobrar y por pagar
- **Antigüedad por documento:** cada factura/NC/pago sin aplicar con su
  **saldo pendiente a la fecha de corte** (importe menos lo conciliado
  con `account_partial_reconcile.max_date <= corte`), ubicado en su
  tramo según `date_maturity`. Igual que el reporte estándar de Odoo.
- Tramos: **0-30** (incluye lo no vencido; no existe columna
  «Corriente», decisión del usuario), 31-60, 61-90, +90.
- **Fecha inicial opcional:** con ella, solo documentos emitidos en el
  rango, con saldo y antigüedad a la fecha final. Sin ella, igual que
  antes.
- Verificado: total del reporte = saldo contable de CxC/CxP.
- **Agrupación por NIT normalizado** (`nit_normalizado()`: mayúsculas,
  sin guiones ni espacios). NIT vacío o `CF` **nunca** se agrupan. Se
  agrupa por `commercial_partner_id`. El nombre mostrado es el del
  contacto con el documento más reciente.

### Estado de cuenta
- Incluye **todos los contactos con el mismo NIT** y los contactos hijos
  (`_partner_ids()`); con NIT vacío o CF, solo el contacto y sus hijos.
- **Documento:** serie-número del DTE; si no hay, `ref` (número de
  factura del proveedor) o el correlativo. Pagos: referencia bancaria.
- **Concepto:** correlativo de Odoo primero (para buscarlo) · tipo de
  documento · descripción corta.
- Sub-filas de retenciones bajo cada factura; `amount_total` ya es
  post-retención → bruto = neto CxC + Σ retenciones.

### Encabezado, folio y formato (13 reportes)
Ventas, compras, diario, mayor, balanza, estado de resultados, balance
general, CxC, CxP, estado de cuenta, conciliación, retenciones ISR.

- Plantillas comunes en `report/report_views.xml`:
  - `l10n_gt_extra.encabezado_folio`: `div.header` repetido en cada
    página con empresa, NIT, dirección (de la **compañía activa**),
    nombre del reporte (variable `titulo`), período y folio.
  - `l10n_gt_extra.cuerpo_reporte`: `div.article` con el estilo común
    de tablas (Arial, 11 px, líneas visibles en PDF, cabecera repetida).
- Uso en cada plantilla, **dentro** de `web.html_container`:
  ```xml
  <t t-set="data_report_margin_top" t-value="40"/>
  <t t-set="data_report_header_spacing" t-value="34"/>
  <t t-call="l10n_gt_extra.encabezado_folio">
      <t t-set="titulo" t-value="'Libro Diario'"/>
  </t>
  <t t-call="l10n_gt_extra.cuerpo_reporte">
      <div class="page"> … </div>
  </t>
  ```
- Sin logo ni URL al pie (decisión del usuario: encabezado funcional).
  El cuerpo ya no repite empresa/NIT/período; solo datos propios del
  reporte (establecimiento del diario, cuenta bancaria, cliente…).
- Orientación: horizontal ventas, compras, balanza, CxC, CxP, ISR;
  vertical el resto. Aprobado.
- **Folio:** el `subst()` propio (en `report_views.xml`) pone en cada
  `span.l10n_gt_folio` el valor `data-folio-inicial + sitepage - 1`. En
  la vista previa se ve el folio inicial.

---

## 3. Trampas conocidas

- **`data_report_page_offset` no existe en Odoo 18**: no hace nada. El
  folio va con `span.l10n_gt_folio` + `data-folio-inicial`.
- **`web.basic_layout` NO se usa dentro de `web.html_container`**: lo
  llama por dentro y produce un `<html>` anidado. Usar
  `l10n_gt_extra.cuerpo_reporte`.
- Odoo usa **un solo** `div.header` por documento: si hay dos, se ve el
  primero. Por eso el encabezado propio sustituye al de la compañía.
- Las líneas de tabla de Bootstrap no salen en el PDF sin el diseño de
  la compañía: las da el estilo de `cuerpo_reporte`.
- **`&nbsp;` en XML es inválido** → `&#160;`.
- `Char(translate=True)` se guarda como `jsonb` → en SQL `campo::text`,
  y al leer desde SQL crudo, convertir el dict (`_to_str`, `_jsonb_str`).
- Asientos publicados bloquean el ORM → `button_draft()` antes de editar.
- Reportes eliminados en v5.45: no restaurar.
- `ir.actions.report` → tabla `ir_act_report_xml`;
  `ir.actions.act_window` → tabla `ir_act_window`.
- Conciliación bancaria: `account_bank_statement_line.is_reconciled`
  (no `account_move_line.reconciled`); requiere OCA
  `account_reconciliation_widget` (18.0).
- La migración `migrations/19.0.0.0/` no corre en 18.0 (versión menor).
- **Clon superficial:** el repo se clonó con `--depth` y solo seguía
  `18.0`. Para una rama nueva del remoto:
  `git remote set-branches --add origin <rama> && git fetch origin <rama>`.
- El aviso `<string>:34: (ERROR/3) Undefined substitution referenced:
  "---------"` al actualizar viene del texto `description` del manifest
  (docutils). Cosmético.

---

## 4. Cómo trabajar (resumen; el detalle está en PROTOCOLO-ENTREGAS.md)

| Variable | Valor en el servidor de pruebas |
|---|---|
| `<REPO>` | `/opt/odoo-docker/addons/l10n_gt_extra` |
| `<BASE>` | `tienda_odoo` (compañía de prueba: 4) |
| `<DOMINIO>` | `iaguatemala.click` |
| `<MODULOS>` | `l10n_gt_extra` |

- El repo no tiene `.pre-commit-config.yaml` ni `tests/`: se valida con
  `py_compile` y el parser XML, y se actualiza con `-u` (sin
  `--test-enable`). No introducir pre-commit en un cambio funcional.
- **Nunca `docker compose restart`** (se cuelga): siempre
  `stop && rm -f && up -d`, en bloque aparte y solo si `-u` salió limpio.
- Actualizar desde la interfaz **no** recarga el Python.
- En el shell, `with_company()` es de los registros, no del `env`:
  `env[modelo].sudo().with_company(4)`.
- Editar en `addons/` (git), nunca en `custom_addons/` (symlinks).
- Al llevar `test` a `18.0`: subir la versión del manifest y crear el
  tag `v18.0.5.X`. En `19.0` ajustar el prefijo de versión.

---

## 5. Pendientes

- **Libro de bancos e impresión de partida** no tienen folio (su
  asistente no tiene el campo). Si se piden, agregar `folio_inicial` y
  usar el encabezado común.
- **Cruce con la SAT** (propuesto, no iniciado): asistente que lea el
  Excel de DTE emitidos/recibidos del portal SAT y marque en Odoo los
  anulados. Hace falta un Excel de ejemplo y saber qué módulo importa
  los XML de compras (el importador actual no detecta anulaciones: el
  XML del DTE no cambia al anularse).
- En `tienda_odoo`, facturas 2–11 llevan IVA 12 % incluido en vez de PEQ
  (datos de prueba). En producción, revisar el impuesto de los productos.
- `INV/2026/00006` (tienda_odoo): publicada con estado FEL `error`, sin
  UUID. Dato de prueba a cancelar.

## 6. Historial

| Versión | Cambio principal |
|---|---|
| 5.50 | Tipos DTE SAT, serie-número FEL, anuladas en cero, rendimiento; CxC/CxP por documento, fecha inicial, agrupación por NIT; estado de cuenta consolidado con documentos DTE; encabezado único con folio por página y estilo común (PR #3 y #4) |
| 5.49 | Balanza: cuentas con saldo arrastrado sin movimiento |
| 5.46–5.48 | Conciliación bancaria; quitar dependencia `gt_tax_regime` |
| 5.45 | Eliminación de 3 reportes obsoletos; botón Preview |
| 5.44 | `numero_retencion`; estado de cuenta con sub-filas |
