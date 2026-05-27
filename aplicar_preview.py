#!/usr/bin/env python3
"""
Ejecutar desde: /opt/odoo-docker/addons/l10n_gt_extra
Agrega botón Previsualizar HTML a todos los wizards de l10n_gt_extra.
"""
import re, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
WIZARD = os.path.join(BASE, 'wizard')

if not os.path.isdir(WIZARD):
    print(f"❌ No encontré la carpeta wizard en {BASE}")
    print(f"   Ejecutá este script desde /opt/odoo-docker/addons/l10n_gt_extra")
    sys.exit(1)

# ── 1. Métodos Python ─────────────────────────────────────────────────────────

METHODS = {
    'account_account_reporte_banco.py':      [('preview_report', 'l10n_gt_extra.reporte_banco_wizard_report', False)],
    'account_account_reporte_diario.py':     [('preview_report', 'l10n_gt_extra.reporte_diario_wizard_report', False)],
    'account_account_reporte_inventario.py': [('preview_report', 'l10n_gt_extra.reporte_inventario_wizard_report', False)],
    'account_account_reporte_mayor.py':      [('preview_report', 'l10n_gt_extra.reporte_mayor_wizard_report', False)],
    'account_journal_reporte_compras.py':    [('preview_report', 'l10n_gt_extra.reporte_compras_wizard_report', True)],
    'account_journal_reporte_ventas.py':     [('preview_report', 'l10n_gt_extra.ventas_reporte_wizard_report', True)],
    'account_reporte_balance_saldos.py':     [('preview_report', 'l10n_gt_extra.reporte_balance_saldos_wizard_report', True)],
    'account_reporte_conciliacion.py':       [('preview_report', 'l10n_gt_extra.reporte_conciliacion_wizard_report', False)],
    'account_reporte_estado_cuenta.py':      [('preview_report', 'l10n_gt_extra.reporte_estado_cuenta_wizard_report', False)],
    'account_reporte_fel.py':                [('preview_report', 'l10n_gt_extra.reporte_fel_wizard_report', True)],
    'account_reporte_isr.py':                [('preview_report', 'l10n_gt_extra.reporte_isr_wizard_report', True)],
    'account_reporte_pequeno.py':            [('preview_report', 'l10n_gt_extra.reporte_pequeno_wizard_report', True)],
    # Dos clases en el mismo archivo:
    'account_reporte_cuentas_cobrar_pagar.py': [
        ('preview_report',  'l10n_gt_extra.reporte_cuentas_cobrar_wizard_report', True),
        ('preview_report',  'l10n_gt_extra.reporte_cuentas_pagar_wizard_report',  True),
    ],
    'account_reporte_financiero.py': [
        ('preview_report', 'l10n_gt_extra.reporte_estado_resultados_wizard_report', False),
        ('preview_report', 'l10n_gt_extra.reporte_balance_general_wizard_report',   False),
    ],
}

def preview_block(ref, landscape):
    ctx = ".with_context(landscape=True)" if landscape else ""
    return (
        f"\n    def preview_report(self):\n"
        f"        data = {{\n"
        f"            'ids': [],\n"
        f"            'model': self._name,\n"
        f"            'form': self.read()[0],\n"
        f"        }}\n"
        f"        action = self.env.ref('{ref}'){ctx}.report_action(self, data=data)\n"
        f"        action['report_type'] = 'qweb-html'\n"
        f"        return action\n"
    )

errors = []

for fname, defs in METHODS.items():
    path = os.path.join(WIZARD, fname)
    if not os.path.isfile(path):
        errors.append(f"No encontrado: {fname}")
        continue

    with open(path) as f:
        content = f.read()

    # Saltar si ya tiene el método
    if 'def preview_report' in content:
        print(f"⏭  Ya tiene preview_report: {fname}")
        continue

    if len(defs) == 1:
        _, ref, ls = defs[0]
        block = preview_block(ref, ls)
        # Insertar antes del primer print_report_excel
        marker = '    def print_report_excel('
        idx = content.find(marker)
        if idx == -1:
            content += block
        else:
            content = content[:idx] + block + '\n' + content[idx:]
    else:
        # Dos clases: insertar antes de cada print_report_excel
        parts = content.split('    def print_report_excel(')
        if len(parts) >= 3:
            _, ref1, ls1 = defs[0]
            _, ref2, ls2 = defs[1]
            content = (
                parts[0] + preview_block(ref1, ls1) + '\n    def print_report_excel(' +
                parts[1] + preview_block(ref2, ls2) + '\n    def print_report_excel(' +
                parts[2]
            )
        else:
            for _, ref, ls in defs:
                content += preview_block(ref, ls)

    with open(path, 'w') as f:
        f.write(content)
    print(f"✅ {fname}")

# ── 2. Botón en XMLs ──────────────────────────────────────────────────────────

XML_FILES = [f.replace('.py', '_views.xml') for f in METHODS.keys()]
BTN = '                    <button name="preview_report" string="&#x1F441; Previsualizar" type="object" class="btn-secondary"/>\n'

for fname in XML_FILES:
    path = os.path.join(WIZARD, fname)
    if not os.path.isfile(path):
        errors.append(f"No encontrado XML: {fname}")
        continue

    with open(path) as f:
        content = f.read()

    if 'preview_report' in content:
        print(f"⏭  Ya tiene botón: {fname}")
        continue

    new_content = re.sub(
        r'(\s+)(<button name="print_report")',
        lambda m: '\n' + BTN + m.group(1) + m.group(2),
        content
    )
    if new_content == content:
        errors.append(f"No encontré <button name=\"print_report\"> en: {fname}")
        continue

    with open(path, 'w') as f:
        f.write(new_content)
    print(f"✅ {fname}")

# ── 3. Bump versión ───────────────────────────────────────────────────────────

manifest = os.path.join(BASE, '__manifest__.py')
with open(manifest) as f:
    mc = f.read()

# Buscar versión actual y subirla en el último dígito
m = re.search(r"'version':\s*'([\d.]+)'", mc)
if m:
    parts = m.group(1).split('.')
    parts[-1] = str(int(parts[-1]) + 1)
    new_ver = '.'.join(parts)
    mc = mc.replace(m.group(0), f"'version': '{new_ver}'")
    with open(manifest, 'w') as f:
        f.write(mc)
    print(f"✅ __manifest__.py → versión {new_ver}")

# ── Resumen ───────────────────────────────────────────────────────────────────
print()
if errors:
    print("⚠️  ADVERTENCIAS:")
    for e in errors:
        print(f"   {e}")
else:
    print("🎉 Todos los cambios aplicados correctamente.")
    print()
    print("Ahora ejecutá:")
    print("  git add -A")
    print("  git commit -m 'feat: botón Previsualizar HTML en todos los wizards'")
    print("  git push origin 18.0")
