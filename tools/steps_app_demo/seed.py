"""Datos SINTÉTICOS para la demostración de Steps App. Se ejecuta DENTRO de una base de demostración:

    odoo-bin shell -d <base_demo> < tools/steps_app_demo/seed.py        (con DEMO_PASSWORD y DEMO_SUMMARY en el entorno)

Nunca cargar en una base productiva: el script se niega si la base no se llama «demo*» o «test*». Es idempotente.
Todas las contraseñas son la de DEMO_PASSWORD (si falta, se genera una al azar y se informa por pantalla).
"""
import json
import os
import secrets

DB = env.cr.dbname  # noqa: F821 - `env` lo entrega `odoo-bin shell`
if not (DB.startswith("demo") or DB.startswith("test") or DB.startswith("t1")):
    raise SystemExit("Se rechaza sembrar datos de demostración en la base %r (el nombre debe empezar por demo/test)." % DB)

PASSWORD = os.environ.get("DEMO_PASSWORD") or secrets.token_urlsafe(12) + "-Aa1"
DOMAIN = "demo.steps.test"
env = env(context=dict(env.context, no_reset_password=True, tracking_disable=True, mail_notrack=True))  # noqa: F821
api = env["step.app.api"]


def get_or_create(model, domain, values):
    record = env[model].sudo().search(domain, limit=1)
    return record or env[model].sudo().create(values)


def company(name):
    return get_or_create("res.company", [("name", "=", name)], {"name": name})


def internal_user(login, name, comp, *xmlids):
    groups = [env.ref("base.group_user").id] + [env.ref(x).id for x in xmlids]
    user = env["res.users"].sudo().search([("login", "=", login)], limit=1)
    values = {"name": name, "login": login, "email": login, "password": PASSWORD, "company_id": comp.id,
              "company_ids": [(6, 0, [comp.id])], "groups_id": [(6, 0, groups)]}
    return user.write(values) or user if user else env["res.users"].sudo().create(values)


def person(email, name, device="demo-seed"):
    """Persona de la app creada con el servicio real (misma ruta que el registro público), con correo verificado."""
    identity = env["step.app.identity"].sudo().search([("provider", "=", "password"), ("subject", "=", email)], limit=1)
    if not identity:
        api.register(email, PASSWORD, name, {"uuid": device, "platform": "seed", "label": "seed"})
        identity = env["step.app.identity"].sudo().search([("provider", "=", "password"), ("subject", "=", email)], limit=1)
    identity.write({"email_verified": True})
    identity.person_id._revoke_sessions("seed")  # que nadie herede sesiones del sembrado
    return identity.person_id


def membership(p, comp, **extra):
    m = env["step.app.membership"].sudo().search([("person_id", "=", p.id), ("company_id", "=", comp.id)], limit=1)
    values = {"person_id": p.id, "company_id": comp.id, "state": "active", **extra}
    if m:
        m.write(values)
        return m
    return env["step.app.membership"].sudo().create(values)


def role(xmlid):
    return env.ref("step_mobile_portal_%s" % xmlid)


def grant(m, *roles, scope=None):
    for r in roles:
        if not m.grant_ids.filtered(lambda g: g.role_id == r and not g.revoked_at):
            env["step.app.grant"].sudo().create({"membership_id": m.id, "module_id": r.module_id.id, "role_id": r.id, "scope_ids": scope or False})


R_BENEF = role("colaciones.step_app_role_colaciones_persona")
R_OPER = role("colaciones.step_app_role_colaciones_operador")
R_COND = role("mobilization.step_app_role_mobilization_conductor")
R_SUP = role("mobilization.step_app_role_mobilization_supervisor")
R_TRK = role("tracker.step_app_role_tracker_operador")

summary = {"password_note": "Contraseña de demostración en DEMO_PASSWORD (no se guarda en el repositorio).", "companies": {}, "users": {}, "persons": {}}

