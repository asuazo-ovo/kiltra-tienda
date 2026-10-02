"""API de administrador de Mostrador, con las dos formas de entrar que usa el mercado (ver accesos.py):

- App de desarrollador (como Shopify): token de 24 h en `X-Mostrador-Access-Token`, que se pide en
  `POST /api/oauth/access_token`. Solo deja hacer lo que cubren sus alcances; lo demás responde 403.
- Credenciales de la cuenta (como Jumpseller): `X-Login-Key` + `X-Auth-Token`. Acceso total.

Como en las plataformas reales, la API entrega datos completos (también los del cliente de cada pedido) y no sabe
nada de WhatsApp ni de quién pregunta: el resguardo lo pone quien conecta un agente.
"""
import contextvars
import hmac
import os

from fastapi import APIRouter, Body, Depends, Form, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from . import accesos, datos, reglas
from .plataforma import PLATAFORMA, TIENDA_CODIGO

router = APIRouter(prefix="/api/v1")
oauth = APIRouter(prefix="/api/oauth")
ESTADOS = ["pago pendiente", "pagado", "en preparación", "despachado", "entregado", "preventa", "en cambio", "cancelado",
           "reembolsado", "pago rechazado"]
ACCESO = contextvars.ContextVar("acceso", default=None)   # lo usa también el MCP


def resolver_acceso(cabeceras):
    """Devuelve (acceso, error). acceso = {"via", "nombre", "alcances"}."""
    token = cabeceras.get("x-mostrador-access-token", "")
    if token:
        a, error = accesos.verificar_token(token)
        if error:
            return None, error
        return {"via": "app", "nombre": a["nombre"], "alcances": set(a["alcances_instalados"])}, None
    login, clave = accesos.credenciales_cuenta()
    if cabeceras.get("x-login-key") or cabeceras.get("x-auth-token"):
        if hmac.compare_digest(cabeceras.get("x-login-key", ""), login) and hmac.compare_digest(cabeceras.get("x-auth-token", ""), clave):
            return {"via": "cuenta", "nombre": "Credenciales de la cuenta", "alcances": set(accesos.ALCANCES)}, None
        return None, "Credenciales de la cuenta inválidas. Cópialas desde el panel: Configuración → API."
    return None, ("Falta autenticación. Usa una app de desarrollador (encabezado X-Mostrador-Access-Token) o las "
                  "credenciales de la cuenta (X-Login-Key y X-Auth-Token).")


def requiere(alcance):
    def dependencia(request: Request,
                    x_mostrador_access_token: str = Header("", alias="X-Mostrador-Access-Token", include_in_schema=True),
                    x_login_key: str = Header("", alias="X-Login-Key"), x_auth_token: str = Header("", alias="X-Auth-Token")):
        acceso, error = resolver_acceso({k.lower(): v for k, v in request.headers.items()})
        if error:
            raise HTTPException(401, error)
        if alcance not in acceso["alcances"]:
            raise HTTPException(403, f"La app «{acceso['nombre']}» no tiene el alcance «{alcance}». "
                                     "Agrégalo en el portal de desarrolladores, lanza una versión nueva y vuelve a instalarla.")
        return acceso
    return Depends(dependencia)


# ─────────────────────────── Canje del token (client credentials) ───────────────────────────
@oauth.post("/access_token", tags=["autenticación"])
async def access_token(request: Request):
    """Canjea el ID de cliente y el secreto de una app instalada por un token que dura 24 horas.
    Acepta formulario o JSON con `grant_type=client_credentials`, `client_id` y `client_secret`."""
    if "json" in request.headers.get("content-type", ""):
        d = await request.json()
    else:
        d = dict(await request.form())
    if d.get("grant_type") != "client_credentials":
        return JSONResponse({"error": "unsupported_grant_type", "error_description": "Usa grant_type=client_credentials."}, 400)
    r, error = accesos.emitir_token(d.get("client_id", ""), d.get("client_secret", ""))
    if error:
        return JSONResponse({"error": "invalid_client", "error_description": error}, 401)
    return r


