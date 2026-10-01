"""Base de datos de la tienda (SQLite). Se crea desde generador/caso.py: la foto del martes 29 de septiembre.

Nada se carga a mano: catálogo, stock de la web, pedidos y clientes salen del mismo origen que los insumos del
curso, así que el panel exporta exactamente lo que dicen `insumos/export-*.csv` mientras nadie compre.
"""
import datetime as dt
import json
import os
import sqlite3
import sys
from contextlib import contextmanager

AQUI = os.path.dirname(os.path.abspath(__file__))
TIENDA = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(os.path.dirname(TIENDA), "generador"))

import caso  # noqa: E402
import exportes  # noqa: E402

RUTA_DB = os.environ.get("KILTRA_DB", os.path.join(TIENDA, "kiltra.db"))

ESQUEMA = """
CREATE TABLE productos (sku TEXT PRIMARY KEY, nombre TEXT, categoria TEXT, precio INTEGER, descripcion TEXT, orden INTEGER);
CREATE TABLE variantes (sku TEXT, color TEXT, talla TEXT, stock INTEGER, estado TEXT, orden INTEGER,
                        PRIMARY KEY (sku, color, talla));
CREATE TABLE pedidos (numero TEXT PRIMARY KEY, fecha TEXT, hora TEXT, cliente TEXT, email TEXT, telefono TEXT,
                      direccion TEXT, comuna TEXT, zona TEXT, subtotal INTEGER, codigo TEXT, descuento INTEGER,
                      despacho INTEGER, total INTEGER, medio_pago TEXT, estado TEXT, courier TEXT, seguimiento TEXT,
                      fecha_despacho TEXT, fecha_estimada TEXT, fecha_entrega TEXT, nota_interna TEXT, origen TEXT);
CREATE TABLE items (numero TEXT, linea INTEGER, sku TEXT, producto TEXT, color TEXT, talla TEXT, cantidad INTEGER,
                    precio_unitario INTEGER, PRIMARY KEY (numero, linea));
CREATE TABLE meta (clave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE config (clave TEXT PRIMARY KEY, valor TEXT);
"""


def config_inicial():
    """La configuración de la tienda en la plataforma el 29-sep: la versión «web» de las políticas del caso."""
    import documentos
    F = caso.POLITICAS
    texto_plazo = {"RM": F["plazo_prometido"]["RM"], "Regiones": F["plazo_prometido"]["Regiones"],
                   "Extremo": F["plazo_prometido"]["Regiones"]}
    return {
        "tienda": {"nombre": "Kiltra", "lema": "ropa sin pedigrí, con mucha calle", "email": "hola@kiltra.example",
                   "instagram": "@kiltra.cl", "horario": F["horario"]["web"], "showroom": F["showroom"]["web"]},
        "envios": {"courier": caso.COURIER, "gratis_desde": F["despacho_gratis"]["web"],
                   "zonas": {z: {"costo": F["costo_despacho"][z], "dias_habiles": F["plazo_prometido_dias"][z],
                                 "texto": texto_plazo[z]} for z in ("RM", "Regiones", "Extremo")},
                   "comunas": dict(sorted(caso.COMUNAS.items()))},
        "descuentos": [
            {"codigo": "BIENVENIDA10", "porcentaje": 10, "solo_primera_compra": True, "vence": None, "activo": True},
            {"codigo": "CAMI15", "porcentaje": 15, "solo_primera_compra": False, "vence": "2026-08-31", "activo": True},
        ],
        "paginas": {"preguntas-frecuentes": {"titulo": "Preguntas frecuentes",
                                             "texto": documentos.preguntas_frecuentes().strip()}},
    }


