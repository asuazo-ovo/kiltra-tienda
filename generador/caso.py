"""Fuente única del caso Kiltra (tienda ficticia). Todo insumo, verificación y solucionario sale de aquí.

Dos generadores aleatorios separados:
- RNG_CATALOGO (semilla 20261001) reproduce exactamente el stock que ya está desplegado en Kapso.
- RNG (semilla 20261002) genera todo lo demás: clientes, pedidos, capas de stock y conversaciones.
"""
import datetime as dt
import random

# ─────────────────────────── Calendario ───────────────────────────
HOY = dt.date(2026, 9, 29)                  # martes: día en que se exporta todo
INICIO_CHATS = dt.date(2026, 9, 15)
FIN_CHATS = dt.date(2026, 9, 28)
FERIADOS = {dt.date(2026, 9, 18): "Fiestas Patrias", dt.date(2026, 9, 19): "Día de las Glorias del Ejército"}
FINDE_LARGO = (dt.datetime(2026, 9, 18, 0, 0), dt.datetime(2026, 9, 21, 0, 0))   # vie 18 a dom 20
FERIA = dt.date(2026, 9, 19)                # feria de diseño en Providencia, sábado
PLANILLA_ACTUALIZADA = dt.date(2026, 9, 21) # Nicolás actualizó el lunes 21; el lunes 28 no alcanzó
DIAS_DESPACHO = (0, 2, 4)                   # Nicolás despacha lunes, miércoles y viernes
PREVENTA_LLEGA = dt.date(2026, 11, 10)

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def habil(d):
    return d.weekday() < 5 and d not in FERIADOS


def sumar_habiles(d, n):
    while n > 0:
        d += dt.timedelta(days=1)
        if habil(d):
            n -= 1
    return d


def fecha_larga(d):
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


def fecha_corta(d):
    return f"{d.day}/{d.month}"


# ─────────────────────────── Políticas, en todas sus versiones ───────────────────────────
# Cada contradicción de la matriz (A1–A8) vive aquí una sola vez y se renderiza en los insumos.
POLITICAS = {
    "cambios_dias": {"web": 30, "instagram": 15, "cata": 15, "rocio_frecuentes": 60},
    "devoluciones": {
        "web": "Tienes 10 días desde que recibes tu pedido para devolverlo y te reembolsamos al mismo medio de pago.",
        "instagram": "No hacemos devoluciones, solo cambios 🙌",
    },
    "despacho_gratis": {"web": 49990, "instagram": 39990},      # 39.990 = promo de invierno, terminó el 31-ago
    "promo_invierno_fin": dt.date(2026, 8, 31),
    "costo_despacho": {"RM": 3990, "Regiones": 5990, "Extremo": 5990},
    "plazo_prometido": {"RM": "2 a 3 días hábiles", "Regiones": "3 a 5 días hábiles"},
    "plazo_prometido_dias": {"RM": 3, "Regiones": 5, "Extremo": 5},   # lo que calcula la web como fecha estimada
    "plazo_courier": {"RM": (2, 4), "Regiones": (3, 6), "Extremo": (7, 10)},  # hábiles desde que el courier retira
    "horario": {"web": "lunes a viernes de 9:00 a 18:00", "instagram": "Respondemos 24/7 💬",
                "cata": "lunes a viernes de 14:00 a 18:00"},
    "showroom": {"web": "Visítanos en nuestro showroom de Ñuñoa, de lunes a sábado.",
                 "real": "solo retiro con hora agendada, los sábados de 11:00 a 14:00"},
    "codigos": {"BIENVENIDA10": "10% en la primera compra, solo en la web",
                "CAMI15": "15% de la colaboración con @cami.viste, vigente hasta el 31 de agosto"},
    "promo_ig": "2 poleras básicas por $25.000 (solo en Instagram, no acumulable)",
    "medios_pago": ["Webpay crédito", "Webpay débito", "Transferencia"],
    "cobertura": {"continental": "todo Chile continental", "cotizacion": ["Isla de Pascua", "Puerto Williams"],
                  "internacional": False},
}

GUIA_TALLAS = {
    "web": {"pecho": {"XS": "80–84", "S": "86–90", "M": "92–96", "L": "98–104", "XL": "106–112"},
            "cintura": {"36": 72, "38": 76, "40": 80, "42": 84, "44": 88, "46": 92}},
    "proveedor": {"pecho": {"XS": "82–86", "S": "88–92", "M": "94–98", "L": "100–106", "XL": "108–114"},
                  "cintura": {"36": 70, "38": 74, "40": 78, "42": 82, "44": 86, "46": 90}},
}

