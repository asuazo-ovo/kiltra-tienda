"""El «después» de Preparar: la tienda con las Políticas de Kiltra v1 aplicadas en el panel.

Fuente: `solucionario/01 - Políticas de Kiltra v1.md` (aprobadas por Agustín el 2-oct-2026). El «antes» es
`datos.config_inicial()`, la foto del 29-sep con sus errores sembrados. Este módulo describe solo lo que cambia
en la configuración, el catálogo y el stock; los pedidos y las apps de desarrollador no se tocan.

Lo que se aplica (fila de la matriz entre paréntesis):
- cambios 30 días; envío del cambio según el motivo (A1, A1b); retracto con reembolso de todo y envío de vuelta
  pagado por Kiltra (A2); garantía de 6 meses (B7);
- plazos desde el próximo retiro del courier, con la nota, y la cobertura real (A4, B10);
- horario de personas, retiro con hora en el taller en vez del showroom (A7, A8);
- CAMI15 inactivo (C5); «100% algodón» en vez de «orgánico» (A6); notas de calce y la guía del proveedor (A5);
- el stock corregido con el conteo físico del 29 (B1); preguntas frecuentes sin «solo cambios» ni showroom, con
  garantía, factura y el aviso de estafa (A2, A8, B7, B9, D4).
"""
import copy
import datetime as dt

from .datos import caso

F = caso.POLITICAS
RETIROS = [0, 2, 4]                    # lunes, miércoles y viernes (date.weekday())
NOMBRES_DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
RETIRO_TALLER = ("Retiro con hora agendada en nuestro taller de Ñuñoa, los sábados de 11:00 a 14:00. Ahí puedes "
                 "probarte la prenda y cambiar la talla en el momento. La hora la confirma el equipo.")
HORARIO = "lunes a viernes de 10:00 a 18:00"
NOTA_RETIRO = ("El courier retira en el taller los lunes, miércoles y viernes. El plazo se cuenta en días hábiles desde "
               "el retiro siguiente a tu compra; los fines de semana y los feriados no cuentan. Antes de cada feriado "
               "largo publicamos la fecha del último retiro.")
NOMBRES = {"POL-001": "Polera básica 100% algodón"}
PREVENTA = {"CHA-002": "Preventa: llega al taller desde el 10 de noviembre y se despacha en el retiro siguiente."}
TEXTO_POLITICA = (
    "Cambios: tienes 30 días desde que recibes tu pedido para cambiar tu prenda por otra talla, color o producto. "
    "La prenda tiene que estar sin uso y con su etiqueta. Si el cambio es por una falla o por un error nuestro "
    "(incluida una talla mal informada en la web), el envío lo pagamos nosotros; en cualquier otro caso lo pagas tú, "
    "con la tarifa de despacho de tu zona. En el retiro del sábado en el taller el cambio no tiene costo.\n\n"
    "Devoluciones (derecho a retracto): tienes 10 días desde que recibes tu pedido para devolverlo, sin dar motivo, "
    "con la prenda sin uso y con su etiqueta. Te reembolsamos todo lo pagado, incluido el despacho, al mismo medio de "
    "pago, a más tardar 5 días hábiles después de que la prenda llega al taller. El envío de vuelta lo pagamos "
    "nosotros, o puedes dejarla en el retiro del sábado.\n\n"
    "Garantía: si una prenda tiene una falla de fabricación, tienes 6 meses desde que la recibes. Tú eliges entre "
    "cambio, reparación o devolución del dinero, y nosotros pagamos los envíos. Escríbenos con una foto de la falla.")


def descripcion(sku):
    """Descripción de la ficha en el «después»: sin «orgánico», con la nota de calce y la de preventa."""
    d = caso.DESCRIPCIONES_WEB.get(sku, "").replace("algodón orgánico", "algodón")
    partes = [d] if d else []
    if sku in caso.NOTAS_CALCE:
        partes.append(caso.NOTAS_CALCE[sku])
    if sku in PREVENTA:
        partes.append(PREVENTA[sku])
    return " ".join(partes)