# ─────────────────────────── Formatos ───────────────────────────
def _base(request):
    return str(request.base_url).rstrip("/")


def producto_json(p, base):
    return {"sku": p["sku"], "name": p["nombre"], "category": p["categoria"], "price": p["precio"], "currency": "CLP",
            "description": p["descripcion"], "permalink": f"{base}/p/{p['sku']}",
            "image": f"{base}/static/fotos/{p['sku']}.jpg" if os.path.exists(os.path.join(datos.TIENDA, "static", "fotos", f"{p['sku']}.jpg")) else None,
            "variants": [{"color": v["color"], "size": v["talla"], "available": v["stock"], "status": v["estado"]} for v in p["variantes"]]}


def pedido_json(p, con_cliente=True):
    j = {"number": p["numero"], "created_at": f"{p['fecha']}T{p['hora']}", "status": p["estado"], **datos.estados_de(p["estado"]),
         "shipping": {"comuna": p["comuna"], "zone": p["zona"], "cost": p["despacho"],
                      "courier": p["courier"] or None, "tracking": p["seguimiento"] or None,
                      "shipped_at": p["fecha_despacho"] or None, "estimated_delivery": p["fecha_estimada"] or None,
                      "delivered_at": p["fecha_entrega"] or None},
         "payment": {"method": p["medio_pago"], "subtotal": p["subtotal"], "discount_code": p["codigo"] or None,
                     "discount": p["descuento"], "total": p["total"]},
         "items": [{"sku": i["sku"], "name": i["producto"], "color": i["color"], "size": i["talla"], "quantity": i["cantidad"],
                    "unit_price": i["precio_unitario"]} for i in p["items"]],
         "internal_note": p["nota_interna"] or None}
    if con_cliente:
        j["customer"] = {"name": p["cliente"], "email": p["email"], "phone": p["telefono"]}
        j["shipping"]["address"] = p["direccion"] or None
    return j


# ─────────────────────────── Tienda, envíos y políticas ───────────────────────────
@router.get("/store", tags=["tienda"])
def tienda(request: Request, acceso=requiere("leer_envios")):
    """Datos de la tienda y su configuración de envíos.

    `state` dice en qué estado del curso está la tienda: «antes» (la del 29-sep, con sus contradicciones) o
    «despues» (las Políticas de Kiltra v1 aplicadas). `test_orders` dice si están cargados los pedidos de prueba
    de la batería (KT-9001 a KT-9006)."""
    t, e = datos.config("tienda"), datos.config("envios")
    return {"platform": PLATAFORMA, "code": TIENDA_CODIGO, "name": t["nombre"], "url": _base(request), "email": t["email"],
            "state": datos.estado(), "test_orders": datos.hay_pedidos_de_prueba(),
            "hours": t["horario"], "pickup": t.get("showroom"), "size_guide": datos.tallas(),
            "shipping": {"courier": e["courier"], "free_from": e["gratis_desde"], "zones": e["zonas"], "comunas": e["comunas"],
                         "counted_from": e.get("cuenta_desde", "compra"), "courier_pickup_days": e.get("dias_de_retiro"),
                         "note": e.get("nota_retiro"), "coverage": e.get("cobertura"),
                         "estimate_if_bought_now": reglas.estimados_si_compras_hoy(),
                         "estimate_computed_at": reglas.ahora().isoformat(timespec="minutes"),
                         "upcoming_holidays": reglas.feriados_proximos()}}


@router.get("/policies", tags=["tienda"])
def politicas(acceso=requiere("leer_politicas")):
    """Políticas de la tienda: el texto que ve el cliente y las reglas con datos (plazos, condiciones)."""
    return datos.config("politicas")


