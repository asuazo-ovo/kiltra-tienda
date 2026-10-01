"""La tienda Kiltra sobre la plataforma ficticia Mostrador (como una tienda en Shopify o Jumpseller).

Tres caras sobre la misma base:
  /            la vitrina de Kiltra (lo que ve el cliente)
  /admin       el panel de Mostrador (lo que ve la dueña): pedidos, productos, clientes, descuentos, envíos,
               páginas y Configuración → API
  /api/v1      la API de administrador de la plataforma (credenciales del panel)   ·   /mcp  su servidor MCP

Correr en local:  python -m uvicorn app.main:app --port 8000   (desde la carpeta tienda/)
"""
import base64
import contextlib
import datetime as dt
import hashlib
import hmac
import json
import os
import time

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import accesos, api, datos, reglas
from .datos import caso
from .plataforma import DOMINIO, PLATAFORMA, PLATAFORMA_LEMA, TIENDA_CODIGO

TIENDA = datos.TIENDA
FOTOS = os.path.join(TIENDA, "static", "fotos")
# En local hay claves de desarrollo. Publicada (Render define RENDER; Hugging Face, SPACE_ID), la tienda nunca
# las usa: si falta una clave, el panel queda cerrado en vez de abrirse con una clave conocida.
PUBLICADA = bool(os.environ.get("RENDER") or os.environ.get("SPACE_ID") or os.environ.get("KILTRA_PUBLICADA"))
_dev = lambda clave, valor: os.environ.get(clave) or (None if PUBLICADA else valor)
SECRETO = (_dev("KILTRA_SECRETO", "secreto-local-de-desarrollo") or os.urandom(32).hex()).encode()
CLAVE_ADMIN = _dev("KILTRA_ADMIN_CLAVE", "demo")
USUARIO_ADMIN = "rocio@kiltra.example"
WHATSAPP = os.environ.get("KILTRA_WHATSAPP", "")          # número del sandbox de Kapso, si se quiere enlazar

datos.crear_base()
accesos.sembrar()
accesos.credenciales_cuenta()

# ─────────────────────────── MCP de la plataforma ───────────────────────────
try:
    from mcp.server.transport_security import TransportSecuritySettings

    from . import mcp_mostrador
    _hosts = ["127.0.0.1:*", "localhost:*"] + ([os.environ["RENDER_EXTERNAL_HOSTNAME"]] if os.environ.get("RENDER_EXTERNAL_HOSTNAME") else [])
    mcp_app = mcp_mostrador.mcp.streamable_http_app(
        streamable_http_path="/", json_response=False, stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=_hosts,
                                                     allowed_origins=[f"https://{h}" for h in _hosts] + [f"http://{h}" for h in _hosts]))
except ImportError:            # sin el paquete mcp la tienda funciona igual, solo sin /mcp
    mcp_mostrador = mcp_app = None


@contextlib.asynccontextmanager
async def ciclo(app):
    if mcp_app:
        async with mcp_mostrador.mcp.session_manager.run():
            yield
    else:
        yield


app = FastAPI(title=f"{PLATAFORMA} — API de administrador (tienda Kiltra)", docs_url="/api/docs", redoc_url=None,
              openapi_url="/api/openapi.json", lifespan=ciclo,
              description=f"API de administrador de {PLATAFORMA}, una plataforma de ecommerce **ficticia** para el curso de "
                          "agentes de WhatsApp de OVO. Se entra por dos vías, como en el mercado: una **app de desarrollador** (como Shopify: `POST /api/oauth/access_token` y luego "
                          "`X-Mostrador-Access-Token`, limitada a sus alcances) o las **credenciales de la cuenta** (como Jumpseller: "
                          "`X-Login-Key` y `X-Auth-Token`, acceso total). Entrega datos completos y permite modificar la tienda.")
app.include_router(api.router)
app.include_router(api.oauth)
app.mount("/static", StaticFiles(directory=os.path.join(TIENDA, "static")), name="static")
if mcp_app:
    app.mount("/mcp", mcp_app)

plantillas = Jinja2Templates(directory=os.path.join(TIENDA, "app", "plantillas"))
J = plantillas.env
J.globals.update(pesos=reglas.pesos, muestra=reglas.muestra, fecha_larga=reglas.fecha_larga, categorias=datos.CATEGORIAS,
                 slug=datos.SLUG, whatsapp=WHATSAPP, plataforma=PLATAFORMA, plataforma_lema=PLATAFORMA_LEMA, dominio=DOMINIO)
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