def preguntas_frecuentes():
    g = caso.GUIA_TALLAS["proveedor"]
    pesos = lambda n: "$" + f"{n:,}".replace(",", ".")
    return f"""
KILTRA · ropa sin pedigrí, con mucha calle
Preguntas frecuentes

¿CUÁNTO SE DEMORA MI PEDIDO?
Despachamos con {caso.COURIER}, que retira en nuestro taller los lunes, miércoles y viernes. Desde ese retiro, tu pedido llega en 2 a 4 días hábiles en la Región Metropolitana, en 3 a 6 a regiones y en 7 a 10 a las zonas extremas.
Los fines de semana y los feriados no cuentan. Al pagar te mostramos la fecha estimada de llegada.

¿CUÁNTO CUESTA EL DESPACHO?
{pesos(F['costo_despacho']['RM'])} en la Región Metropolitana y {pesos(F['costo_despacho']['Regiones'])} a regiones y zonas extremas.
Despacho gratis en compras desde {pesos(F['despacho_gratis']['web'])}.

¿A DÓNDE DESPACHAN?
A todo Chile continental. Isla de Pascua y Puerto Williams se cotizan aparte: escríbenos. Por ahora no despachamos al extranjero.

¿PUEDO CAMBIAR MI PRENDA?
Sí. Tienes 30 días desde que recibes tu pedido para cambiarla por otra talla, color o producto, sin uso y con su etiqueta.
Si el cambio es por una falla o por un error nuestro, el envío lo pagamos nosotros; si no, lo pagas tú con la tarifa de tu zona. En el retiro del sábado el cambio no tiene costo.

¿PUEDO DEVOLVER MI COMPRA?
Sí. Tienes 10 días desde que la recibes para devolverla, sin dar motivo, sin uso y con su etiqueta. Te reembolsamos todo lo pagado, incluido el despacho, al mismo medio de pago. El envío de vuelta lo pagamos nosotros.

¿Y SI MI PRENDA VIENE CON UNA FALLA?
Tienes 6 meses de garantía desde que la recibes. Tú eliges entre cambio, reparación o devolución del dinero, y nosotros pagamos los envíos. Escríbenos con una foto de la falla.

¿CÓMO SÉ MI TALLA?
Revisa nuestra guía de tallas y la nota de calce de cada prenda (por ejemplo, el mom fit viene una talla más chico). Medimos el contorno de pecho:
XS {g['pecho']['XS']} cm · S {g['pecho']['S']} cm · M {g['pecho']['M']} cm · L {g['pecho']['L']} cm · XL {g['pecho']['XL']} cm
En jeans y pantalones, la talla corresponde a la cintura:
{' · '.join(f"{t} = {c} cm" for t, c in g['cintura'].items())}

¿CÓMO PUEDO PAGAR?
Con Webpay (crédito o débito) o por transferencia. Si pagas por transferencia, tu pedido se confirma cuando recibimos el pago, y si no llega en 48 horas el pedido se anula. Te enviamos la boleta electrónica a tu correo.

¿EMITEN FACTURA?
Sí. Escríbenos después de comprar y la emitimos en un plazo de 2 días hábiles.

¿TIENEN TIENDA FÍSICA?
No tenemos showroom. {RETIRO_TALLER}

¿TIENEN DESCUENTOS?
Usa el código BIENVENIDA10 y obtén un 10% de descuento en tu primera compra en la web. Los descuentos no se acumulan entre sí ni con las promociones de Instagram.

¿QUÉ ES UNA PREVENTA?
Algunas prendas se venden antes de llegar al taller. En la ficha verás desde cuándo llegan; las despachamos en el retiro siguiente a esa fecha.

¿ME LLEGÓ UN MENSAJE PARA PAGAR UNA ADUANA, ES DE USTEDES?
No. Kiltra nunca cobra por SMS ni con un link que no sea esta tienda, y {caso.COURIER} no cobra aduana en despachos dentro de Chile. No pagues y bórralo.

¿CÓMO LOS CONTACTO?
Por WhatsApp o por mensaje directo en Instagram (@kiltra.cl). Nuestro asistente responde a toda hora; el equipo atiende de {HORARIO}.
"""


def config(base):
    """La configuración «después», partiendo de una copia de la del «antes» (`datos.config_inicial()`)."""
    c = copy.deepcopy(base)
    c["tienda"].update({"horario": HORARIO, "showroom": RETIRO_TALLER})
    e = c["envios"]
    plazo = {"RM": (2, 4), "Regiones": (3, 6), "Extremo": (7, 10)}
    for z, (lo, hi) in plazo.items():
        e["zonas"][z].update({"dias_habiles": hi, "dias_habiles_min": lo, "texto": f"{lo} a {hi} días hábiles desde el retiro"})
    e.update({"cuenta_desde": "retiro", "dias_de_retiro": [NOMBRES_DIA[d] for d in RETIROS], "nota_retiro": NOTA_RETIRO,
              "cobertura": {"texto": "Todo Chile continental.", "se_cotiza": F["cobertura"]["cotizacion"],
                            "internacional": False}})
    for d in c["descuentos"]:
        if d["codigo"] == "CAMI15":
            d["activo"] = False
    c["paginas"]["preguntas-frecuentes"]["texto"] = preguntas_frecuentes().strip()
    pol = c["politicas"]["cambios-y-devoluciones"]
    pol["texto"] = TEXTO_POLITICA
    pol["reglas"].update({
        "envio_del_cambio": "segun_motivo",
        "envio_del_cambio_detalle": ("Lo paga Kiltra si es por una falla o un error de Kiltra (incluida una talla mal "
                                     "informada en la web); si no, el cliente, con la tarifa de su zona. En el retiro "
                                     "del sábado no tiene costo."),
        "envio_de_la_devolucion": "tienda",
        "reembolso": ("de todo lo pagado, incluido el despacho, al mismo medio de pago, a más tardar 5 días hábiles "
                      "después de que la prenda llega al taller"),
        "garantia_meses": 6,
        "garantia": "falla de fabricación; el cliente elige cambio, reparación o devolución; Kiltra paga los envíos",
        "excepciones": "no hay excepciones publicadas; un cambio fuera de plazo lo decide solo la dueña",
    })
    c["tallas"] = {"fuente": "proveedor", **copy.deepcopy(caso.GUIA_TALLAS["proveedor"])}
    return c


