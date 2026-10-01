"""API de administrador de la plataforma (como la de Shopify o Jumpseller, simplificada).

Igual que en las plataformas reales:
- se entra con dos credenciales que la dueña copia del panel (Configuración → API): X-Login-Key y X-Auth-Token;
- entrega TODO: datos de todos los clientes (nombre, correo, teléfono, dirección) y permite modificar stock y pedidos;
- no sabe nada de WhatsApp ni de quién pregunta. El resguardo lo pone quien conecta un agente (el intermediario).
"""
import hashlib
import hmac
import os
import secrets

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request

from . import datos
from .plataforma import PLATAFORMA, TIENDA_CODIGO

router = APIRouter(prefix="/api/v1")
ESTADOS = ["pago pendiente", "pagado", "en preparación", "despachado", "entregado", "preventa", "en cambio", "cancelado",
           "reembolsado", "pago rechazado"]


def credenciales():
    """Login Key y Auth Token de la tienda. En la nube salen de variables de entorno (estables entre reinicios);
    en local se generan una vez. «Regenerar» en el panel los reemplaza hasta el próximo reinicio."""
    semilla = (os.environ.get("KILTRA_SECRETO") or "secreto-local-de-desarrollo").encode()
    estable = f"{TIENDA_CODIGO}-{hashlib.sha256(semilla + b'login').hexdigest()[:10]}"
    login = datos.meta("api_login") or datos.meta("api_login", os.environ.get("KILTRA_API_LOGIN") or estable)
    token = datos.meta("api_token") or datos.meta("api_token", os.environ.get("KILTRA_API_KEY") or secrets.token_hex(16))
    return login, token


def regenerar_token():
    return datos.meta("api_token", secrets.token_hex(16))


def con_credenciales(x_login_key: str = Header("", alias="X-Login-Key"), x_auth_token: str = Header("", alias="X-Auth-Token")):
    login, token = credenciales()
    if not (hmac.compare_digest(x_login_key, login) and hmac.compare_digest(x_auth_token, token)):
        raise HTTPException(401, "Credenciales inválidas. Cópialas desde el panel: Configuración → API.")


def _base(request):
    return str(request.base_url).rstrip("/")


def producto_json(p, base):
    return {"sku": p["sku"], "name": p["nombre"], "category": p["categoria"], "price": p["precio"], "currency": "CLP",
            "description": p["descripcion"], "permalink": f"{base}/p/{p['sku']}",
            "image": f"{base}/static/fotos/{p['sku']}.jpg" if os.path.exists(os.path.join(datos.TIENDA, "static", "fotos", f"{p['sku']}.jpg")) else None,
            "variants": [{"color": v["color"], "size": v["talla"], "stock": v["stock"], "status": v["estado"]} for v in p["variantes"]]}


def pedido_json(p):
    return {"number": p["numero"], "created_at": f"{p['fecha']}T{p['hora']}", "status": p["estado"],
            "customer": {"name": p["cliente"], "email": p["email"], "phone": p["telefono"]},
            "shipping": {"address": p["direccion"] or None, "comuna": p["comuna"], "zone": p["zona"], "cost": p["despacho"],
                         "courier": p["courier"] or None, "tracking": p["seguimiento"] or None,
                         "shipped_at": p["fecha_despacho"] or None, "estimated_delivery": p["fecha_estimada"] or None,
                         "delivered_at": p["fecha_entrega"] or None},
            "payment": {"method": p["medio_pago"], "subtotal": p["subtotal"], "discount_code": p["codigo"] or None,
                        "discount": p["descuento"], "total": p["total"]},
            "items": [{"sku": i["sku"], "name": i["producto"], "color": i["color"], "size": i["talla"], "quantity": i["cantidad"],
                       "unit_price": i["precio_unitario"]} for i in p["items"]],
            "internal_note": p["nota_interna"] or None}


@router.get("/store", tags=["tienda"], dependencies=[Depends(con_credenciales)])
def tienda(request: Request):
    """Datos de la tienda y su configuración de envíos."""
    t, e = datos.config("tienda"), datos.config("envios")
    return {"platform": PLATAFORMA, "code": TIENDA_CODIGO, "name": t["nombre"], "url": _base(request), "email": t["email"],
            "shipping": {"courier": e["courier"], "free_from": e["gratis_desde"], "zones": e["zonas"]}}


@router.get("/products", tags=["productos"], dependencies=[Depends(con_credenciales)])
def productos(request: Request, query: str = "", category: str = "", size: str = "", color: str = "",
              max_price: int | None = None, limit: int = Query(50, le=100)):
    """Lista o busca productos, con todas sus variantes y el stock de cada una."""
    res = datos.buscar(query, category, size, color, max_price)
    return {"count": len(res), "products": [producto_json(p, _base(request)) for p in res[:limit]]}


@router.get("/products/{sku}", tags=["productos"], dependencies=[Depends(con_credenciales)])
def producto(request: Request, sku: str):
    p = datos.producto(sku)
    if not p:
        raise HTTPException(404, "No existe un producto con ese SKU.")
    return producto_json(p, _base(request))


@router.put("/products/{sku}/variants", tags=["productos"], dependencies=[Depends(con_credenciales)])
def actualizar_stock(sku: str, color: str = Body(...), size: str = Body(...), stock: int = Body(..., ge=0)):
    """Cambia el stock de una variante (color y talla)."""
    p = datos.producto(sku)
    if not p or not any(v["color"] == color and v["talla"] == size for v in p["variantes"]):
        raise HTTPException(404, "No existe esa variante.")
    datos.guardar_stock({(p["sku"], color, size): stock})
    return {"sku": p["sku"], "color": color, "size": size, "stock": stock}


@router.get("/orders", tags=["pedidos"], dependencies=[Depends(con_credenciales)])
def pedidos(status: str = "", query: str = "", limit: int = Query(50, le=200)):
    """Lista pedidos (los más nuevos primero), con los datos completos del cliente."""
    return {"orders": [pedido_json(p) for p in datos.pedidos(status or None, query or None, limit)]}


@router.get("/orders/{number}", tags=["pedidos"], dependencies=[Depends(con_credenciales)])
def pedido(number: str):
    p = datos.pedido(number)
    if not p:
        raise HTTPException(404, "No existe un pedido con ese número.")
    return pedido_json(p)


@router.put("/orders/{number}", tags=["pedidos"], dependencies=[Depends(con_credenciales)])
def cambiar_estado(number: str, status: str = Body(..., embed=True)):
    """Cambia el estado de un pedido."""
    p = datos.pedido(number)
    if not p:
        raise HTTPException(404, "No existe un pedido con ese número.")
    if status not in ESTADOS:
        raise HTTPException(422, f"Estado no válido. Usa uno de: {', '.join(ESTADOS)}.")
    datos.cambiar_estado(p["numero"], status)
    return pedido_json(datos.pedido(p["numero"]))


@router.get("/customers", tags=["clientes"], dependencies=[Depends(con_credenciales)])
def clientes(query: str = "", limit: int = Query(50, le=500)):
    """Clientes de la tienda (nombre, correo, teléfono, comuna, pedidos y total comprado)."""
    return {"customers": [{"name": c["nombre"], "email": c["email"], "phone": c["telefono"], "comuna": c["comuna"],
                           "orders_count": c["pedidos"], "total_spent": c["total"], "last_order": c["ultima"]}
                          for c in datos.clientes(query or None, limit)]}