J.globals.update(foto=foto)


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
    e = reglas.envios()
    return {"request": request, "n_carro": sum(c[3] for c in carro), "gratis_desde": e["gratis_desde"],
            "plazo_rm": e["zonas"]["RM"]["texto"], "tienda": datos.config("tienda"), **kw}


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
    return html(request, "producto.html", p=p, color=color, tallas=tallas, despacho=despacho, comunas=reglas.comunas(),
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
    return html(request, "carro.html", lineas=lineas, subtotal=subtotal, falta=max(0, reglas.envios()["gratis_desde"] - subtotal))


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
                comunas=reglas.comunas(), error=None)


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
    return html(request, "checkout.html", lineas=lineas, subtotal=subtotal, f=f, calc=calc, comunas=reglas.comunas(), error=error,
                status=400 if error else 200)


def _firma(texto):
    return hmac.new(SECRETO, texto.encode(), hashlib.sha256).hexdigest()[:16]


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
    """Arma las preguntas desde el texto que la tienda cargó en el panel (Páginas)."""
    texto = datos.config("paginas")["preguntas-frecuentes"]["texto"]
    bloques, actual = [], None
    for linea in texto.splitlines():
        l = linea.strip()
        if l.startswith("¿") and l.endswith("?"):
            s = l.lower() if l.upper() == l else l
            actual = {"pregunta": s[0] + s[1].upper() + s[2:], "respuesta": []}
            bloques.append(actual)
        elif actual is not None and l:
            r = actual["respuesta"]
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


# ─────────────────────────── Panel de Mostrador ───────────────────────────
SESION = "mostrador_sesion"


def _sesion_valida(request):
    v = request.cookies.get(SESION, "")
    try:
        venc, firma = v.split(".")
        return int(venc) > time.time() and hmac.compare_digest(firma, _firma("panel" + venc))
    except ValueError:
        return False


class NoAutorizado(Exception):
    pass


@app.exception_handler(NoAutorizado)
def _a_entrar(request, exc):
    return RedirectResponse(f"/admin/entrar?volver={request.url.path}", status_code=303)


def panel(request):
    if not _sesion_valida(request):
        raise NoAutorizado()


def phtml(request, plantilla, seccion, status=200, **kw):
    return plantillas.TemplateResponse(request, plantilla, {"request": request, "seccion": seccion,
                                                           "tienda": datos.config("tienda"),
                                                           "apps_nav": [a for a in accesos.apps() if a["instalada"]], **kw},
                                       status_code=status)


@app.get("/admin/entrar", response_class=HTMLResponse)
def entrar(request: Request, volver: str = "/admin"):
    return phtml(request, "panel_entrar.html", None, error=None, volver=volver, cerrado=not CLAVE_ADMIN)


@app.post("/admin/entrar", response_class=HTMLResponse)
def entrar_enviar(request: Request, correo: str = Form(""), clave: str = Form(""), volver: str = Form("/admin")):
    if CLAVE_ADMIN and correo.strip().lower() == USUARIO_ADMIN and hmac.compare_digest(clave, CLAVE_ADMIN):
        venc = str(int(time.time()) + 8 * 3600)
        resp = RedirectResponse(volver if volver.startswith("/admin") else "/admin", status_code=303)
        resp.set_cookie(SESION, f"{venc}.{_firma('panel' + venc)}", max_age=8 * 3600, httponly=True, samesite="lax")
        return resp
    return phtml(request, "panel_entrar.html", None, status=401, volver=volver, cerrado=not CLAVE_ADMIN,
                 error="El correo o la contraseña no coinciden.")


@app.get("/admin/salir")
def salir():
    resp = RedirectResponse("/admin/entrar", status_code=303)
    resp.delete_cookie(SESION)
    return resp


@app.get("/admin", response_class=HTMLResponse)
def p_inicio(request: Request):
    panel(request)
    return phtml(request, "panel_inicio.html", "inicio", r=datos.resumen(), ultimos=datos.pedidos(limite=8),
                 estados=datos.estados_pedidos())


@app.get("/admin/pedidos", response_class=HTMLResponse)
def p_pedidos(request: Request, estado: str = "", q: str = ""):
    panel(request)
    return phtml(request, "panel_pedidos.html", "pedidos", pedidos=datos.pedidos(estado or None, q or None),
                 estados=datos.estados_pedidos(), estado=estado, q=q)