# Lo que solo sabe Rocío (entrevista); en el «después» pasa a ser un dato de cada producto.
# Lo que dice la ficha de cada producto en la web (el «antes»: sin notas de calce, y lo de «orgánico» sin respaldo).
DESCRIPCIONES_WEB = {
    "POL-001": "100% algodón orgánico. Hecha en Chile.", "CAM-001": "100% lino.", "VES-001": "100% lino.",
    "PAN-005": "Lino y algodón.", "CHA-004": "100% lana merino.", "CHA-005": "Lana de oveja.", "ACC-001": "Lana acrílica.",
    "PAN-002": "Denim rígido, tiro alto.", "POL-003": "Calce oversize.",
}


def hora_pedido(p):
    """Hora de compra con minutos, tal como la registra la web (los minutos se derivan del número)."""
    return f"{p['hora']:02d}:{(int(p['numero'][3:]) * 7) % 60:02d}"


NOTAS_CALCE = {
    "PAN-002": "Viene una talla más chica: recomendamos pedir una talla más.",
    "POL-003": "Calce amplio (oversize): si la prefieres ajustada, pide una talla menos.",
    "CAM-001": "El lino puede encoger hasta un 2% en el primer lavado.",
    "VES-001": "Calce holgado; el largo llega bajo la rodilla.",
    "CHA-002": "Calce justo: si vas a usar polerón debajo, pide una talla más.",
}

# ─────────────────────────── Catálogo (idéntico al desplegado en Kapso) ───────────────────────────
ROPA = ["XS", "S", "M", "L", "XL"]
JEANS = ["36", "38", "40", "42", "44", "46"]
UNICA = ["Única"]

PRODUCTOS = [
    ("POL-001", "Polera básica de algodón orgánico", "poleras", 12990, ["blanco", "negro", "gris melange", "verde oliva"], ROPA[1:]),
    ("POL-002", "Polera manga larga rayada", "poleras", 15990, ["azul marino con blanco", "rojo con blanco"], ROPA[1:]),
    ("POL-003", "Polera oversize estampada", "poleras", 14990, ["negro", "arena"], ROPA[1:]),
    ("POL-004", "Polera cuello V", "poleras", 11990, ["blanco", "azul"], ROPA),
    ("POL-005", "Polera deportiva dry-fit", "poleras", 13990, ["negro", "azul"], ROPA[1:]),
    ("PLR-001", "Polerón canguro", "polerones", 29990, ["gris", "negro", "burdeo"], ROPA[1:]),
    ("PLR-002", "Polerón french terry cuello redondo", "polerones", 27990, ["crudo", "verde"], ROPA),
    ("PLR-003", "Polerón con cierre", "polerones", 32990, ["negro", "azul marino"], ROPA[1:]),
    ("CAM-001", "Camisa de lino", "camisas", 34990, ["blanco", "celeste"], ROPA[1:]),
    ("CAM-002", "Camisa leñadora de franela", "camisas", 31990, ["cuadrillé rojo", "cuadrillé verde"], ROPA[1:]),
    ("CAM-003", "Blusa fluida estampada", "camisas", 24990, ["floral azul", "floral terracota"], ROPA[:4]),
    ("PAN-001", "Jeans recto clásico", "pantalones", 39990, ["azul medio", "azul oscuro", "negro"], JEANS),
    ("PAN-002", "Jeans mom fit", "pantalones", 37990, ["azul claro", "azul medio"], JEANS[:5]),
    ("PAN-003", "Pantalón cargo", "pantalones", 35990, ["verde militar", "beige"], JEANS),
    ("PAN-004", "Pantalón de buzo", "pantalones", 22990, ["gris", "negro"], ROPA[1:]),
    ("PAN-005", "Short de lino", "pantalones", 19990, ["beige", "blanco"], ROPA[1:]),
    ("PAN-006", "Leggings", "pantalones", 19990, ["negro", "gris"], ROPA),
    ("VES-001", "Vestido midi de lino", "vestidos y faldas", 44990, ["arena", "negro"], ROPA[:4]),
    ("VES-002", "Vestido camisero", "vestidos y faldas", 39990, ["azul", "verde"], ROPA[:4]),
    ("VES-003", "Falda plisada midi", "vestidos y faldas", 27990, ["negro", "camel"], ROPA[:4]),
    ("CHA-001", "Chaqueta de mezclilla", "chaquetas", 49990, ["azul medio", "negro"], ROPA[1:]),
    ("CHA-002", "Parka acolchada liviana", "chaquetas", 69990, ["negro", "verde oliva", "azul marino"], ROPA[1:]),
    ("CHA-003", "Cortaviento impermeable", "chaquetas", 54990, ["amarillo", "azul"], ROPA[1:]),
    ("CHA-004", "Chaleco de lana merino", "chaquetas", 42990, ["gris", "crudo", "burdeo"], ROPA[1:]),
    ("CHA-005", "Poncho de lana", "chaquetas", 59990, ["crudo", "gris"], UNICA),
    ("ACC-001", "Gorro de lana", "accesorios", 12990, ["negro", "gris", "mostaza"], UNICA),
    ("ACC-002", "Bufanda tejida", "accesorios", 15990, ["gris", "burdeo"], UNICA),
    ("ACC-003", "Calcetines pack de 3", "accesorios", 7990, ["surtido"], ["35-38", "39-42", "43-46"]),
    ("ACC-004", "Bolso de lona", "accesorios", 18990, ["crudo", "negro"], UNICA),
    ("ACC-005", "Cinturón de cuero", "accesorios", 16990, ["café", "negro"], ["S/M", "L/XL"]),
]
PROD = {p[0]: {"sku": p[0], "nombre": p[1], "categoria": p[2], "precio": p[3], "colores": p[4], "tallas": p[5]}
        for p in PRODUCTOS}