for key, cname in (("norte", "Agrícola Demo Norte"), ("sur", "Agrícola Demo Sur")):
    comp = company(cname)
    product = get_or_create("product.template", [("name", "=", "Almuerzo demo %s" % key)], {"name": "Almuerzo demo %s" % key, "is_meal": True})
    supplier = get_or_create("res.partner", [("name", "=", "Casino demo %s" % key)], {"name": "Casino demo %s" % key, "is_meal_supplier": True})
    totems = []
    for n in (1, 2) if key == "norte" else (1,):
        totems.append(get_or_create("step.colacion.totem", [("code", "=", "%s-T%d" % (key.upper(), n)), ("company_id", "=", comp.id)], {
            "name": "Casino %s %d" % (key, n), "code": "%s-T%d" % (key.upper(), n), "company_id": comp.id,
            "product_tmpl_id": product.id, "supplier_id": supplier.id, "identification_method": "barcode"}))
    employees = {}
    for code, name, eligible in (("1", "Beneficiaria Demo", True), ("2", "Trabajador Dos", True), ("3", "Sin Colación Demo", False), ("4", "Pasajero Cuatro", True)):
        barcode = "%s%s" % (key[:1].upper() + "EMP", code)
        employees[code] = get_or_create("hr.employee", [("barcode", "=", barcode)], {"name": "%s (%s)" % (name, key), "company_id": comp.id, "barcode": barcode, "meal_eligible": eligible})
    brand = get_or_create("fleet.vehicle.model.brand", [("name", "=", "Marca demo")], {"name": "Marca demo"})
    model = get_or_create("fleet.vehicle.model", [("name", "=", "Bus demo")], {"name": "Bus demo", "brand_id": brand.id})
    vehicle = get_or_create("fleet.vehicle", [("license_plate", "=", "DEMO-%s" % key[:1].upper())], {
        "model_id": model.id, "company_id": comp.id, "license_plate": "DEMO-%s" % key[:1].upper(), "step_max_pass": 3, "step_min_pass": 1, "step_mobilization_enabled": True})
    transporter = get_or_create("res.partner", [("name", "=", "Transportes demo %s" % key)], {"name": "Transportes demo %s" % key, "step_trans_person": True})
    route = get_or_create("hr.route", [("name", "=", "Ruta demo %s" % key), ("company_id", "=", comp.id)], {"name": "Ruta demo %s" % key, "company_id": comp.id, "desde": "Fundo", "hasta": "Planta"})
    if not route.route_line:
        for i, stop in enumerate(("Fundo", "Cruce", "Planta"), 1):
            env["hr.route.line"].sudo().create({"route_id": route.id, "name": stop, "sequence": i})
    summary["companies"][key] = {"id": comp.id, "name": cname, "org_uid": comp.step_app_org_uid, "org_code": comp.step_app_org_code,
                                 "totem_ids": [t.id for t in totems], "employee_barcodes": {c: e.barcode for c, e in employees.items()}, "vehicle_id": vehicle.id, "route_id": route.id}
    summary["companies"][key]["_objects"] = (comp, employees, transporter, route, vehicle, totems)

(norte, emp_n, trans_n, route_n, veh_n, totems_n) = summary["companies"]["norte"].pop("_objects")
(sur, emp_s, trans_s, route_s, veh_s, totems_s) = summary["companies"]["sur"].pop("_objects")

# --- Usuarios de Odoo (reales, con permisos acotados): un administrador por empresa y un usuario sin acceso ---
# Cada administrador gestiona accesos de SU empresa y puede consultar (solo lectura de grupo «Usuario») los registros de Colaciones y
# Movilización de esa empresa para comprobar el resultado; las reglas multiempresa de Odoo impiden ver la otra empresa.
ADMIN_GROUPS = ("step_mobile_portal.group_step_app_manager", "step_colaciones.group_colaciones_user", "step_mobilization.group_mobilization_user")
internal_user("admin.norte@%s" % DOMAIN, "Admin Norte", norte, *ADMIN_GROUPS)
internal_user("admin.sur@%s" % DOMAIN, "Admin Sur", sur, *ADMIN_GROUPS)
internal_user("sin.acceso@%s" % DOMAIN, "Usuario sin acceso", norte)
summary["users"] = {"admin_norte": "admin.norte@%s" % DOMAIN, "admin_sur": "admin.sur@%s" % DOMAIN, "sin_acceso": "sin.acceso@%s" % DOMAIN}