@app.get("/admin/pedidos/{numero}", response_class=HTMLResponse)
def p_pedido(request: Request, numero: str):
    panel(request)
    p = datos.pedido(numero)
    if not p:
        raise HTTPException(404)
    return phtml(request, "panel_pedido.html", "pedidos", p=p, estados=api.ESTADOS)


@app.post("/admin/pedidos/{numero}")
def p_pedido_estado(request: Request, numero: str, estado: str = Form(...)):
    panel(request)
    if estado in api.ESTADOS:
        datos.cambiar_estado(numero, estado)
    return RedirectResponse(f"/admin/pedidos/{numero}?guardado=1", status_code=303)


@app.get("/admin/productos", response_class=HTMLResponse)
def p_productos(request: Request, q: str = ""):
    panel(request)
    ps = datos.buscar(texto=q) if q.strip() else datos.productos()
    return phtml(request, "panel_productos.html", "productos", productos=ps, q=q, guardado=request.query_params.get("guardado"))


@app.post("/admin/productos")
async def p_productos_guardar(request: Request):
    panel(request)
    form = await request.form()
    cambios = {}
    for k, v in form.items():
        if k.startswith("s|") and str(v).strip().isdigit():
            _, sku, color, talla = k.split("|")
            cambios[(sku, color, talla)] = int(v)
    datos.guardar_stock(cambios)
    return RedirectResponse("/admin/productos?guardado=1", status_code=303)


@app.get("/admin/clientes", response_class=HTMLResponse)
def p_clientes(request: Request, q: str = ""):
    panel(request)
    return phtml(request, "panel_clientes.html", "clientes", clientes=datos.clientes(q or None), q=q)


@app.get("/admin/descuentos", response_class=HTMLResponse)
def p_descuentos(request: Request):
    panel(request)
    return phtml(request, "panel_descuentos.html", "descuentos", descuentos=datos.config("descuentos"),
                 hoy=reglas.ahora().date().isoformat(), guardado=request.query_params.get("guardado"))


@app.post("/admin/descuentos")
async def p_descuentos_guardar(request: Request):
    panel(request)
    form = await request.form()
    nuevos = []
    for i in range(int(form.get("n", 0)) + 1):
        codigo = str(form.get(f"codigo_{i}", "")).strip().upper()
        if not codigo or form.get(f"borrar_{i}"):
            continue
        try:
            pct = max(1, min(90, int(form.get(f"porcentaje_{i}", 10))))
        except ValueError:
            pct = 10
        nuevos.append({"codigo": codigo, "porcentaje": pct, "solo_primera_compra": bool(form.get(f"primera_{i}")),
                       "vence": str(form.get(f"vence_{i}", "")).strip() or None, "activo": bool(form.get(f"activo_{i}"))})
    datos.guardar_config("descuentos", nuevos)
    return RedirectResponse("/admin/descuentos?guardado=1", status_code=303)


@app.get("/admin/configuracion", response_class=HTMLResponse)
def p_config_general(request: Request):
    panel(request)
    return phtml(request, "panel_config_general.html", "configuracion", sub="general", guardado=request.query_params.get("guardado"))


@app.post("/admin/configuracion")
async def p_config_general_guardar(request: Request):
    panel(request)
    form = await request.form()
    t = datos.config("tienda")
    for k in ("email", "horario", "showroom"):
        if k in form:
            t[k] = str(form[k]).strip()
    datos.guardar_config("tienda", t)
    return RedirectResponse("/admin/configuracion?guardado=1", status_code=303)


@app.get("/admin/envios")
def p_envios_antes():
    return RedirectResponse("/admin/configuracion/envios", status_code=301)


@app.get("/admin/configuracion/envios", response_class=HTMLResponse)
def p_envios(request: Request):
    panel(request)
    return phtml(request, "panel_envios.html", "configuracion", sub="envios", e=reglas.envios(),
                 guardado=request.query_params.get("guardado"))


@app.post("/admin/configuracion/envios")
async def p_envios_guardar(request: Request):
    panel(request)
    form = await request.form()
    e = reglas.envios()
    num = lambda k, d: int(str(form.get(k, d)).replace(".", "").strip() or d)
    e["gratis_desde"] = num("gratis_desde", e["gratis_desde"])
    for z in e["zonas"]:
        e["zonas"][z] = {"costo": num(f"costo_{z}", e["zonas"][z]["costo"]),
                         "dias_habiles": num(f"dias_{z}", e["zonas"][z]["dias_habiles"]),
                         "texto": str(form.get(f"texto_{z}", e["zonas"][z]["texto"])).strip()}
    datos.guardar_config("envios", e)
    return RedirectResponse("/admin/configuracion/envios?guardado=1", status_code=303)