RNG_CATALOGO = random.Random(20261001)
STOCK_BASE = {}   # (sku, color, talla) -> stock, tal como está en Kapso (generar.py)
for sku, nombre, cat, precio, colores, tallas in PRODUCTOS:
    color_agotado = RNG_CATALOGO.choice(colores) if len(colores) > 2 and RNG_CATALOGO.random() < 0.4 else None
    for c in colores:
        for t in tallas:
            r = RNG_CATALOGO.random()
            STOCK_BASE[(sku, c, t)] = 0 if c == color_agotado or r < 0.15 else (
                RNG_CATALOGO.randint(1, 2) if r < 0.35 else RNG_CATALOGO.randint(3, 12))

RNG = random.Random(20261002)

# ─────────────────────────── Equipo ───────────────────────────
EQUIPO = {
    "rocio": {"nombre": "Rocío Valdés", "rol": "Dueña. Diseño, compras y casi todo el WhatsApp"},
    "nicolas": {"nombre": "Nicolás Ibarra", "rol": "Socio. Bodega y despachos (lunes, miércoles y viernes)"},
    "cata": {"nombre": "Catalina Reyes", "rol": "Atención part-time, lunes a viernes de 14:00 a 18:00"},
    "agencia": {"nombre": "Trama Digital", "rol": "Agencia externa de Instagram"},
}
COURIER = "Courier Andes"

# ─────────────────────────── Clientes ───────────────────────────
NOMBRES = ["Camila", "Valentina", "Javiera", "Antonia", "Fernanda", "Catalina", "Constanza", "Francisca", "Isidora",
           "Josefa", "Martina", "Florencia", "Daniela", "Paula", "Carolina", "Macarena", "Bárbara", "Trinidad",
           "Agustina", "Emilia", "Sofía", "Renata", "Amanda", "Ignacia", "Rocío", "Pilar", "Gabriela", "Natalia",
           "Andrea", "Claudia", "Loreto", "Marcela", "Paulina", "Verónica", "Carla", "Belén", "Montserrat", "Maite",
           "Diego", "Matías", "Sebastián", "Tomás", "Ignacio", "Benjamín", "Vicente", "Felipe", "Joaquín", "Nicolás",
           "Cristóbal", "Martín", "Lucas", "Maximiliano", "Gonzalo", "Rodrigo", "Andrés", "Pablo", "Francisco",
           "Javier", "Álvaro", "Esteban", "Simón", "Bastián", "Gabriel", "Hernán", "Mauricio", "Claudio"]
APELLIDOS = ["Rojas", "Muñoz", "Soto", "González", "Díaz", "Contreras", "Silva", "Pérez", "Morales", "Fuentes",
             "Araya", "Sepúlveda", "Espinoza", "Castillo", "Tapia", "Reyes", "Gutiérrez", "Castro", "Pizarro",
             "Álvarez", "Vásquez", "Sánchez", "Fernández", "Ramírez", "Carrasco", "Gómez", "Cortés", "Herrera",
             "Núñez", "Jara", "Vergara", "Rivera", "Figueroa", "Riquelme", "García", "Miranda", "Bravo", "Vera",
             "Molina", "Vega", "Campos", "Sandoval", "Orellana", "Cárdenas", "Olivares", "Alarcón", "Gallardo",
             "Ortiz", "Garrido", "Salazar", "Guzmán", "Henríquez", "Saavedra", "Navarro", "Aguilera", "Parra",
             "Romero", "Aravena", "Vargas", "Lagos", "Paredes", "Ibáñez", "Toro", "Poblete", "Cáceres", "Valenzuela"]

