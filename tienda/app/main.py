"""Tienda web de Kiltra (ficticia): vitrina, carro, checkout simulado, seguimiento, panel y API.

Correr en local:  python -m uvicorn app.main:app --port 8000   (desde la carpeta tienda/)
"""
import base64
import datetime as dt
import hashlib
import hmac
import json
import os

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import datos, reglas
from .datos import caso

TIENDA = datos.TIENDA
FOTOS = os.path.join(TIENDA, "static", "fotos")
# En local hay claves de desarrollo. Publicada (Render define RENDER; Hugging Face, SPACE_ID), la tienda nunca
# las usa: si falta una clave, el panel o la API quedan cerrados en vez de abrirse con una clave conocida.
PUBLICADA = bool(os.environ.get("RENDER") or os.environ.get("SPACE_ID") or os.environ.get("KILTRA_PUBLICADA"))
_dev = lambda clave, valor: os.environ.get(clave) or (None if PUBLICADA else valor)
SECRETO = (_dev("KILTRA_SECRETO", "secreto-local-de-desarrollo") or os.urandom(32).hex()).encode()
CLAVE_ADMIN = _dev("KILTRA_ADMIN_CLAVE", "demo")
API_KEY = _dev("KILTRA_API_KEY", "demo-local")
WHATSAPP = os.environ.get("KILTRA_WHATSAPP", "")          # número del sandbox de Kapso, si se quiere enlazar

datos.crear_base()
app = FastAPI(title="Kiltra — API de la tienda (ficticia)", docs_url="/api/docs", redoc_url=None,
              openapi_url="/api/openapi.json",
              description="API de la tienda ficticia Kiltra, para el curso de agentes de WhatsApp de OVO. "
                          "Requiere el encabezado X-API-Key.")
app.mount("/static", StaticFiles(directory=os.path.join(TIENDA, "static")), name="static")
plantillas = Jinja2Templates(directory=os.path.join(TIENDA, "app", "plantillas"))
J = plantillas.env
J.globals.update(pesos=reglas.pesos, muestra=reglas.muestra, fecha_larga=reglas.fecha_larga, categorias=datos.CATEGORIAS,
                 slug=datos.SLUG, gratis_desde=reglas.GRATIS_DESDE, plazo_rm=caso.POLITICAS["plazo_prometido"]["RM"],
                 whatsapp=WHATSAPP)
J.filters["fecha"] = lambda s: dt.date.fromisoformat(s) if s else None