@app.get("/admin/configuracion/politicas", response_class=HTMLResponse)
def p_politicas(request: Request):
    panel(request)
    return phtml(request, "panel_politicas.html", "configuracion", sub="politicas",
                 pol=datos.config("politicas")["cambios-y-devoluciones"], guardado=request.query_params.get("guardado"))


@app.post("/admin/configuracion/politicas")
async def p_politicas_guardar(request: Request):
    panel(request)
    form = await request.form()
    pols = datos.config("politicas")
    pol = pols["cambios-y-devoluciones"]
    pol["texto"] = str(form.get("texto", pol["texto"])).replace("\r\n", "\n").strip()
    r = pol["reglas"]
    for k in ("cambio_dias", "devolucion_dias"):
        v = str(form.get(k, "")).strip()
        r[k] = int(v) if v.isdigit() else r[k]
    r["desde"] = form.get("desde", r["desde"])
    r["condicion"] = str(form.get("condicion", r["condicion"])).strip()
    r["envio_del_cambio"] = form.get("envio_del_cambio") or None
    r["reembolso"] = str(form.get("reembolso", r["reembolso"])).strip()
    datos.guardar_config("politicas", pols)
    return RedirectResponse("/admin/configuracion/politicas?guardado=1", status_code=303)


@app.get("/politicas/cambios-y-devoluciones", response_class=HTMLResponse)
def politica_publica(request: Request):
    pol = datos.config("politicas")["cambios-y-devoluciones"]
    return html(request, "politica.html", pol=pol)


@app.get("/admin/paginas", response_class=HTMLResponse)
def p_paginas(request: Request):
    panel(request)
    return phtml(request, "panel_paginas.html", "paginas", paginas=datos.config("paginas"), guardado=request.query_params.get("guardado"))


@app.post("/admin/paginas")
def p_paginas_guardar(request: Request, texto: str = Form("")):
    panel(request)
    pags = datos.config("paginas")
    pags["preguntas-frecuentes"]["texto"] = texto.replace("\r\n", "\n").strip()
    datos.guardar_config("paginas", pags)
    return RedirectResponse("/admin/paginas?guardado=1", status_code=303)


@app.get("/admin/api")
def p_api_antes():
    return RedirectResponse("/admin/configuracion/api", status_code=301)


@app.get("/admin/configuracion/api", response_class=HTMLResponse)
def p_api(request: Request):
    """Credenciales de la cuenta: la vía tipo Jumpseller (acceso total, sin alcances)."""
    panel(request)
    login, token = accesos.credenciales_cuenta()
    return phtml(request, "panel_api.html", "configuracion", sub="api", login=login, token=token,
                 base=str(request.base_url).rstrip("/"), mcp=bool(mcp_app), regenerado=request.query_params.get("regenerado"))


@app.post("/admin/configuracion/api/regenerar")
def p_api_regenerar(request: Request):
    panel(request)
    accesos.regenerar_token_cuenta()
    return RedirectResponse("/admin/configuracion/api?regenerado=1", status_code=303)


# ── Apps: instaladas, instalar (consentimiento) y desinstalar ──
@app.get("/admin/configuracion/apps", response_class=HTMLResponse)
def p_apps(request: Request):
    panel(request)
    return phtml(request, "panel_apps.html", "configuracion", sub="apps", apps=accesos.apps(),
                 desinstalada=request.query_params.get("desinstalada"), instalada=request.query_params.get("instalada"))


@app.get("/admin/apps/instalar/{client_id}", response_class=HTMLResponse)
def p_instalar(request: Request, client_id: str):
    panel(request)
    a = accesos.app(client_id)
    if not a:
        raise HTTPException(404)
    ver, cambiar = accesos.consentimiento(a["alcances"])
    return phtml(request, "panel_instalar.html", "configuracion", a=a, ver=ver, cambiar=cambiar)


@app.post("/admin/apps/instalar/{client_id}")
def p_instalar_ok(request: Request, client_id: str):
    panel(request)
    if not accesos.app(client_id):
        raise HTTPException(404)
    accesos.instalar(client_id)
    return RedirectResponse("/admin/configuracion/apps?instalada=1", status_code=303)