COMUNAS = {  # comuna -> zona de despacho
    "Ñuñoa": "RM", "Providencia": "RM", "Las Condes": "RM", "La Reina": "RM", "Maipú": "RM", "Santiago": "RM",
    "La Florida": "RM", "Puente Alto": "RM", "Macul": "RM", "San Miguel": "RM", "Vitacura": "RM",
    "Peñalolén": "RM", "Independencia": "RM", "Recoleta": "RM", "Estación Central": "RM", "Lo Barnechea": "RM",
    "Valparaíso": "Regiones", "Viña del Mar": "Regiones", "Concepción": "Regiones", "Temuco": "Regiones",
    "Puerto Montt": "Regiones", "Antofagasta": "Regiones", "La Serena": "Regiones", "Rancagua": "Regiones",
    "Talca": "Regiones", "Valdivia": "Regiones", "Iquique": "Regiones", "Osorno": "Regiones",
    "Chillán": "Regiones", "Arica": "Regiones", "Punta Arenas": "Extremo", "Coyhaique": "Extremo",
}
COMUNAS_RM = [c for c, z in COMUNAS.items() if z == "RM"]
COMUNAS_REG = [c for c, z in COMUNAS.items() if z != "RM"]

CLIENTES = {}        # clave -> dict(nombre, telefono, email, comuna, guardado_como)
_usados = set()
_tel = iter(RNG.sample(range(1000, 9999), 400))


def _email(nombre):
    base = nombre.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n"), (" ", ".")):
        base = base.replace(a, b)
    return f"{base}@example.com"


def nuevo_cliente(clave=None, nombre=None, comuna=None, guardado=None):
    """Crea un cliente ficticio. `guardado` es cómo lo tiene Rocío en sus contactos (None = sin guardar)."""
    while nombre is None or nombre in _usados:
        nombre = f"{RNG.choice(NOMBRES)} {RNG.choice(APELLIDOS)}"
    _usados.add(nombre)
    clave = clave or f"cli{len(CLIENTES) + 1:03d}"
    comuna = comuna or (RNG.choice(COMUNAS_RM) if RNG.random() < 0.62 else RNG.choice(COMUNAS_REG))
    tel = f"+56 9 0000 {next(_tel)}"
    if guardado is None:
        r = RNG.random()
        guardado = nombre if r < 0.45 else (nombre.split()[0] + " " + RNG.choice(["clienta", "cliente", "web", "insta", "Kiltra"])
                                              if r < 0.6 else tel)
    CLIENTES[clave] = {"clave": clave, "nombre": nombre, "telefono": tel, "email": _email(nombre),
                       "comuna": comuna, "zona": COMUNAS[comuna], "guardado_como": guardado}
    return CLIENTES[clave]


# Clientes con nombre propio en el caso (los de los pedidos originales se conservan)
FIJOS = [
    ("camila", "Camila Rojas", "Ñuñoa", "Camila Rojas"), ("diego", "Diego Muñoz", "Concepción", None),
    ("valentina", "Valentina Soto", "Providencia", "Valentina Soto"), ("matias", "Matías González", "Valparaíso", None),
    ("fernanda", "Fernanda Díaz", "Temuco", "Fernanda Díaz"), ("tomas", "Tomás Contreras", "Maipú", "Tomás Contreras"),
    ("javiera", "Javiera Silva", "La Reina", "Javiera Silva"), ("ignacio", "Ignacio Pérez", "Antofagasta", None),
    ("antonia", "Antonia Morales", "Las Condes", "Antonia Morales"), ("sebastian", "Sebastián Fuentes", "Puerto Montt", None),
    ("isidora", "Isidora Fuenzalida", "Vitacura", "Isido clienta top 💛"), ("gladys", "Gladys Henríquez", "San Miguel", "Sra. Gladys"),
    ("martin", "Martín Aravena", "Las Condes", None), ("constanza", "Constanza Bravo", "Valdivia", None),
    ("florencia", "Florencia Lagos", "Macul", "Flo Lagos"), ("ext", "Daniel Walker", "Santiago", None),
]
for k, n, c, g in FIJOS:
    nuevo_cliente(k, n, c, g if g else f"+56 9 0000 {next(_tel)}")