def _colores_foto():
    try:
        with open(os.path.join(FOTOS, "colores.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


COLOR_FOTO = _colores_foto()


def foto(sku):
    return f"/static/fotos/{sku}.jpg" if os.path.exists(os.path.join(FOTOS, f"{sku}.jpg")) else None


def _preparar(p):
    """Ordena los colores para que el primero sea el de la foto."""
    if not p:
        return p
    fc = COLOR_FOTO.get(p["sku"])
    if fc in p["colores"]:
        p["colores"] = [fc] + [c for c in p["colores"] if c != fc]
    p["foto"] = foto(p["sku"])
    p["color_foto"] = fc
    return p


J.globals.update(foto=foto)


# ─────────────────────────── Carro (cookie) ───────────────────────────
def leer_carro(request):
    try:
        return json.loads(base64.urlsafe_b64decode(request.cookies.get("carro", "")).decode()) or []
    except Exception:
        return []


def escribir_carro(resp, carro):
    resp.set_cookie("carro", base64.urlsafe_b64encode(json.dumps(carro).encode()).decode(), max_age=60 * 60 * 24 * 14,
                    httponly=True, samesite="lax")


def detalle_carro(carro):
    lineas, subtotal = [], 0
    for i, (sku, color, talla, cant) in enumerate(carro):
        p = datos.producto(sku)
        if not p:
            continue
        v = next((v for v in p["variantes"] if v["color"] == color and v["talla"] == talla), None)
        stock = v["stock"] if v else 0
        lineas.append({"i": i, "sku": sku, "producto": p["nombre"], "color": color, "talla": talla, "cantidad": cant,
                       "precio_unitario": p["precio"], "total": p["precio"] * cant, "stock": stock, "foto": foto(sku),
                       "preventa": v["estado"] if v and v["estado"].startswith("preventa") else None})
        subtotal += p["precio"] * cant
    return lineas, subtotal


def contexto(request, **kw):
    carro = leer_carro(request)
    return {"request": request, "n_carro": sum(c[3] for c in carro), **kw}


def html(request, plantilla, status=200, **kw):
    return plantillas.TemplateResponse(request, plantilla, contexto(request, **kw), status_code=status)


# ─────────────────────────── Vitrina ───────────────────────────
@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    destacados = [_preparar(p) for p in datos.mas_pedidos(8)]
    return html(request, "inicio.html", destacados=destacados, portada=_preparar(datos.producto("CAM-002")))


@app.get("/c/{slug}", response_class=HTMLResponse)
def categoria(request: Request, slug: str, orden: str = "relevancia"):
    cat = datos.DESDE_SLUG.get(slug)
    if not cat:
        raise HTTPException(404)
    ps = [_preparar(p) for p in datos.productos(cat, orden)]
    return html(request, "categoria.html", titulo=datos.NOMBRE_CAT[cat], productos=ps, slug_actual=slug, orden=orden)


@app.get("/buscar", response_class=HTMLResponse)
def buscar(request: Request, q: str = ""):
    ps = [_preparar(p) for p in datos.buscar(texto=q)] if q.strip() else []
    return html(request, "categoria.html", titulo=f"Resultados para «{q}»" if q else "Buscar", productos=ps, q=q,
                slug_actual=None, orden=None)


@app.get("/p/{sku}", response_class=HTMLResponse)
def ficha(request: Request, sku: str, color: str = "", comuna: str = "", agregado: int = 0):
    p = _preparar(datos.producto(sku))
    if not p:
        raise HTTPException(404)
    color = color if color in p["colores"] else (p["colores"][0] if p["colores"] else "")
    tallas = [v for v in p["variantes"] if v["color"] == color]
    despacho = None
    if comuna:
        costo = reglas.costo_despacho(comuna, p["precio"])
        despacho = {"comuna": comuna, "costo": costo, "fecha": reglas.fecha_estimada(comuna)} if costo is not None else {"comuna": comuna}
    relacionados = [_preparar(x) for x in datos.productos(p["categoria"]) if x["sku"] != p["sku"]][:4]
    return html(request, "producto.html", p=p, color=color, tallas=tallas, despacho=despacho, comunas=reglas.COMUNAS,
                agregado=agregado, relacionados=relacionados, guia=caso.GUIA_TALLAS["web"])


# ─────────────────────────── Carro y checkout ───────────────────────────
@app.post("/carro/agregar")
def carro_agregar(request: Request, sku: str = Form(...), color: str = Form(...), talla: str = Form(...), cantidad: int = Form(1)):
    carro = leer_carro(request)
    for c in carro:
        if c[:3] == [sku, color, talla]:
            c[3] += cantidad
            break
    else:
        carro.append([sku, color, talla, cantidad])
    resp = RedirectResponse(f"/p/{sku}?color={color}&agregado=1", status_code=303)
    escribir_carro(resp, carro)
    return resp


@app.get("/carro", response_class=HTMLResponse)
def carro(request: Request):
    lineas, subtotal = detalle_carro(leer_carro(request))
    return html(request, "carro.html", lineas=lineas, subtotal=subtotal, falta=max(0, reglas.GRATIS_DESDE - subtotal))


@app.post("/carro/actualizar")
def carro_actualizar(request: Request, i: int = Form(...), cantidad: int = Form(...)):
    carro = leer_carro(request)
    if 0 <= i < len(carro):
        if cantidad <= 0:
            carro.pop(i)
        else:
            carro[i][3] = min(cantidad, 10)
    resp = RedirectResponse("/carro", status_code=303)
    escribir_carro(resp, carro)
    return resp


def _calcular(lineas, subtotal, comuna, codigo, email):
    descuento, msg_codigo = reglas.validar_codigo(codigo, email, subtotal)
    neto = subtotal - descuento
    envio = reglas.costo_despacho(comuna, neto) if comuna else None
    return {"descuento": descuento, "msg_codigo": msg_codigo, "neto": neto, "envio": envio,
            "total": neto + (envio or 0), "fecha": reglas.fecha_estimada(comuna) if comuna else None}


@app.get("/checkout", response_class=HTMLResponse)
def checkout(request: Request):
    lineas, subtotal = detalle_carro(leer_carro(request))
    if not lineas:
        return RedirectResponse("/carro", status_code=303)
    return html(request, "checkout.html", lineas=lineas, subtotal=subtotal, f={}, calc=_calcular(lineas, subtotal, "", "", ""),
                comunas=reglas.COMUNAS, error=None)


@app.post("/checkout", response_class=HTMLResponse)
def checkout_enviar(request: Request, nombre: str = Form(""), email: str = Form(""), telefono: str = Form(""),
                    direccion: str = Form(""), comuna: str = Form(""), codigo: str = Form(""), medio_pago: str = Form("Webpay crédito"),
                    accion: str = Form("pagar")):
    lineas, subtotal = detalle_carro(leer_carro(request))
    if not lineas:
        return RedirectResponse("/carro", status_code=303)
    f = {"nombre": nombre.strip(), "email": email.strip(), "telefono": telefono.strip(), "direccion": direccion.strip(),
         "comuna": comuna, "codigo": codigo.strip().upper(), "medio_pago": medio_pago}
    calc = _calcular(lineas, subtotal, comuna, codigo, email)
    error = None
    if accion == "pagar":
        faltan = [n for n, k in (("nombre", "nombre"), ("correo", "email"), ("teléfono", "telefono"), ("dirección", "direccion"),
                                ("comuna", "comuna")) if not f[k]]
        if faltan:
            error = "Completa " + ", ".join(faltan) + " para seguir."
        elif "@" not in f["email"]:
            error = "El correo no parece válido: revisa que tenga @."
        elif sum(ch.isdigit() for ch in f["telefono"]) < 8:
            error = "El teléfono tiene que tener al menos 8 dígitos."
        else:
            ahora = reglas.ahora()
            estado = "pago pendiente" if medio_pago == "Transferencia" else "pagado"
            try:
                numero = datos.crear_pedido({
                    "fecha": ahora.date().isoformat(), "hora": ahora.strftime("%H:%M"), "cliente": f["nombre"], "email": f["email"],
                    "telefono": f["telefono"], "direccion": f["direccion"], "comuna": comuna, "zona": reglas.zona(comuna),
                    "subtotal": subtotal, "codigo": f["codigo"] if calc["descuento"] else "", "descuento": calc["descuento"],
                    "despacho": calc["envio"], "total": calc["total"], "medio_pago": medio_pago, "estado": estado,
                    "courier": "", "seguimiento": "", "fecha_despacho": "", "fecha_estimada": calc["fecha"].isoformat(),
                    "fecha_entrega": "", "nota_interna": "", "origen": "web"}, lineas)
            except datos.SinStock as e:
                error = f"Mientras comprabas se acabó el stock de {e}. Ajusta tu carro para seguir."
            else:
                resp = RedirectResponse(f"/pedido/{numero}?t={_firma(numero)}", status_code=303)
                escribir_carro(resp, [])
                return resp
    return html(request, "checkout.html", lineas=lineas, subtotal=subtotal, f=f, calc=calc, comunas=reglas.COMUNAS, error=error,
                status=400 if error else 200)


def _firma(numero):
    return hmac.new(SECRETO, numero.encode(), hashlib.sha256).hexdigest()[:16]


@app.get("/pedido/{numero}", response_class=HTMLResponse)
def confirmacion(request: Request, numero: str, t: str = ""):
    p = datos.pedido(numero)
    if not p or not hmac.compare_digest(t, _firma(p["numero"])):
        raise HTTPException(404)
    return html(request, "confirmacion.html", p=p)


# ─────────────────────────── Seguimiento e información ───────────────────────────
ETAPAS = ["pagado", "en preparación", "despachado", "entregado"]


@app.get("/seguimiento", response_class=HTMLResponse)
def seguimiento(request: Request):
    return html(request, "seguimiento.html", p=None, error=None, numero="", email="")


@app.post("/seguimiento", response_class=HTMLResponse)
def seguimiento_buscar(request: Request, numero: str = Form(""), email: str = Form("")):
    p = datos.pedido(numero) if numero.strip() else None
    if not p or p["email"].lower() != email.strip().lower():
        return html(request, "seguimiento.html", p=None, numero=numero, email=email, status=404,
                    error="No encontramos un pedido con ese número y ese correo. Revisa los dos datos en el correo de confirmación.")
    return html(request, "seguimiento.html", p=p, etapas=ETAPAS, numero=numero, email=email, error=None)


def _faq():
    import documentos
    bloques, actual = [], None
    for linea in documentos.preguntas_frecuentes().strip().splitlines()[3:]:
        if linea.startswith("¿") and linea.endswith("?") and linea.upper() == linea:
            s = linea.lower()
            actual = {"pregunta": s[0] + s[1].upper() + s[2:], "respuesta": []}
            bloques.append(actual)
        elif actual is not None and linea.strip():
            l, r = linea.strip(), actual["respuesta"]
            # el texto viene cortado a lo ancho: una línea que sigue la oración anterior se une a ella
            if r and r[-1][-1] not in ".!?:" and l[0].islower():
                r[-1] += " " + l
            else:
                r.append(l)
    return bloques


@app.get("/preguntas-frecuentes", response_class=HTMLResponse)
def faq(request: Request):
    return html(request, "faq.html", bloques=_faq())


@app.get("/guia-de-tallas", response_class=HTMLResponse)
def guia(request: Request):
    return html(request, "tallas.html", guia=caso.GUIA_TALLAS["web"])


# ─────────────────────────── Panel de la tienda ───────────────────────────
basica = HTTPBasic(realm="Panel de Kiltra")


def admin(cred: HTTPBasicCredentials = Depends(basica)):
    if not CLAVE_ADMIN:
        raise HTTPException(503, "El panel está cerrado: falta configurar KILTRA_ADMIN_CLAVE.")
    if not (hmac.compare_digest(cred.username, "kiltra") and hmac.compare_digest(cred.password, CLAVE_ADMIN)):
        raise HTTPException(401, headers={"WWW-Authenticate": 'Basic realm="Panel de Kiltra"'})
    return cred.username


@app.get("/admin", response_class=HTMLResponse)
def admin_pedidos(request: Request, estado: str = "", q: str = "", _=Depends(admin)):
    return html(request, "admin_pedidos.html", pedidos=datos.pedidos(estado or None, q or None), estados=datos.estados_pedidos(),
                estado=estado, q=q)


@app.get("/admin/pedidos/{numero}", response_class=HTMLResponse)
def admin_pedido(request: Request, numero: str, _=Depends(admin)):
    p = datos.pedido(numero)
    if not p:
        raise HTTPException(404)
    return html(request, "admin_pedido.html", p=p, estados=ETAPAS + ["pago pendiente", "preventa", "en cambio", "cancelado",
                                                                   "reembolsado", "pago rechazado"])


@app.post("/admin/pedidos/{numero}")
def admin_pedido_estado(numero: str, estado: str = Form(...), _=Depends(admin)):
    datos.cambiar_estado(numero, estado)
    return RedirectResponse(f"/admin/pedidos/{numero}", status_code=303)


@app.get("/admin/stock", response_class=HTMLResponse)
def admin_stock(request: Request, _=Depends(admin)):
    with datos.conexion() as con:
        filas = [dict(f) for f in con.execute("SELECT v.*, p.nombre FROM variantes v JOIN productos p ON p.sku=v.sku ORDER BY v.orden")]
    return html(request, "admin_stock.html", filas=filas, guardado=request.query_params.get("guardado"))


@app.post("/admin/stock")
async def admin_stock_guardar(request: Request, _=Depends(admin)):
    form = await request.form()
    cambios = {}
    for k, v in form.items():
        if k.startswith("s|") and str(v).strip().lstrip("-").isdigit():
            _, sku, color, talla = k.split("|")
            cambios[(sku, color, talla)] = int(v)
    datos.guardar_stock(cambios)
    return RedirectResponse("/admin/stock?guardado=1", status_code=303)


@app.get("/admin/exportar/{que}.csv")
def admin_exportar(que: str, _=Depends(admin)):
    if que not in ("productos", "pedidos"):
        raise HTTPException(404)
    texto = datos.exportar_productos() if que == "productos" else datos.exportar_pedidos()
    return Response(texto.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="export-{que}-web.csv"'})


# ─────────────────────────── API ───────────────────────────
def con_llave(x_api_key: str = Header("", alias="X-API-Key")):
    if not API_KEY:
        raise HTTPException(503, "La API está cerrada: falta configurar KILTRA_API_KEY.")
    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(401, "Falta el encabezado X-API-Key o no es válido.")


def _producto_api(p, base):
    vs = p.get("coinciden", p["variantes"])
    por_color = {}
    for v in vs:
        if v["stock"] > 0:
            por_color.setdefault(v["color"], []).append(v["talla"] if v["stock"] > 2 else f"{v['talla']} (quedan {v['stock']})")
    return {"sku": p["sku"], "nombre": p["nombre"], "categoria": p["categoria"], "precio": p["precio"],
            "disponible": bool(por_color), "tallas_con_stock_por_color": por_color,
            "agotado_en": [f"{v['color']} {v['talla']}" for v in vs if v["stock"] == 0],
            "preventa": p["preventa"], "url": f"{base}p/{p['sku']}",
            "imagen_url": f"{base}static/fotos/{p['sku']}.jpg" if foto(p["sku"]) else None}


@app.get("/api/v1/productos", tags=["catálogo"], dependencies=[Depends(con_llave)])
def api_productos(request: Request, texto: str = "", categoria: str = "", talla: str = "", color: str = "",
                  precio_max: int | None = None, sku: str = ""):
    """Busca prendas por texto, categoría, talla, color, precio máximo o SKU. Devuelve hasta 6."""
    res = datos.buscar(texto, categoria, talla, color, precio_max, sku)
    base = str(request.base_url)
    return {"total": len(res), "resultados": [_producto_api(p, base) for p in res[:6]],
            "nota": "Hay más resultados: pide más detalle al cliente." if len(res) > 6 else None}


@app.get("/api/v1/productos/{sku}", tags=["catálogo"], dependencies=[Depends(con_llave)])
def api_producto(request: Request, sku: str):
    p = datos.producto(sku)
    if not p:
        raise HTTPException(404, "No existe ese SKU.")
    return _producto_api(p, str(request.base_url))


@app.get("/api/v1/pedidos/{numero}", tags=["pedidos"], dependencies=[Depends(con_llave)])
def api_pedido(numero: str, telefono: str = Query(..., description="Teléfono desde el que escribe el cliente")):
    """Estado de un pedido. Solo responde si el teléfono coincide con el del pedido (los últimos 8 dígitos)."""
    p = datos.pedido(numero)
    if not p:
        return {"encontrado": False, "mensaje": "No existe un pedido con ese número."}
    dig = lambda s: "".join(ch for ch in s if ch.isdigit())[-8:]
    if not dig(telefono) or dig(telefono) != dig(p["telefono"]):
        return {"encontrado": True, "verificado": False,
                "mensaje": "El teléfono no coincide con el del pedido. No entregues ningún dato del pedido."}
    return {"encontrado": True, "verificado": True, "pedido": {
        k: p[k] for k in ("numero", "fecha", "estado", "comuna", "total", "medio_pago", "courier", "seguimiento",
                          "fecha_despacho", "fecha_estimada", "fecha_entrega")} | {
        "cliente": p["cliente"].split()[0],
        "items": [{k: i[k] for k in ("producto", "color", "talla", "cantidad")} for i in p["items"]]}}


@app.get("/salud", include_in_schema=False)
def salud():
    return {"ok": True}


@app.exception_handler(404)
def no_encontrado(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": getattr(exc, "detail", "No encontrado")}, status_code=404)
    return html(request, "404.html", status=404)
