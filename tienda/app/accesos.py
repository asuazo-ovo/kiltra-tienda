"""Las dos formas de conectar una aplicación a una tienda en Mostrador, calcadas del mercado:

1. «Apps de desarrollador», como en Shopify (informe del 1-oct-2026):
   crear la app → elegir alcances → instalarla aprobando una pantalla de consentimiento → la tienda entrega un
   ID de cliente y un secreto (rotable) → la app pide un token por API (client credentials) que dura 24 horas →
   cada llamada va con `X-Mostrador-Access-Token` y la API rechaza lo que el alcance no cubre (403).
2. «Credenciales de la cuenta», como en Jumpseller: Login Key + Auth Token copiados del panel, en
   `X-Login-Key` / `X-Auth-Token`. Acceso total, sin alcances.

Render borra la base en cada reinicio: por eso la app «Agente WhatsApp» viene preinstalada con credenciales que
se derivan de variables de entorno (estables), y los tokens son firmados (no se guardan): sobreviven al reinicio.
"""
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import time

from . import datos
from .plataforma import TIENDA_CODIGO

SEMILLA = (os.environ.get("KILTRA_SECRETO") or "secreto-local-de-desarrollo").encode()
DURACION_TOKEN = 86399   # como Shopify: 24 horas menos un segundo

# (recurso, nombre visible, qué ve la dueña en el consentimiento al leer, al escribir)
RECURSOS = [
    ("productos", "Productos", "Ver productos: nombres, precios, fotos y descripciones", "Crear y modificar productos"),
    ("inventario", "Inventario", "Ver el stock de cada talla y color", "Cambiar el stock"),
    ("pedidos", "Pedidos", "Ver pedidos, incluidos los datos del cliente de cada pedido: nombre, correo, teléfono y dirección",
     "Modificar pedidos: estado, cancelación y reembolso"),
    ("clientes", "Clientes", "Ver datos de clientes: nombre, correo, teléfono, comuna y compras", "Crear y modificar clientes"),
    ("descuentos", "Descuentos", "Ver los códigos de descuento", "Crear y modificar descuentos"),
    ("envios", "Envíos", "Ver zonas, tarifas y plazos de envío", "Modificar zonas, tarifas y plazos"),
    ("politicas", "Políticas", "Ver las políticas de cambios y devoluciones", "Modificar las políticas"),
    ("paginas", "Páginas", "Ver las páginas de la tienda (preguntas frecuentes)", "Modificar las páginas"),
]
ALCANCES = [f"{a}_{r}" for r, *_ in RECURSOS for a in ("leer", "escribir")]
ALCANCES_AGENTE = ["leer_productos", "leer_inventario", "leer_pedidos", "leer_clientes", "leer_descuentos", "leer_envios",
                   "leer_politicas", "leer_paginas"]


def _deriva(etiqueta, n):
    return hashlib.sha256(SEMILLA + etiqueta.encode()).hexdigest()[:n]


def app_sembrada():
    """La app del agente de WhatsApp, preinstalada. Sus credenciales no cambian entre reinicios."""
    return {"client_id": os.environ.get("KILTRA_CLIENT_ID") or f"mo_{_deriva('client_id', 24)}",
            "secreto": os.environ.get("KILTRA_CLIENT_SECRET") or f"mos_{_deriva('client_secret', 32)}",
            "nombre": "Agente WhatsApp", "alcances": ALCANCES_AGENTE}


# ─────────────────────────── Apps de desarrollador ───────────────────────────
def _fila(f):
    if not f:
        return None
    a = dict(f)
    a["alcances"] = json.loads(a["alcances"])
    a["alcances_instalados"] = json.loads(a["alcances_instalados"]) if a["alcances_instalados"] else []
    return a


def apps():
    with datos.conexion() as con:
        return [_fila(f) for f in con.execute("SELECT * FROM apps ORDER BY creada")]


def app(client_id):
    with datos.conexion() as con:
        return _fila(con.execute("SELECT * FROM apps WHERE client_id=?", (client_id,)).fetchone())


def crear_app(nombre, alcances):
    a = {"client_id": f"mo_{secrets.token_hex(12)}", "secreto": f"mos_{secrets.token_hex(16)}"}
    alc = [x for x in ALCANCES if x in alcances]
    with datos.conexion() as con:
        con.execute("INSERT INTO apps VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (a["client_id"], nombre.strip() or "App sin nombre", a["secreto"], None, json.dumps(alc), 1, None, "", "",
                     dt.datetime.now().isoformat(timespec="minutes")))
    return a["client_id"]