# el teléfono guardado de los sin guardar tiene que ser su propio teléfono
for k, n, c, g in FIJOS:
    if not g:
        CLIENTES[k]["guardado_como"] = CLIENTES[k]["telefono"]


# ─────────────────────────── Pedidos de septiembre (export de la web) ───────────────────────────
def variantes(sku):
    p = PROD[sku]
    return [(sku, c, t) for c in p["colores"] for t in p["tallas"]]


TODAS = [v for p in PRODUCTOS for v in variantes(p[0])]


def proximo_despacho(fecha_pago, hora_pago):
    d = fecha_pago if hora_pago < 10 else fecha_pago + dt.timedelta(days=1)
    while not (d.weekday() in DIAS_DESPACHO and habil(d)):
        d += dt.timedelta(days=1)
    return d


PEDIDOS = []   # dicts; el número se asigna al ordenar por fecha
CLAVE_PEDIDO = {}


def _item(sku, color, talla, cant=1):
    return {"sku": sku, "producto": PROD[sku]["nombre"], "color": color, "talla": talla, "cantidad": cant,
            "precio_unitario": PROD[sku]["precio"]}


def pedido(fecha, hora, cliente, items, clave=None, medio=None, codigo=None, **forzar):
    zona = cliente["zona"]
    subtotal = sum(i["precio_unitario"] * i["cantidad"] for i in items)
    descuento = round(subtotal * 0.10) if codigo == "BIENVENIDA10" else 0
    neto = subtotal - descuento
    envio = 0 if neto >= POLITICAS["despacho_gratis"]["web"] else POLITICAS["costo_despacho"][zona]
    medio = medio or RNG.choices(POLITICAS["medios_pago"], [55, 35, 10])[0]
    p = {"clave": clave, "fecha": fecha, "hora": hora, "cliente": cliente["nombre"], "cliente_clave": cliente["clave"],
         "telefono": cliente["telefono"], "email": cliente["email"], "comuna": cliente["comuna"], "zona": zona,
         "items": items, "subtotal": subtotal, "codigo": codigo or "", "descuento": descuento, "envio": envio,
         "total": neto + envio, "medio_pago": medio, "courier": "", "seguimiento": "", "fecha_despacho": None,
         "fecha_estimada": sumar_habiles(fecha, POLITICAS["plazo_prometido_dias"][zona]), "fecha_entrega": None,
         "estado": "", "nota_interna": ""}
    # pago: transferencias se confirman a mano entre 0 y 2 días después
    pago = fecha if medio != "Transferencia" else fecha + dt.timedelta(days=RNG.choice([0, 1, 1, 2]))
    desp = proximo_despacho(pago, hora if pago == fecha else 9)
    lo, hi = POLITICAS["plazo_courier"][zona]
    entrega = sumar_habiles(desp, RNG.randint(lo, hi))
    p.update(fecha_pago=pago, fecha_despacho=desp, fecha_entrega=entrega)
    p.update(forzar)
    PEDIDOS.append(p)
    if clave:
        CLAVE_PEDIDO[clave] = p
    return p


def _estado(p, hoy=HOY):
    """Estado al exportar (eventos hasta el día anterior a HOY)."""
    if p["estado"]:
        return p["estado"]
    lim = hoy - dt.timedelta(days=1)
    if p["fecha_entrega"] and p["fecha_entrega"] <= lim:
        return "entregado"
    if p["fecha_despacho"] and p["fecha_despacho"] <= lim:
        return "despachado"
    if p["fecha_pago"] <= lim:
        return "en preparación"
    return "pago pendiente" if p["medio_pago"] == "Transferencia" else "pagado"


def estado_en(p, d):
    """Estado del pedido en la fecha d (para que las respuestas de los chats calcen con el export)."""
    if p.get("estado") in ("cancelado", "pago rechazado") and d >= p["fecha"]:
        return p["estado"]
    if p["fecha_entrega"] and p["fecha_entrega"] <= d and p.get("estado") not in ("pagado", "preventa", "pago pendiente"):
        return "entregado"
    if p["fecha_despacho"] and p["fecha_despacho"] <= d and p.get("estado") not in ("pagado", "preventa", "pago pendiente"):
        return "despachado"
    return "en preparación"