def _conectar():
    con = sqlite3.connect(RUTA_DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


@contextmanager
def conexion():
    con = _conectar()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def crear_base(forzar=False):
    """Crea la base desde caso.py si no existe (o si se fuerza). Devuelve True si la creó."""
    if os.path.exists(RUTA_DB) and not forzar:
        return False
    if os.path.exists(RUTA_DB):
        os.remove(RUTA_DB)
    with conexion() as con:
        con.executescript(ESQUEMA)
        orden_sku = {p[0]: i for i, p in enumerate(caso.PRODUCTOS)}
        for sku, nombre, cat, precio, colores, tallas in caso.PRODUCTOS:
            con.execute("INSERT INTO productos VALUES (?,?,?,?,?,?)",
                        (sku, nombre, cat, precio, caso.DESCRIPCIONES_WEB.get(sku, ""), orden_sku[sku]))
        for i, v in enumerate(exportes.variantes_web()):
            con.execute("INSERT INTO variantes VALUES (?,?,?,?,?,?)",
                        (v["sku"], v["color"], v["talla"], v["stock"], v["estado_publicacion"], i))
        iso = lambda d: d.isoformat() if d else ""
        for p in exportes.pedidos_web():
            con.execute("INSERT INTO pedidos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (p["numero"], iso(p["fecha"]), p["hora"], p["cliente"], p["email"], p["telefono"], "",
                         p["comuna"], p["zona"], p["subtotal"], p["codigo"], p["descuento"], p["despacho"], p["total"],
                         p["medio_pago"], p["estado"], p["courier"], p["seguimiento"], iso(p["fecha_despacho"]),
                         iso(p["fecha_estimada"]), iso(p["fecha_entrega"]), p["nota_interna"], "caso"))
            for j, it in enumerate(p["items"]):
                con.execute("INSERT INTO items VALUES (?,?,?,?,?,?,?,?)",
                            (p["numero"], j, it["sku"], it["producto"], it["color"], it["talla"], it["cantidad"],
                             it["precio_unitario"]))
        con.execute("INSERT INTO meta VALUES ('creada', ?)", (dt.datetime.now().isoformat(timespec="seconds"),))
        for clave, valor in config_inicial().items():
            con.execute("INSERT INTO config VALUES (?, ?)", (clave, json.dumps(valor, ensure_ascii=False)))
    return True


# ─────────────────────────── Configuración de la tienda (editable en el panel) ───────────────────────────
def config(clave):
    with conexion() as con:
        f = con.execute("SELECT valor FROM config WHERE clave=?", (clave,)).fetchone()
        return json.loads(f["valor"]) if f else None


def guardar_config(clave, valor):
    with conexion() as con:
        con.execute("INSERT OR REPLACE INTO config VALUES (?, ?)", (clave, json.dumps(valor, ensure_ascii=False)))


def meta(clave, valor=None):
    with conexion() as con:
        if valor is not None:
            con.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (clave, valor))
            return valor
        f = con.execute("SELECT valor FROM meta WHERE clave=?", (clave,)).fetchone()
        return f["valor"] if f else None


def verificar_siembra():
    """Chequeos de que la configuración recién sembrada calza con los insumos del caso."""
    import documentos
    F = caso.POLITICAS
    env, pag = config("envios"), config("paginas")
    return [
        ("Las preguntas frecuentes de la plataforma son el texto de insumos/preguntas-frecuentes-web.txt",
         pag["preguntas-frecuentes"]["texto"] == documentos.preguntas_frecuentes().strip()),
        ("Despacho gratis desde el umbral de la web", env["gratis_desde"] == F["despacho_gratis"]["web"]),
        ("Costos de despacho por zona", all(env["zonas"][z]["costo"] == F["costo_despacho"][z] for z in env["zonas"])),
        ("Plazo prometido por zona", all(env["zonas"][z]["dias_habiles"] == F["plazo_prometido_dias"][z] for z in env["zonas"])),
        ("Las comunas del checkout son las del caso", env["comunas"] == caso.COMUNAS),
    ]


# ─────────────────────────── Clientes (la plataforma los arma desde los pedidos) ───────────────────────────
def clientes(texto=None, limite=500):
    q = ("SELECT lower(email) email, MAX(cliente) nombre, MAX(telefono) telefono, MAX(comuna) comuna, COUNT(*) pedidos, "
         "SUM(CASE WHEN estado NOT IN ('cancelado','pago rechazado','reembolsado') THEN total ELSE 0 END) total, "
         "MAX(fecha) ultima FROM pedidos")
    args = []
    if texto:
        q += " WHERE cliente LIKE ? OR email LIKE ? OR telefono LIKE ?"
        args = [f"%{texto}%"] * 3
    q += " GROUP BY lower(email) ORDER BY ultima DESC LIMIT ?"
    with conexion() as con:
        return [dict(f) for f in con.execute(q, args + [limite])]


def resumen():
    with conexion() as con:
        f = con.execute("SELECT COUNT(*) n, SUM(total) t FROM pedidos WHERE estado NOT IN ('cancelado','pago rechazado','reembolsado')").fetchone()
        pend = con.execute("SELECT COUNT(*) FROM pedidos WHERE estado IN ('pagado','en preparación','pago pendiente')").fetchone()[0]
        sin = con.execute("SELECT COUNT(*) FROM variantes WHERE stock=0 AND estado='publicado'").fetchone()[0]
        bajo = con.execute("SELECT COUNT(*) FROM variantes WHERE stock BETWEEN 1 AND 2 AND estado='publicado'").fetchone()[0]
        return {"pedidos": f["n"], "ventas": f["t"] or 0, "por_despachar": pend, "variantes_agotadas": sin, "variantes_bajo": bajo}