# --- Personas de la app y sus membresías (los vínculos con trabajador/conductor son EXPLÍCITOS) ---
chofer1 = get_or_create("res.partner", [("name", "=", "Chofer Uno Demo")], {"name": "Chofer Uno Demo", "step_chofer": True, "transpor_id": trans_n.id})
chofer2 = get_or_create("res.partner", [("name", "=", "Chofer Dos Demo")], {"name": "Chofer Dos Demo", "step_chofer": True, "transpor_id": trans_n.id})
chofer_s = get_or_create("res.partner", [("name", "=", "Chofer Sur Demo")], {"name": "Chofer Sur Demo", "step_chofer": True, "transpor_id": trans_s.id})

p = person("beneficiaria@%s" % DOMAIN, "Beneficiaria Demo")
m = membership(p, norte, employee_id=emp_n["1"].id); grant(m, R_BENEF)
p = person("operador@%s" % DOMAIN, "Operador Demo")
m = membership(p, norte); grant(m, R_OPER, scope=[totems_n[0].id])  # solo el tótem 1 de Norte
p = person("conductor1@%s" % DOMAIN, "Conductor Uno")
m = membership(p, norte, partner_id=chofer1.id); grant(m, R_COND)
p = person("conductor2@%s" % DOMAIN, "Conductor Dos")
m = membership(p, norte, partner_id=chofer2.id); grant(m, R_COND)
p = person("supervisor@%s" % DOMAIN, "Supervisor Demo")
m = membership(p, norte); grant(m, R_SUP)
p = person("multi@%s" % DOMAIN, "Persona Multi")
m = membership(p, norte, employee_id=emp_n["2"].id); grant(m, R_BENEF, R_TRK)
m = membership(p, sur, partner_id=chofer_s.id); grant(m, R_COND)
person("sinmembresia@%s" % DOMAIN, "Cuenta sin empresa")  # registrada, sin membresía: no ve nada
p = person("solicita@%s" % DOMAIN, "Solicita Acceso")
membership(p, norte, state="requested", request_note="Soy conductor de la ruta 3 (demostración)")

# --- Servicios asignados (dos conductores de Norte con servicios distintos, uno de Sur) ---
def trip(comp, route, vehicle, transporter, driver):
    existing = env["step.movi.registry"].sudo().search([("chofer_id", "=", driver.id), ("recorrido_id", "=", route.id), ("state", "in", ("draft", "open"))], limit=1)
    return existing or env["step.movi.registry"].sudo().create({
        "company_id": comp.id, "recorrido_id": route.id, "vehicle_id": vehicle.id, "partner_id": transporter.id, "chofer_id": driver.id, "direction": "ida"})

t1, t2, ts = trip(norte, route_n, veh_n, trans_n, chofer1), trip(norte, route_n, veh_n, trans_n, chofer2), trip(sur, route_s, veh_s, trans_s, chofer_s)
summary["trips"] = {"conductor1": t1.id, "conductor2": t2.id, "multi_sur": ts.id}

# --- Invitación pendiente para una persona que aún no se registra ---
inv = env["step.app.invitation"].sudo().search([("email", "=", "nuevo@%s" % DOMAIN), ("state", "=", "pending")], limit=1)
if not inv:
    inv = env["step.app.invitation"].sudo().create({"email": "nuevo@%s" % DOMAIN, "company_id": norte.id, "line_ids": [(0, 0, {"role_id": R_BENEF.id})]})
summary["invitation"] = {"email": inv.email, "code": inv.issue_token()}  # el código se muestra una sola vez
env.cr.commit()

print("DEMO_SEED_OK")
if os.environ.get("DEMO_SUMMARY"):
    with open(os.environ["DEMO_SUMMARY"], "w") as fh:
        json.dump({**summary, "password": PASSWORD}, fh, indent=2)  # el archivo va FUERA del repositorio
    print("Resumen escrito en", os.environ["DEMO_SUMMARY"])