def sembrar():
    """Crea la tabla de apps y la app del agente, preinstalada, si no existen."""
    with datos.conexion() as con:
        con.execute("CREATE TABLE IF NOT EXISTS apps (client_id TEXT PRIMARY KEY, nombre TEXT, secreto TEXT, secreto_anterior TEXT, "
                    "alcances TEXT, version INTEGER, alcances_instalados TEXT, version_instalada TEXT, instalada TEXT, creada TEXT)")
    s = app_sembrada()
    if not app(s["client_id"]):
        with datos.conexion() as con:
            ahora = dt.datetime.now().isoformat(timespec="minutes")
            con.execute("INSERT INTO apps VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (s["client_id"], s["nombre"], s["secreto"], None, json.dumps(s["alcances"]), 1, json.dumps(s["alcances"]),
                         "1", ahora, ahora))


def lanzar_version(client_id, alcances):
    """Los alcances quedan fijos en una versión: cambiarlos crea una versión nueva, que hay que volver a aprobar."""
    alc = [x for x in ALCANCES if x in alcances]
    with datos.conexion() as con:
        con.execute("UPDATE apps SET alcances=?, version=version+1 WHERE client_id=?", (json.dumps(alc), client_id))


def instalar(client_id):
    a = app(client_id)
    with datos.conexion() as con:
        con.execute("UPDATE apps SET alcances_instalados=?, version_instalada=?, instalada=? WHERE client_id=?",
                    (json.dumps(a["alcances"]), str(a["version"]), dt.datetime.now().isoformat(timespec="minutes"), client_id))


def desinstalar(client_id):
    with datos.conexion() as con:
        con.execute("UPDATE apps SET alcances_instalados=NULL, version_instalada='', instalada='' WHERE client_id=?", (client_id,))


def rotar_secreto(client_id):
    """El secreto nuevo reemplaza al anterior para pedir tokens. Los tokens ya entregados siguen hasta que vencen."""
    nuevo = f"mos_{secrets.token_hex(16)}"
    with datos.conexion() as con:
        con.execute("UPDATE apps SET secreto_anterior=secreto, secreto=? WHERE client_id=?", (nuevo, client_id))
    return nuevo


def eliminar_app(client_id):
    with datos.conexion() as con:
        con.execute("DELETE FROM apps WHERE client_id=?", (client_id,))


# ─────────────────────────── Tokens (firmados, sin guardar) ───────────────────────────
def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _deb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def emitir_token(client_id, client_secret):
    """Client credentials. Devuelve (respuesta, error)."""
    a = app(client_id)
    if not a or not hmac.compare_digest(client_secret or "", a["secreto"]):
        return None, "client_id o client_secret inválidos."
    if not a["instalada"]:
        return None, "La app no está instalada en la tienda. Instálala desde el portal de desarrolladores."
    exp = int(time.time()) + DURACION_TOKEN
    carga = _b64(json.dumps({"app": client_id, "v": a["version_instalada"], "exp": exp}, separators=(",", ":")).encode())
    firma = _b64(hmac.new(SEMILLA, carga.encode(), hashlib.sha256).digest())
    return {"access_token": f"mot_{carga}.{firma}", "scope": ",".join(a["alcances_instalados"]), "expires_in": DURACION_TOKEN}, None


def verificar_token(token):
    """Devuelve (app, error). Falla si la firma no calza, venció, o la app ya no está instalada."""
    try:
        cuerpo = token.removeprefix("mot_")
        carga, firma = cuerpo.split(".")
        esperada = _b64(hmac.new(SEMILLA, carga.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(firma, esperada):
            return None, "Token inválido."
        d = json.loads(_deb64(carga))
    except (ValueError, json.JSONDecodeError):
        return None, "Token inválido."
    if d["exp"] < time.time():
        return None, "El token venció. Pide uno nuevo en /api/oauth/access_token."
    a = app(d["app"])
    if not a or not a["instalada"] or a["version_instalada"] != d["v"]:
        return None, "La app ya no está instalada en la tienda."
    return a, None


# ─────────────────────────── Credenciales de la cuenta (tipo Jumpseller) ───────────────────────────
def credenciales_cuenta():
    login = datos.meta("api_login") or datos.meta("api_login", os.environ.get("KILTRA_API_LOGIN") or f"{TIENDA_CODIGO}-{_deriva('login', 10)}")
    token = datos.meta("api_token") or datos.meta("api_token", os.environ.get("KILTRA_API_KEY") or secrets.token_hex(16))
    return login, token


def regenerar_token_cuenta():
    return datos.meta("api_token", secrets.token_hex(16))


def consentimiento(alcances):
    """Los permisos traducidos a frases, como la pantalla de instalación de Shopify."""
    ver, cambiar = [], []
    for r, nombre, lee, escribe in RECURSOS:
        if f"leer_{r}" in alcances or f"escribir_{r}" in alcances:
            ver.append(lee)
        if f"escribir_{r}" in alcances:
            cambiar.append(escribe)
    return ver, cambiar