def _items_al_azar(n=None):
    n = n or RNG.choices([1, 2, 3], [62, 30, 8])[0]
    out = []
    for _ in range(n):
        v = RNG.choice(TODAS)
        if v[0] == "PLR-001" and v[1] == "burdeo" or v[0] == "CHA-002" and v[1] == "verde oliva":
            v = ("POL-001", "negro", "M")
        out.append(_item(*v, cant=RNG.choices([1, 2], [88, 12])[0]))
    return out


def _construir_pedidos():
    c = CLIENTES
    # ── Pedidos sembrados (matriz) ──
    # A2: Valentina compró el 7, recibió el 11 y pidió devolverlo el 15; se lo negaron con el destacado.
    pedido(dt.date(2026, 9, 7), 12, c["valentina"], [_item("VES-002", "verde", "S")], clave="retracto",
           medio="Webpay crédito", fecha_despacho=dt.date(2026, 9, 9), fecha_entrega=dt.date(2026, 9, 11))
    # A1a: compró el 1, recibió el 4; el 22 pide cambio (18 días) y Cata le dice 15.
    pedido(dt.date(2026, 9, 1), 20, c["florencia"], [_item("PAN-001", "negro", "40")], clave="cambio18",
           fecha_despacho=dt.date(2026, 9, 2), fecha_entrega=dt.date(2026, 9, 4))
    # A3: le prometieron despacho gratis desde 39.990 y le cobraron.
    nuevo_cliente("barbara", "Bárbara Saavedra", "La Florida")
    pedido(dt.date(2026, 9, 16), 15, c["barbara"], [_item("PLR-002", "crudo", "M"), _item("POL-001", "negro", "M")],
           clave="gratis39", nota_interna="Clienta reclama: Cata le dijo despacho gratis desde $39.990")
    # B1: los seis polerones burdeo vendidos sin stock el fin de semana largo.
    burdeo = []
    for i, (t, d, h) in enumerate([("S", 19, 11), ("M", 19, 16), ("M", 19, 22), ("L", 20, 10), ("S", 20, 13), ("M", 20, 21)]):
        cl = nuevo_cliente(f"burdeo{i + 1}")
        burdeo.append(pedido(dt.date(2026, 9, d), h, cl, [_item("PLR-001", "burdeo", t)], clave=f"burdeo{i + 1}",
                             medio=RNG.choice(["Webpay crédito", "Webpay débito"]),
                             estado="pagado", fecha_despacho=None, fecha_entrega=None,
                             nota_interna="SIN STOCK: se vendió todo en la feria del sábado. Avisar a la clienta."))
    burdeo[0].update(estado="despachado", items=[_item("PLR-001", "gris", "S")], fecha_despacho=dt.date(2026, 9, 23),
                     seguimiento="", nota_interna="Sin stock burdeo: aceptó cambio a gris por WhatsApp")
    burdeo[1].update(estado="reembolsado", nota_interna="Sin stock burdeo: pidió reembolso por WhatsApp (25-sep)")
    # B2: la parka apartada por chat que después se vende por la web.
    nuevo_cliente("reserva", "Paulina Castillo", "Ñuñoa", "Pauli Castillo")
    nuevo_cliente("parka_web", "Gabriel Tapia", "Rancagua")
    pedido(dt.date(2026, 9, 23), 10, c["parka_web"], [_item("CHA-002", "negro", "M")], clave="parka_web")
    # B3: atrasado (Temuco), courier perdido después de los feriados.
    pedido(dt.date(2026, 9, 15), 9, c["fernanda"], [_item("PLR-001", "gris", "S"), _item("ACC-001", "mostaza", "Única")],
           clave="atrasado", medio="Webpay débito", fecha_despacho=dt.date(2026, 9, 16), fecha_entrega=None,
           estado="despachado", nota_interna="Courier: retraso en centro de distribución de Temuco")
    # B4: el courier dice entregado y la clienta no lo recibió.
    pedido(dt.date(2026, 9, 14), 19, c["javiera"], [_item("CAM-001", "celeste", "M")], clave="no_recibido",
           fecha_despacho=dt.date(2026, 9, 16), fecha_entrega=dt.date(2026, 9, 21),
           nota_interna="Clienta dice que no le llegó (22-sep). Pendiente reclamo al courier")
    # B5: cambio de dirección con el pedido ya despachado.
    pedido(dt.date(2026, 9, 24), 8, c["sebastian"], [_item("CHA-004", "gris", "M")], clave="cambio_dir",
           fecha_despacho=dt.date(2026, 9, 25), fecha_entrega=None, estado="despachado")
    # B6: pago rechazado que el banco igual descontó, y transferencia sin confirmar.
    pedido(dt.date(2026, 9, 23), 22, c["ignacio"], [_item("CHA-003", "amarillo", "XL")], clave="rechazado",
           medio="Webpay crédito", estado="pago rechazado", fecha_despacho=None, fecha_entrega=None)
    pedido(dt.date(2026, 9, 24), 13, c["matias"], [_item("CHA-002", "azul marino", "L")], clave="transferencia",
           medio="Transferencia", estado="pago pendiente", fecha_despacho=None, fecha_entrega=None)
    # B8: preventa de la parka verde oliva.
    for i, t in enumerate(["M", "S"]):
        cl = nuevo_cliente(f"preventa{i + 1}")
        pedido(dt.date(2026, 9, 10 + i * 12), 18, cl, [_item("CHA-002", "verde oliva", t)], clave=f"preventa{i + 1}",
               estado="preventa", fecha_despacho=None, fecha_entrega=None,
               nota_interna=f"Preventa: llega el {fecha_corta(PREVENTA_LLEGA)}")
    # D1: el pedido de Antonia por el que pregunta su pololo.
    pedido(dt.date(2026, 9, 22), 21, c["antonia"], [_item("POL-002", "rojo con blanco", "S"), _item("PAN-005", "beige", "S")],
           clave="antonia", fecha_despacho=dt.date(2026, 9, 23), fecha_entrega=dt.date(2026, 9, 28))
    # Los pedidos originales de Diego y Camila (pruebas del agente)
    pedido(dt.date(2026, 9, 21), 18, c["diego"], [_item("PAN-001", "azul oscuro", "42")], clave="diego",
           fecha_despacho=dt.date(2026, 9, 23), fecha_entrega=None, estado="despachado")
    pedido(dt.date(2026, 9, 3), 11, c["camila"], [_item("POL-001", "negro", "M", 2)], clave="camila")
    pedido(dt.date(2026, 9, 11), 17, c["isidora"], [_item("VES-001", "arena", "S"), _item("ACC-004", "crudo", "Única")],
           clave="isidora", medio="Webpay crédito")
    pedido(dt.date(2026, 9, 26), 20, c["constanza"], [_item("CHA-001", "negro", "S")], clave="constanza",
           codigo="BIENVENIDA10")
    # Cancelados por la clienta antes del despacho
    for d in (8, 24):
        cl = nuevo_cliente()
        pedido(dt.date(2026, 9, d), RNG.randint(9, 22), cl, _items_al_azar(1), estado="cancelado",
               fecha_despacho=None, fecha_entrega=None, nota_interna="Cancelado a pedido de la clienta")

    # ── Pedidos de relleno, con el ritmo real de la tienda ──
    d = dt.date(2026, 9, 1)
    while d < HOY:
        n = RNG.choice([3, 3, 4, 4, 5]) if d.weekday() < 5 else RNG.choice([2, 3, 3, 4])
        if d in (dt.date(2026, 9, 19), dt.date(2026, 9, 20)):
            n += 2   # promo de Fiestas Patrias en Instagram
        for _ in range(n):
            cl = nuevo_cliente() if RNG.random() < 0.9 else RNG.choice([CLIENTES[k] for k in ("camila", "isidora", "florencia", "tomas")])
            cod = "BIENVENIDA10" if RNG.random() < 0.12 else None
            pedido(d, RNG.choice([8, 9, 10, 11, 12, 13, 15, 17, 19, 20, 21, 22, 23]), cl, _items_al_azar(), codigo=cod)
        d += dt.timedelta(days=1)

    PEDIDOS.sort(key=lambda p: (p["fecha"], p["hora"], p["cliente"]))
    for i, p in enumerate(PEDIDOS):
        p["numero"] = f"KT-{1001 + i}"
        p["estado"] = _estado(p)
        if p["estado"] in ("despachado", "entregado", "en cambio") and not p["seguimiento"]:
            p["courier"] = COURIER
            p["seguimiento"] = f"CA-{RNG.randint(700000, 799999)}"
        if p["estado"] not in ("despachado", "entregado"):
            p["fecha_despacho"] = None
        if p["estado"] != "entregado":
            p["fecha_entrega"] = None