# ─────────────────────────── Catálogo ───────────────────────────
CATEGORIAS = [("poleras", "Poleras"), ("polerones", "Polerones"), ("camisas", "Camisas"), ("pantalones", "Pantalones"),
              ("vestidos y faldas", "Vestidos y faldas"), ("chaquetas", "Chaquetas"), ("accesorios", "Accesorios")]
SLUG = {c: c.replace(" ", "-") for c, _ in CATEGORIAS}
DESDE_SLUG = {v: k for k, v in SLUG.items()}
NOMBRE_CAT = dict(CATEGORIAS)


def _producto(con, fila):
    vs = [dict(v) for v in con.execute("SELECT * FROM variantes WHERE sku=? AND estado!='oculto' ORDER BY orden", (fila["sku"],))]
    colores, tallas = [], []
    for v in vs:
        if v["color"] not in colores:
            colores.append(v["color"])
        if v["talla"] not in tallas:
            tallas.append(v["talla"])
    stock_total = sum(v["stock"] for v in vs)
    preventa = next((v["estado"] for v in vs if v["estado"].startswith("preventa")), None)
    return {**dict(fila), "variantes": vs, "colores": colores, "tallas": tallas, "stock_total": stock_total,
            "agotado": stock_total == 0, "preventa": preventa, "slug_cat": SLUG[fila["categoria"]]}


def productos(categoria=None, orden="relevancia"):
    q = "SELECT * FROM productos" + (" WHERE categoria=?" if categoria else "")
    q += {"precio_asc": " ORDER BY precio, orden", "precio_desc": " ORDER BY precio DESC, orden"}.get(orden, " ORDER BY orden")
    with conexion() as con:
        return [_producto(con, f) for f in con.execute(q, (categoria,) if categoria else ())]


def producto(sku):
    with conexion() as con:
        f = con.execute("SELECT * FROM productos WHERE sku=?", (sku.upper(),)).fetchone()
        return _producto(con, f) if f else None


def mas_pedidos(n=8):
    with conexion() as con:
        skus = [r["sku"] for r in con.execute(
            "SELECT i.sku, SUM(i.cantidad) u FROM items i JOIN pedidos p ON p.numero=i.numero "
            "WHERE p.estado NOT IN ('cancelado','pago rechazado') GROUP BY i.sku ORDER BY u DESC, i.sku LIMIT ?", (n,))]
        return [_producto(con, con.execute("SELECT * FROM productos WHERE sku=?", (s,)).fetchone()) for s in skus]


def _norm(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "").lower()) if unicodedata.category(c) != "Mn").strip()


def buscar(texto="", categoria="", talla="", color="", precio_max=None, sku=""):
    """La misma lógica que la función buscar_productos de Kapso, ahora sobre la base de la tienda."""
    texto, categoria, talla, color = _norm(texto), _norm(categoria), _norm(talla), _norm(color)
    res = []
    for p in productos():
        if sku and _norm(p["sku"]) != _norm(sku):
            continue
        if categoria and categoria not in _norm(p["categoria"]):
            continue
        if precio_max and p["precio"] > precio_max:
            continue
        if texto and not all(w in _norm(p["nombre"] + " " + p["categoria"]) for w in texto.split()):
            continue
        vs = [v for v in p["variantes"] if (not color or color in _norm(v["color"])) and (not talla or _norm(v["talla"]) == talla)]
        if (color or talla) and not vs:
            continue
        p["coinciden"] = vs
        res.append(p)
    return res


# ─────────────────────────── Pedidos ───────────────────────────
def pedido(numero):
    with conexion() as con:
        n = numero.strip().upper()
        if not n.startswith("KT-"):
            n = "KT-" + "".join(ch for ch in n if ch.isdigit())
        f = con.execute("SELECT * FROM pedidos WHERE numero=?", (n,)).fetchone()
        if not f:
            return None
        p = dict(f)
        p["items"] = [dict(i) for i in con.execute("SELECT * FROM items WHERE numero=? ORDER BY linea", (n,))]
        return p


