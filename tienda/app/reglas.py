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


# Feriados de Chile que cuenta la tienda para sus fechas de hoy en adelante. Los de septiembre vienen del caso;
# los demás no van en el generador para no mover las fechas del «antes» (los insumos quedan idénticos).
FERIADOS = {**caso.FERIADOS,
            dt.date(2026, 10, 12): "Encuentro de Dos Mundos", dt.date(2026, 10, 31): "Día de las Iglesias Evangélicas",
            dt.date(2026, 11, 1): "Todos los Santos", dt.date(2026, 12, 8): "Inmaculada Concepción",
            dt.date(2026, 12, 25): "Navidad", dt.date(2027, 1, 1): "Año Nuevo"}


def habil(d):
    return d.weekday() < 5 and d not in FERIADOS


def sumar_habiles(d, n):
    while n > 0:
        d += dt.timedelta(days=1)
        if habil(d):
            n -= 1
    return d


def proximo_retiro(d):
    """El primer día de retiro del courier (lunes, miércoles o viernes hábil) estrictamente después de d."""
    from .despues import RETIROS
    d += dt.timedelta(days=1)
    while d.weekday() not in RETIROS or not habil(d):
        d += dt.timedelta(days=1)
    return d


def fecha_estimada(comuna, desde=None):
    e = envios()
    z = e["comunas"].get(comuna)
    if z is None:
        return None
    return estimado_zona(z, desde)["hasta"]


def estimado_zona(z, desde=None):
    """Lo que la tienda promete hoy para una zona: desde qué día cuenta, entre qué fechas llega y la fecha estimada.
    En el «antes» cuenta desde la compra, como la web del 29-sep (A4); en el «después», desde el próximo retiro."""
    e = envios()
    zona_cfg = e["zonas"][z]
    compra = (desde or ahora()).date()
    if e.get("cuenta_desde") == "retiro":
        inicio = proximo_retiro(compra)
        lo = zona_cfg.get("dias_habiles_min", zona_cfg["dias_habiles"])
        return {"compra": compra, "proximo_retiro": inicio, "desde": sumar_habiles(inicio, lo),
                "hasta": sumar_habiles(inicio, zona_cfg["dias_habiles"])}
    hasta = caso.sumar_habiles(compra, zona_cfg["dias_habiles"])
    return {"compra": compra, "proximo_retiro": None, "desde": None, "hasta": hasta}


def estimados_si_compras_hoy(desde=None):
    out = {}
    for z in envios()["zonas"]:
        x = estimado_zona(z, desde)
        txt = (f"Si compras hoy, el courier lo retira el {fecha_larga(x['proximo_retiro'])} y llega entre el "
               f"{fecha_larga(x['desde'])} y el {fecha_larga(x['hasta'])} (fecha estimada: {fecha_larga(x['hasta'])})."
               if x["proximo_retiro"] else f"Fecha estimada de llegada si compras hoy: {fecha_larga(x['hasta'])}.")
        out[z] = {"next_pickup": x["proximo_retiro"].isoformat() if x["proximo_retiro"] else None,
                  "from": x["desde"].isoformat() if x["desde"] else None, "to": x["hasta"].isoformat(), "text": txt}
    return out


def feriados_proximos(desde=None, dias=60):
    hoy = (desde or ahora()).date()
    return [{"date": d.isoformat(), "name": n} for d, n in sorted(FERIADOS.items()) if hoy <= d <= hoy + dt.timedelta(days=dias)]


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