_construir_pedidos()

# Pedido de julio (garantía, B7): no está en el export de septiembre.
PEDIDO_JULIO = {"numero": "KT-0874", "cliente": "Tomás Contreras", "fecha": dt.date(2026, 7, 22),
                "items": [_item("PLR-003", "negro", "L")], "estado": "entregado", "fecha_entrega": dt.date(2026, 7, 28)}
# Venta asistida por chat (C4): Rocío la anotó en un cuaderno, no existe en la web.
VENTA_ASISTIDA = {"cliente": "Gladys Henríquez", "fecha": dt.date(2026, 9, 17),
                  "items": [_item("CHA-004", "crudo", "L"), _item("ACC-002", "gris", "Única")], "medio": "Transferencia"}

# ─────────────────────────── Stock en cuatro capas ───────────────────────────
STOCK_REAL = dict(STOCK_BASE)                     # conteo físico de Nicolás del 29-sep
for t in PROD["PLR-001"]["tallas"]:
    STOCK_REAL[("PLR-001", "burdeo", t)] = 0
for t in PROD["CHA-002"]["tallas"]:
    STOCK_REAL[("CHA-002", "verde oliva", t)] = 0

# Lo vendido en la feria del 19-sep cuya hoja se perdió (no se descontó). Burdeo aparte: ver abajo.
FERIA_PERDIDA = {}
for v in RNG.sample([v for v in TODAS if v[0] in ("PLR-002", "PLR-003", "ACC-001", "ACC-002", "CHA-004", "POL-001", "POL-003")
                     and STOCK_BASE[v] > 0], 12):
    FERIA_PERDIDA[v] = RNG.randint(1, 2)
