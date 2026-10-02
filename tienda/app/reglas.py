"""Las reglas que aplica la plataforma con la configuración que la tienda cargó en el panel.

Recién creada la base, la configuración es la versión «web» del 29-sep (con sus errores sembrados):
- A4: la fecha estimada son N días hábiles desde la compra, sin considerar los días de despacho ni el courier.
- B10: la web dice «a todo Chile», pero el checkout solo ofrece las comunas configuradas.
- C5: BIENVENIDA10 vale en la primera compra; CAMI15 venció el 31 de agosto.
Lo que se corrija en el panel (Preparar del curso) cambia estas reglas sin tocar el código. El estado «después»
(app/despues.py) las corrige todas de una vez: la fecha estimada se cuenta desde el próximo retiro del courier.
"""
import datetime as dt

from . import datos
from .datos import caso

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Santiago")
except Exception:          # Windows sin tzdata: Chile continental está en UTC-3 en primavera
    _TZ = dt.timezone(dt.timedelta(hours=-3))


def ahora():
    return dt.datetime.now(_TZ).replace(tzinfo=None)


def pesos(n):
    return "$" + f"{int(n):,}".replace(",", ".")


def envios():
    return datos.config("envios")


def comunas():
    return list(envios()["comunas"])


def zona(comuna):
    return envios()["comunas"].get(comuna)


def costo_despacho(comuna, neto):
    e = envios()
    z = e["comunas"].get(comuna)
    if z is None:
        return None
    return 0 if neto >= e["gratis_desde"] else e["zonas"][z]["costo"]


def fecha_estimada(comuna, desde=None):
    e = envios()
    z = e["comunas"].get(comuna)
    if z is None:
        return None
    inicio = (desde or ahora()).date()
    if e.get("cuenta_desde") == "retiro":          # el «después» (A4): desde el próximo retiro del courier
        from .despues import proximo_retiro
        inicio = proximo_retiro(inicio)
    return caso.sumar_habiles(inicio, e["zonas"][z]["dias_habiles"])


def fecha_larga(d):
    return caso.fecha_larga(d) if d else ""


def validar_codigo(codigo, email, subtotal):
    """Devuelve (descuento, mensaje). descuento 0 si el código no aplica."""
    c = (codigo or "").strip().upper()
    if not c:
        return 0, ""
    d = next((x for x in datos.config("descuentos") if x["codigo"].upper() == c), None)
    if not d or not d.get("activo", True):
        return 0, f"El código {c} no existe. Revisa que esté bien escrito."
    if d.get("vence") and ahora().date() > dt.date.fromisoformat(d["vence"]):
        v = dt.date.fromisoformat(d["vence"])
        return 0, f"El código {c} venció el {v.day} de {caso.MESES[v.month - 1]}."
    if d.get("solo_primera_compra") and email and datos.pedidos_de_email(email) > 0:
        return 0, f"{c} es solo para tu primera compra, y este correo ya tiene pedidos."
    return round(subtotal * d["porcentaje"] / 100), f"{c} aplicado: {d['porcentaje']}% de descuento."


COLORES = {  # muestra de color para la ficha (presentación, no dato del negocio)
    "blanco": "#F7F7F5", "negro": "#1D1D1F", "gris melange": "#A9ABAE", "verde oliva": "#5F6B3C", "arena": "#D6C4A3",
    "azul": "#2F5DA8", "gris": "#8A8D91", "burdeo": "#6B1E2C", "crudo": "#EDE6D6", "verde": "#3F7A4E", "celeste": "#A9CBE8",
    "azul medio": "#4A6E9C", "azul oscuro": "#22324F", "azul claro": "#8FB0D4", "verde militar": "#4B5133", "beige": "#D9C7A7",
    "camel": "#B98A55", "amarillo": "#F2C230", "mostaza": "#C9951E", "café": "#6A4630", "azul marino": "#1C2740",
    "surtido": "conic-gradient(#6B1E2C 0 33%, #C9951E 0 66%, #1C2740 0)",
    "azul marino con blanco": "repeating-linear-gradient(0deg, #1C2740 0 4px, #F7F7F5 4px 8px)",
    "rojo con blanco": "repeating-linear-gradient(0deg, #B3262E 0 4px, #F7F7F5 4px 8px)",
    "cuadrillé rojo": "repeating-linear-gradient(0deg, rgba(25,25,25,.45) 0 3px, transparent 3px 8px), #B3262E",
    "cuadrillé verde": "repeating-linear-gradient(0deg, rgba(25,25,25,.45) 0 3px, transparent 3px 8px), #3F6B45",
    "floral azul": "radial-gradient(circle at 30% 30%, #F7F7F5 0 2px, transparent 3px), #2F5DA8",
    "floral terracota": "radial-gradient(circle at 30% 30%, #F7F7F5 0 2px, transparent 3px), #B5603C",
}


def muestra(color):
    return COLORES.get(color, "#CCCCCC")
