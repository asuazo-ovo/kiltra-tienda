"""Servidor MCP de Mostrador (como el de Jumpseller o el conector de Shopify para Claude): administrar la tienda
desde un asistente de IA. Mismo patrón que SIGMA Mantención (SDK mcp 2.x, streamable HTTP).

Entra con cualquiera de las dos vías de la API (app con alcances, o credenciales de la cuenta) y cada herramienta
exige su alcance. Tiene herramientas que LEEN y que ESCRIBEN: sirve para que la dueña administre su tienda, y es
justamente lo que no se conecta directo a un agente que conversa con desconocidos por WhatsApp.
"""
import json

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import api, datos
from .plataforma import PLATAFORMA

LECTURA = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
ESCRITURA = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
BASE = {"url": ""}   # la fija main.py con la URL pública

mcp = MCPServer(
    f"{PLATAFORMA} · tienda Kiltra",
    instructions=(f"Panel de administración de la tienda Kiltra en {PLATAFORMA} (plataforma de ecommerce ficticia). "
                  "Productos con variantes y stock, pedidos con datos completos de clientes, clientes y políticas. "
                  "Algunas herramientas modifican la tienda. Datos ficticios."),
)


def _j(o):
    return json.dumps(o, ensure_ascii=False, indent=1)


def _sin_permiso(alcance):
    acceso = api.ACCESO.get()
    if not acceso or alcance not in acceso["alcances"]:
        nombre = acceso["nombre"] if acceso else "esta conexión"
        return _j({"error": f"«{nombre}» no tiene el alcance «{alcance}»."})
    return None


@mcp.tool(name="buscar_productos", title="Buscar productos", annotations=LECTURA)
def buscar_productos(texto: str = "", categoria: str = "", talla: str = "", color: str = "", precio_max: int | None = None) -> str:
    """Busca productos por texto, categoría, talla, color o precio máximo, con sus variantes y stock disponible."""
    if e := _sin_permiso("leer_productos"):
        return e
    res = datos.buscar(texto, categoria, talla, color, precio_max)
    return _j({"cantidad": len(res), "productos": [api.producto_json(p, BASE["url"]) for p in res[:20]]})


@mcp.tool(name="ver_pedido", title="Ver un pedido", annotations=LECTURA)
def ver_pedido(numero: str) -> str:
    """Muestra un pedido completo: cliente (nombre, correo, teléfono, dirección), productos, pago, despacho y sus tres estados."""
    if e := _sin_permiso("leer_pedidos"):
        return e
    p = datos.pedido(numero)
    return _j(api.pedido_json(p) if p else {"error": "No existe un pedido con ese número."})


@mcp.tool(name="buscar_pedidos", title="Buscar pedidos", annotations=LECTURA)
def buscar_pedidos(estado: str = "", texto: str = "", limite: int = 20) -> str:
    """Lista pedidos por estado o por texto (número, nombre o correo del cliente)."""
    if e := _sin_permiso("leer_pedidos"):
        return e
    return _j([api.pedido_json(p) for p in datos.pedidos(estado or None, texto or None, min(limite, 100))])


@mcp.tool(name="buscar_clientes", title="Buscar clientes", annotations=LECTURA)
def buscar_clientes(texto: str = "", limite: int = 20) -> str:
    """Busca clientes por nombre, correo o teléfono: datos de contacto, pedidos y total comprado."""
    if e := _sin_permiso("leer_clientes"):
        return e
    return _j(datos.clientes(texto or None, min(limite, 100)))


@mcp.tool(name="ver_politicas", title="Ver las políticas de la tienda", annotations=LECTURA)
def ver_politicas() -> str:
    """Políticas de cambios y devoluciones: el texto que ve el cliente y las reglas con plazos y condiciones."""
    if e := _sin_permiso("leer_politicas"):
        return e
    return _j(datos.config("politicas"))


@mcp.tool(name="actualizar_stock", title="Actualizar stock", annotations=ESCRITURA)
def actualizar_stock(sku: str, color: str, talla: str, stock: int) -> str:
    """Cambia el stock disponible de una variante de un producto. Modifica la tienda."""
    if e := _sin_permiso("escribir_inventario"):
        return e
    p = datos.producto(sku)
    if not p or not any(v["color"] == color and v["talla"] == talla for v in p["variantes"]):
        return _j({"error": "No existe esa variante."})
    datos.guardar_stock({(p["sku"], color, talla): stock})
    return _j({"ok": True, "sku": p["sku"], "color": color, "talla": talla, "stock": max(0, stock)})


@mcp.tool(name="cambiar_estado_pedido", title="Cambiar el estado de un pedido", annotations=ESCRITURA)
def cambiar_estado_pedido(numero: str, estado: str) -> str:
    """Cambia el estado de un pedido (por ejemplo a «cancelado» o «reembolsado»). Modifica la tienda."""
    if e := _sin_permiso("escribir_pedidos"):
        return e
    p = datos.pedido(numero)
    if not p:
        return _j({"error": "No existe un pedido con ese número."})
    if estado not in api.ESTADOS:
        return _j({"error": f"Estado no válido. Usa uno de: {', '.join(api.ESTADOS)}."})
    datos.cambiar_estado(p["numero"], estado)
    return _j({"ok": True, "numero": p["numero"], "estado": estado})