FERIA_BURDEO = {("PLR-001", "burdeo", "S"): 2, ("PLR-001", "burdeo", "M"): 3, ("PLR-001", "burdeo", "L"): 1}

# Ventas por mensaje de Instagram entre el 22 y el 28, que Rocío avisa tarde en el grupo.
VENTAS_IG = {("ACC-001", "mostaza", "Única"): 2, ("POL-003", "arena", "M"): 1, ("VES-003", "camel", "S"): 1}

VENTAS_WEB_POST = {}   # ventas de la web después de la actualización del lunes 21
for p in PEDIDOS:
    if p["fecha"] > PLANILLA_ACTUALIZADA and p["estado"] not in ("cancelado", "pago rechazado", "preventa", "reembolsado"):
        for i in p["items"]:
            k = (i["sku"], i["color"], i["talla"])
            VENTAS_WEB_POST[k] = VENTAS_WEB_POST.get(k, 0) + i["cantidad"]

# Nunca puede haber más ventas que unidades: el conteo real sube lo necesario (el sobrante es el stock del 21).
STOCK_PLANILLA = {}
STOCK_WEB = {}
OCULTOS = {("CAM-003", "floral terracota", t) for t in PROD["CAM-003"]["tallas"]}   # Nicolás los puso en 0: falla de lote
for v in TODAS:
    real = STOCK_REAL[v]
    vendidos = VENTAS_WEB_POST.get(v, 0) + VENTAS_IG.get(v, 0)
    STOCK_PLANILLA[v] = real + vendidos + FERIA_PERDIDA.get(v, 0)
    STOCK_WEB[v] = STOCK_PLANILLA[v] - VENTAS_WEB_POST.get(v, 0)
for v in FERIA_BURDEO:
    STOCK_PLANILLA[v] = 0      # Nicolás descontó las 6 ventas de la web, pero no las 6 de la feria
    STOCK_WEB[v] = 0
for v in OCULTOS:
    STOCK_WEB[v] = 0
PREVENTA_WEB = {("CHA-002", "verde oliva", t): 10 for t in PROD["CHA-002"]["tallas"]}

if __name__ == "__main__":
    from collections import Counter
    print("pedidos:", len(PEDIDOS), Counter(p["estado"] for p in PEDIDOS))
    print("clientes:", len(CLIENTES))
    print("claves:", {k: v["numero"] for k, v in CLAVE_PEDIDO.items()})
    dif_pw = sum(1 for v in TODAS if STOCK_PLANILLA[v] != STOCK_WEB[v])
    dif_rw = sum(1 for v in TODAS if STOCK_REAL[v] != STOCK_WEB[v])
    print("variantes:", len(TODAS), "| planilla≠web:", dif_pw, "| real≠web:", dif_rw,
          "| web>real (riesgo de sobreventa):", sum(1 for v in TODAS if STOCK_WEB[v] > STOCK_REAL[v]))
    tarde = [p for p in PEDIDOS if p["estado"] == "entregado" and p["fecha_entrega"] > p["fecha_estimada"]]
    ent = [p for p in PEDIDOS if p["estado"] == "entregado"]
    print("entregados:", len(ent), "| después de la fecha estimada:", len(tarde))