def pedidos(estado=None, texto=None, limite=200):
    q, args = "SELECT * FROM pedidos WHERE 1=1", []
    if estado:
        q += " AND estado=?"
        args.append(estado)
    if texto:
        q += " AND (numero LIKE ? OR cliente LIKE ? OR email LIKE ?)"
        args += [f"%{texto}%"] * 3
    q += " ORDER BY fecha DESC, hora DESC LIMIT ?"
    args.append(limite)
    with conexion() as con:
        filas = [dict(f) for f in con.execute(q, args)]
        for p in filas:
            p["items"] = [dict(i) for i in con.execute("SELECT * FROM items WHERE numero=? ORDER BY linea", (p["numero"],))]
        return filas


def estados_pedidos():
    with conexion() as con:
        return [(r["estado"], r["n"]) for r in con.execute("SELECT estado, COUNT(*) n FROM pedidos GROUP BY estado ORDER BY n DESC")]


def pedidos_de_email(email):
    with conexion() as con:
        return con.execute("SELECT COUNT(*) FROM pedidos WHERE lower(email)=lower(?) AND estado NOT IN ('cancelado','pago rechazado')",
                           (email.strip(),)).fetchone()[0]


def siguiente_numero(con):
    ult = con.execute("SELECT MAX(CAST(substr(numero, 4) AS INTEGER)) FROM pedidos").fetchone()[0] or 1000
    return f"KT-{ult + 1}"


class SinStock(Exception):
    pass


def crear_pedido(datos, lineas):
    """lineas: [{sku, producto, color, talla, cantidad, precio_unitario}]. Descuenta el stock de la web."""
    with conexion() as con:
        con.execute("BEGIN IMMEDIATE")
        for l in lineas:
            r = con.execute("SELECT stock FROM variantes WHERE sku=? AND color=? AND talla=?", (l["sku"], l["color"], l["talla"])).fetchone()
            if not r or r["stock"] < l["cantidad"]:
                raise SinStock(f"{l['producto']} {l['color']} {l['talla']}: quedan {r['stock'] if r else 0}")
        numero = siguiente_numero(con)
        for l in lineas:
            con.execute("UPDATE variantes SET stock=stock-? WHERE sku=? AND color=? AND talla=?",
                        (l["cantidad"], l["sku"], l["color"], l["talla"]))
        d = {**datos, "numero": numero}
        cols = ["numero", "fecha", "hora", "cliente", "email", "telefono", "direccion", "comuna", "zona", "subtotal", "codigo",
                "descuento", "despacho", "total", "medio_pago", "estado", "courier", "seguimiento", "fecha_despacho",
                "fecha_estimada", "fecha_entrega", "nota_interna", "origen"]
        con.execute(f"INSERT INTO pedidos ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [d.get(c, "") for c in cols])
        for j, l in enumerate(lineas):
            con.execute("INSERT INTO items VALUES (?,?,?,?,?,?,?,?)",
                        (numero, j, l["sku"], l["producto"], l["color"], l["talla"], l["cantidad"], l["precio_unitario"]))
        return numero


def cambiar_estado(numero, estado):
    with conexion() as con:
        con.execute("UPDATE pedidos SET estado=? WHERE numero=?", (estado, numero))


def guardar_stock(cambios):
    """cambios: {(sku, color, talla): stock}"""
    with conexion() as con:
        for (sku, c, t), s in cambios.items():
            con.execute("UPDATE variantes SET stock=? WHERE sku=? AND color=? AND talla=?", (max(0, int(s)), sku, c, t))


# ─────────────────────────── Exportaciones (mismo formato que los insumos) ───────────────────────────
def exportar_productos():
    with conexion() as con:
        filas = con.execute("SELECT v.*, p.nombre, p.categoria, p.precio, p.descripcion FROM variantes v "
                            "JOIN productos p ON p.sku=v.sku ORDER BY v.orden").fetchall()
        return exportes.csv_productos({"sku": f["sku"], "producto": f["nombre"], "categoria": f["categoria"], "precio": f["precio"],
                                       "color": f["color"], "talla": f["talla"], "stock": f["stock"],
                                       "estado_publicacion": f["estado"], "descripcion": f["descripcion"]} for f in filas)


def exportar_pedidos():
    with conexion() as con:
        ps = []
        for f in con.execute("SELECT * FROM pedidos ORDER BY CAST(substr(numero, 4) AS INTEGER)"):
            p = dict(f)
            p["items"] = [dict(i) for i in con.execute("SELECT * FROM items WHERE numero=? ORDER BY linea", (p["numero"],))]
            ps.append(p)
        return exportes.csv_pedidos(ps)
