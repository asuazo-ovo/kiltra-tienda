"""Formato de las exportaciones de la tienda web de Kiltra (CSV de productos y de pedidos).

Lo usan dos lados que tienen que coincidir byte a byte:
- el generador, que escribe `insumos/export-*.csv` (la foto del 29 de septiembre);
- la tienda (`tienda/app`), cuyo panel exporta desde su base de datos.
"""
import csv
import io

import caso

COLS_PRODUCTOS = ["sku", "producto", "categoria", "precio", "color", "talla", "stock", "estado_publicacion", "descripcion"]
COLS_PEDIDOS = ["numero", "fecha", "hora", "cliente", "email", "telefono", "comuna", "zona", "productos", "unidades",
                "subtotal", "codigo", "descuento", "despacho", "total", "medio_pago", "estado", "courier", "seguimiento",
                "fecha_despacho", "fecha_estimada", "fecha_entrega", "nota_interna"]


def _iso(d):
    return d.isoformat() if hasattr(d, "isoformat") else (d or "")


# ── Registros canónicos, construidos desde caso.py (la foto del 29-sep) ──
def variantes_web():
    """Una fila por producto × color × talla, como la tiene la tienda web el 29-sep."""
    for sku, nombre, cat, precio, colores, tallas in caso.PRODUCTOS:
        for c in colores:
            for t in tallas:
                v = (sku, c, t)
                if v in caso.PREVENTA_WEB:
                    stock, est = caso.PREVENTA_WEB[v], f"preventa (llega {caso.PREVENTA_LLEGA.isoformat()})"
                elif v in caso.OCULTOS:
                    stock, est = 0, "oculto"
                else:
                    stock, est = caso.STOCK_WEB[v], "publicado"
                yield {"sku": sku, "producto": nombre, "categoria": cat, "precio": precio, "color": c, "talla": t,
                       "stock": stock, "estado_publicacion": est, "descripcion": caso.DESCRIPCIONES_WEB.get(sku, "")}


def pedidos_web():
    for p in caso.PEDIDOS:
        yield {**p, "hora": caso.hora_pedido(p), "despacho": p["envio"]}


# ── Filas ──
def fila_producto(v):
    return [v[c] for c in COLS_PRODUCTOS]


def fila_pedido(p):
    prods = "; ".join(f"{i['sku']} {i['producto']} {i['color']} {i['talla']} x{i['cantidad']}" for i in p["items"])
    return [p["numero"], _iso(p["fecha"]), p["hora"], p["cliente"], p["email"], p["telefono"], p["comuna"], p["zona"], prods,
            sum(i["cantidad"] for i in p["items"]), p["subtotal"], p["codigo"], p["descuento"], p["despacho"], p["total"],
            p["medio_pago"], p["estado"], p["courier"], p["seguimiento"], _iso(p["fecha_despacho"]),
            _iso(p["fecha_estimada"]), _iso(p["fecha_entrega"]), p["nota_interna"]]


def csv_texto(cols, filas):
    """CSV con BOM (para que Excel lea bien los acentos) y fin de línea \\r\\n, como lo baja la tienda."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    w.writerows(filas)
    return "﻿" + buf.getvalue()


def csv_productos(variantes):
    return csv_texto(COLS_PRODUCTOS, (fila_producto(v) for v in variantes))


def csv_pedidos(pedidos):
    return csv_texto(COLS_PEDIDOS, (fila_pedido(p) for p in pedidos))