@app.post("/admin/apps/desinstalar/{client_id}")
def p_desinstalar(request: Request, client_id: str):
    panel(request)
    accesos.desinstalar(client_id)
    return RedirectResponse("/admin/configuracion/apps?desinstalada=1", status_code=303)


# ── Portal de desarrolladores (como el Dev Dashboard de Shopify) ──
def dhtml(request, plantilla, status=200, **kw):
    return plantillas.TemplateResponse(request, plantilla, {"request": request, "tienda": datos.config("tienda"),
                                                           "alcances_por_recurso": accesos.RECURSOS, **kw}, status_code=status)


@app.get("/desarrolladores", response_class=HTMLResponse)
def d_inicio(request: Request):
    panel(request)
    return dhtml(request, "dev_apps.html", apps=accesos.apps())


@app.get("/desarrolladores/apps/nueva", response_class=HTMLResponse)
def d_nueva(request: Request):
    panel(request)
    return dhtml(request, "dev_nueva.html", error=None)


@app.post("/desarrolladores/apps/nueva")
async def d_nueva_crear(request: Request):
    panel(request)
    form = await request.form()
    alcances = [k for k in form.keys() if k in accesos.ALCANCES]
    if not str(form.get("nombre", "")).strip():
        return dhtml(request, "dev_nueva.html", status=400, error="Ponle un nombre a la app.")
    cid = accesos.crear_app(str(form["nombre"]), alcances)
    return RedirectResponse(f"/desarrolladores/apps/{cid}?lanzada=1", status_code=303)


@app.get("/desarrolladores/apps/{client_id}", response_class=HTMLResponse)
def d_app(request: Request, client_id: str):
    panel(request)
    a = accesos.app(client_id)
    if not a:
        raise HTTPException(404)
    return dhtml(request, "dev_app.html", a=a, base=str(request.base_url).rstrip("/"), q=request.query_params)


@app.post("/desarrolladores/apps/{client_id}/version")
async def d_version(request: Request, client_id: str):
    panel(request)
    form = await request.form()
    accesos.lanzar_version(client_id, [k for k in form.keys() if k in accesos.ALCANCES])
    return RedirectResponse(f"/desarrolladores/apps/{client_id}?version=1", status_code=303)


@app.post("/desarrolladores/apps/{client_id}/rotar")
def d_rotar(request: Request, client_id: str):
    panel(request)
    accesos.rotar_secreto(client_id)
    return RedirectResponse(f"/desarrolladores/apps/{client_id}?rotado=1", status_code=303)


@app.post("/desarrolladores/apps/{client_id}/eliminar")
def d_eliminar(request: Request, client_id: str):
    panel(request)
    accesos.eliminar_app(client_id)
    return RedirectResponse("/desarrolladores?eliminada=1", status_code=303)


@app.get("/admin/exportar/{que}.csv")
def p_exportar(request: Request, que: str):
    panel(request)
    if que not in ("productos", "pedidos"):
        raise HTTPException(404)
    texto = datos.exportar_productos() if que == "productos" else datos.exportar_pedidos()
    return Response(texto.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="export-{que}-web.csv"'})


@app.get("/salud", include_in_schema=False)
def salud():
    return {"ok": True}


@app.exception_handler(404)
def no_encontrado(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": getattr(exc, "detail", "No encontrado")}, status_code=404)
    return html(request, "404.html", status=404)


# ─────────────────────────── /mcp: credenciales y ruta sin barra final ───────────────────────────
class _PuertaMcp:
    """El MCP pide las mismas credenciales que la API, y `/mcp` equivale a `/mcp/`."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").rstrip("/") == "/mcp":
            if scope["path"] == "/mcp":
                scope = dict(scope, path="/mcp/", raw_path=b"/mcp/")
            h = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            acceso, error = api.resolver_acceso(h)
            if error:
                cuerpo = json.dumps({"detail": error}, ensure_ascii=False).encode()
                await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": cuerpo})
                return
            mcp_mostrador.BASE["url"] = f"{h.get('x-forwarded-proto', scope.get('scheme', 'http'))}://{h.get('host', '')}"
            ficha = api.ACCESO.set(acceso)
            try:
                await self.app(scope, receive, send)
            finally:
                api.ACCESO.reset(ficha)
            return
        await self.app(scope, receive, send)


app = _PuertaMcp(app)  # type: ignore[assignment]