@router.get("/pages", tags=["tienda"])
def paginas(acceso=requiere("leer_paginas")):
    """Páginas de contenido de la tienda (preguntas frecuentes)."""
    return datos.config("paginas")


@router.get("/discounts", tags=["tienda"])
def descuentos(acceso=requiere("leer_descuentos")):
    return {"discounts": datos.config("descuentos")}


# ─────────────────────────── Productos e inventario ───────────────────────────
@router.get("/products", tags=["productos"])
def productos(request: Request, query: str = "", category: str = "", size: str = "", color: str = "",
              max_price: int | None = None, limit: int = Query(50, le=100), acceso=requiere("leer_productos")):
    """Lista o busca productos, con sus variantes. El stock disponible de cada variante requiere leer_inventario."""
    res = datos.buscar(query, category, size, color, max_price)
    out = [producto_json(p, _base(request)) for p in res[:limit]]
    if "leer_inventario" not in acceso["alcances"]:
        for p in out:
            for v in p["variants"]:
                v.pop("available")
    return {"count": len(res), "products": out}


@router.get("/products/{sku}", tags=["productos"])
def producto(request: Request, sku: str, acceso=requiere("leer_productos")):
    p = datos.producto(sku)
    if not p:
        raise HTTPException(404, "No existe un producto con ese SKU.")
    j = producto_json(p, _base(request))
    if "leer_inventario" not in acceso["alcances"]:
        for v in j["variants"]:
            v.pop("available")
    return j


@router.put("/products/{sku}/variants", tags=["productos"])
def actualizar_stock(sku: str, color: str = Body(...), size: str = Body(...), available: int = Body(..., ge=0),
                     acceso=requiere("escribir_inventario")):
    """Cambia el stock disponible de una variante (color y talla)."""
    p = datos.producto(sku)
    if not p or not any(v["color"] == color and v["talla"] == size for v in p["variantes"]):
        raise HTTPException(404, "No existe esa variante.")
    datos.guardar_stock({(p["sku"], color, size): available})
    return {"sku": p["sku"], "color": color, "size": size, "available": available}


# ─────────────────────────── Pedidos y clientes ───────────────────────────
@router.get("/orders", tags=["pedidos"])
def pedidos(status: str = "", query: str = "", limit: int = Query(50, le=200), acceso=requiere("leer_pedidos")):
    """Lista pedidos (los más nuevos primero), con los datos del cliente de cada uno."""
    return {"orders": [pedido_json(p) for p in datos.pedidos(status or None, query or None, limit)]}


@router.get("/orders/{number}", tags=["pedidos"])
def pedido(number: str, acceso=requiere("leer_pedidos")):
    p = datos.pedido(number)
    if not p:
        raise HTTPException(404, "No existe un pedido con ese número.")
    return pedido_json(p)


@router.put("/orders/{number}", tags=["pedidos"])
def cambiar_estado(number: str, status: str = Body(..., embed=True), acceso=requiere("escribir_pedidos")):
    """Cambia el estado de un pedido."""
    p = datos.pedido(number)
    if not p:
        raise HTTPException(404, "No existe un pedido con ese número.")
    if status not in ESTADOS:
        raise HTTPException(422, f"Estado no válido. Usa uno de: {', '.join(ESTADOS)}.")
    datos.cambiar_estado(p["numero"], status)
    return pedido_json(datos.pedido(p["numero"]))


@router.get("/customers", tags=["clientes"])
def clientes(query: str = "", limit: int = Query(50, le=500), acceso=requiere("leer_clientes")):
    """Clientes de la tienda (nombre, correo, teléfono, comuna, pedidos y total comprado)."""
    return {"customers": [{"name": c["nombre"], "email": c["email"], "phone": c["telefono"], "comuna": c["comuna"],
                           "orders_count": c["pedidos"], "total_spent": c["total"], "last_order": c["ultima"]}
                          for c in datos.clientes(query or None, limit)]}