# ─────────────────────────── Pedidos de prueba para la batería ───────────────────────────
# Solo existen en el «después» y solo si la tienda tiene la variable KILTRA_TELEFONO_PRUEBA (el teléfono de
# quien prueba: es un dato personal y vive solo en el entorno de Render, nunca en el repo). Así el agente,
# que solo informa un pedido al teléfono con que se hizo (D1), tiene pedidos propios con que probar cada caso.
# Las fechas son relativas a hoy: se rehacen cada vez que se aplica el «después».
PRUEBA = [  # número, caso de la batería, sku, estado
    ("KT-9001", "B3: atrasado, la fecha estimada venció hace 2 días hábiles", "PLR-001", "despachado"),
    ("KT-9002", "A1/A2: entregado hace 20 días (dentro del cambio, fuera del retracto)", "PAN-002", "entregado"),
    ("KT-9003", "A1/B7: entregado hace 40 días (fuera del cambio, dentro de la garantía)", "PLR-002", "entregado"),
    ("KT-9004", "B5: en preparación (todavía se puede cambiar la dirección)", "CAM-002", "en preparación"),
    ("KT-9005", "A2: entregado hace 5 días (dentro del retracto)", "VES-002", "entregado"),
    ("KT-9006", "B4: el courier lo marca entregado hace 3 días", "CHA-001", "entregado"),
]


def _habiles_atras(d, n):
    while n > 0:
        d -= dt.timedelta(days=1)
        if caso.habil(d):
            n -= 1
    return d


def _habil_antes(d):
    """El día hábil más cercano en o antes de d."""
    while not caso.habil(d):
        d -= dt.timedelta(days=1)
    return d


def proximo_retiro(d):
    """El primer día de retiro (lunes, miércoles o viernes hábil) estrictamente después de d."""
    d += dt.timedelta(days=1)
    while d.weekday() not in RETIROS or not caso.habil(d):
        d += dt.timedelta(days=1)
    return d


def pedidos_de_prueba(telefono, hoy):
    """Seis pedidos con el teléfono de quien prueba, uno por caso de la batería que necesita un pedido propio."""
    prod = {p[0]: p for p in caso.PRODUCTOS}
    iso = lambda d: d.isoformat() if d else ""
    out = []
    for numero, nota, sku, estado in PRUEBA:
        _, nombre, _, precio, colores, tallas = prod[sku]
        color, talla = next(((c, t) for c in colores for t in tallas if caso.STOCK_REAL.get((sku, c, t), 0) > 0),
                            (colores[0], tallas[0]))
        entrega = None
        if numero == "KT-9001":
            estimada = _habiles_atras(hoy, 2)
            despacho = _habiles_atras(estimada, 4)
        elif numero == "KT-9004":
            despacho = None
            estimada = caso.sumar_habiles(proximo_retiro(hoy), 4)
        else:
            dias = {"KT-9002": 20, "KT-9003": 40, "KT-9005": 5, "KT-9006": 3}[numero]
            entrega = _habil_antes(hoy - dt.timedelta(days=dias))
            despacho = _habiles_atras(entrega, 2)
            estimada = caso.sumar_habiles(despacho, 4)
        compra = _habiles_atras(despacho, 1) if despacho else _habiles_atras(hoy, 1)
        envio = 0 if precio >= F["despacho_gratis"]["web"] else F["costo_despacho"]["RM"]
        out.append({
            "numero": numero, "fecha": iso(compra), "hora": "12:00", "cliente": "Cliente de prueba",
            "email": "prueba@kiltra.example", "telefono": telefono, "direccion": "Av. de prueba 123", "comuna": "Providencia",
            "zona": "RM", "subtotal": precio, "codigo": "", "descuento": 0, "despacho": envio, "total": precio + envio,
            "medio_pago": "Webpay crédito", "estado": estado, "courier": caso.COURIER if despacho else "",
            "seguimiento": f"CA-PRUEBA-{numero[3:]}" if despacho else "", "fecha_despacho": iso(despacho),
            "fecha_estimada": iso(estimada), "fecha_entrega": iso(entrega),
            "nota_interna": f"PEDIDO DE PRUEBA para la batería · {nota}", "origen": "prueba",
            "items": [{"sku": sku, "producto": nombre, "color": color, "talla": talla, "cantidad": 1, "precio_unitario": precio}],
        })
    return out
