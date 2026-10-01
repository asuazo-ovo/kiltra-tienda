"""Los documentos del caso que no son chats: textos, planillas y exportaciones de la web.

Todos los valores de políticas salen de caso.POLITICAS y las cifras de caso.PEDIDOS y del stock: si cambia el
origen, cambian todos los archivos a la vez.
"""
import csv
import datetime as dt
import os

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

import caso
import exportes
from caso import POLITICAS as F, fecha_larga, fecha_corta

pesos = lambda n: f"${n:,}".replace(",", ".")


def _escribir(ruta, texto):
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto.strip() + "\n")


# ─────────────────────────── Textos públicos (web e Instagram) ───────────────────────────
def preguntas_frecuentes():
    g = caso.GUIA_TALLAS["web"]
    return f"""
KILTRA · ropa sin pedigrí, con mucha calle
Preguntas frecuentes — kiltra.cl/preguntas-frecuentes
(texto copiado de la página el {fecha_corta(caso.HOY)})

¿CUÁNTO SE DEMORA MI PEDIDO?
Despachamos a todo Chile con {caso.COURIER}. En la Región Metropolitana tu pedido llega en {F['plazo_prometido']['RM']}
y a regiones en {F['plazo_prometido']['Regiones']}. Al confirmar tu compra te mostramos la fecha estimada de llegada.

¿CUÁNTO CUESTA EL DESPACHO?
{pesos(F['costo_despacho']['RM'])} en la Región Metropolitana y {pesos(F['costo_despacho']['Regiones'])} a regiones.
¡Despacho GRATIS en compras desde {pesos(F['despacho_gratis']['web'])}!

¿PUEDO CAMBIAR MI PRENDA?
Sí. Tienes {F['cambios_dias']['web']} días desde que recibes tu pedido para cambiarla por otra talla, color o
producto. La prenda tiene que estar sin uso y con su etiqueta. Escríbenos por WhatsApp para coordinar.

¿PUEDO DEVOLVER MI COMPRA?
{F['devoluciones']['web']}

¿CÓMO SÉ MI TALLA?
Revisa nuestra guía de tallas. Medimos el contorno de pecho:
XS {g['pecho']['XS']} cm · S {g['pecho']['S']} cm · M {g['pecho']['M']} cm · L {g['pecho']['L']} cm · XL {g['pecho']['XL']} cm
En jeans y pantalones, la talla corresponde a la cintura:
{' · '.join(f"{t} = {c} cm" for t, c in g['cintura'].items())}

¿CÓMO PUEDO PAGAR?
Con Webpay (crédito o débito) o por transferencia. Si pagas por transferencia, tu pedido se confirma cuando
recibimos el pago. Te enviamos la boleta electrónica a tu correo.

¿TIENEN TIENDA FÍSICA?
{F['showroom']['web']} Escríbenos por WhatsApp antes de venir.

¿TIENEN DESCUENTOS?
Usa el código BIENVENIDA10 y obtén un 10% de descuento en tu primera compra. Los descuentos no son acumulables.

¿QUÉ ES UNA PREVENTA?
Algunas prendas se venden antes de llegar a bodega. En la ficha del producto verás la fecha de llegada.

¿CÓMO LOS CONTACTO?
Por WhatsApp o por mensaje directo en Instagram (@kiltra.cl). Atendemos de {F['horario']['web']}.
"""


def destacados_instagram():
    return f"""
INSTAGRAM @kiltra.cl — biografía y destacados
(textos copiados el {fecha_corta(caso.HOY)}; entre paréntesis, cuándo se publicó cada destacado)

BIOGRAFÍA
Kiltra 🐾 ropa sin pedigrí, con mucha calle
Hecho en Ñuñoa · Envíos a todo Chile 🚚
{F['horario']['instagram']} · Compra en kiltra.cl

DESTACADO «ENVÍOS» (marzo 2024)
🚚 Llegamos a todo Chile en 2 a 3 días hábiles
📦 Despachos de lunes a sábado

DESTACADO «ENVÍOS» — segunda historia (junio 2026)
❄️ PROMO INVIERNO ❄️
Despacho GRATIS en compras desde {pesos(F['despacho_gratis']['instagram'])}

DESTACADO «CAMBIOS» (marzo 2024)
💛 Tienes {F['cambios_dias']['instagram']} días para cambiar tu prenda
🏷️ Sin uso y con etiqueta
{F['devoluciones']['instagram']}

DESTACADO «TALLAS» (marzo 2024)
Guía de tallas (contorno de pecho)
{' · '.join(f"{t} {c}" for t, c in caso.GUIA_TALLAS['proveedor']['pecho'].items())}
Jeans (cintura): {' · '.join(f"{t} = {c} cm" for t, c in caso.GUIA_TALLAS['proveedor']['cintura'].items())}

DESTACADO «PROMOS» (agosto 2026)
🔥 {F['promo_ig']} 🔥
✨ Código CAMI15: 15% off con @cami.viste ✨

DESTACADO «SHOWROOM» (2023)
📍 Visítanos en nuestro showroom de Ñuñoa
De lunes a sábado · Te esperamos con café ☕

PUBLICACIÓN FIJADA (15 de septiembre de 2026)
🇨🇱 ¡Felices Fiestas Patrias! 🇨🇱 Nos vemos el sábado 19 en la Feria de Diseño de Providencia 🐾
Y la web sigue abierta todo el fin de semana largo 💻
"""


def guias_tallas():
    out = {}
    for fuente, titulo in (("web", "Guía de tallas publicada en kiltra.cl"),
                           ("proveedor", "Guía de tallas del proveedor (Textiles del Sur, ficha técnica 2024)")):
        g = caso.GUIA_TALLAS[fuente]
        out[fuente] = f"""
{titulo.upper()}

PARTES DE ARRIBA (poleras, polerones, camisas, chaquetas, vestidos)
Contorno de pecho, en centímetros
{chr(10).join(f"  {t:<3} {c}" for t, c in g['pecho'].items())}

PANTALONES Y JEANS
Contorno de cintura, en centímetros
{chr(10).join(f"  {t:<3} {c}" for t, c in g['cintura'].items())}
"""
    out["web"] += "\nSi estás entre dos tallas, te recomendamos la más grande.\n"
    out["proveedor"] += "\nMedidas de la prenda en plano, tolerancia ± 2 cm. Uso interno del taller.\n"
    return out


def correo_courier():
    p = F["plazo_courier"]
    return f"""
De: Ejecutiva de cuentas pymes <pymes@courierandes.example>
Para: Rocío Valdés <hola@kiltra.example>
Fecha: jueves 10 de septiembre de 2026, 16:42
Asunto: Plazos de entrega, feriados de septiembre y aviso de seguridad

Hola Rocío:

Te escribo para recordarte las condiciones de tu contrato y algunos avisos de septiembre.

1. PLAZOS DE ENTREGA. Se cuentan en días hábiles desde que retiramos el paquete en tu taller:
   - Región Metropolitana: {p['RM'][0]} a {p['RM'][1]} días hábiles.
   - Regiones: {p['Regiones'][0]} a {p['Regiones'][1]} días hábiles.
   - Zonas extremas (Punta Arenas, Coyhaique y similares): {p['Extremo'][0]} a {p['Extremo'][1]} días hábiles.
   Los plazos no corren en feriados ni fines de semana.

2. RETIROS. Seguimos retirando los lunes, miércoles y viernes. Por Fiestas Patrias no habrá retiros el
   viernes 18 ni el sábado 19 de septiembre: los envíos de esos días salen el lunes 21. Esa semana los
   centros de distribución de regiones van a tener más carga de lo normal.

3. COBERTURA. Llegamos a todo Chile continental. Isla de Pascua y Puerto Williams se cotizan aparte
   (van por avión y el costo depende del peso). No hacemos envíos internacionales.

4. RECLAMOS. Si un cliente dice que no recibió un paquete marcado como entregado, tienes 5 días hábiles
   desde la fecha de entrega para abrir un reclamo en el formulario de la plataforma, con el número de
   seguimiento. Sin el reclamo dentro de ese plazo no podemos investigar.

5. AVISO DE SEGURIDAD. Están circulando SMS falsos a nombre de {caso.COURIER} que piden pagar «aduana» o
   «reprogramación» en un enlace. Nosotros nunca cobramos por SMS ni por enlaces. Te pedimos que se lo
   cuentes a tus clientes.

Saludos,
Ejecutiva de cuentas pymes
{caso.COURIER} (empresa ficticia)
"""


# ─────────────────────────── Entrevistas de levantamiento ───────────────────────────
def entrevistas(lb):
    n_ped = len(caso.PEDIDOS)
    feria_total = sum(caso.FERIA_PERDIDA.values()) + sum(caso.FERIA_BURDEO.values())
    rocio = f"""
NOTAS DE ENTREVISTA — Rocío Valdés, dueña de Kiltra
Martes 29 de septiembre de 2026, 10:00 a 10:50, en el taller de Ñuñoa
(notas de levantamiento; entre comillas, frases textuales)

LA TIENDA
- Fundó Kiltra en 2021. Vende por la web, por Instagram y en la feria de diseño de Providencia, una vez al mes.
- En septiembre, hasta el lunes 28, la web lleva {n_ped} pedidos. «Septiembre es bueno por el 18, pero octubre y noviembre son peores, por el Cyber y la Navidad.»
- El WhatsApp es el WhatsApp Business de su celular personal, el mismo número desde 2021. «Todas mis clientas tienen ese número. No lo voy a cambiar.»

CÓMO SE ATIENDE HOY
- Cata responde de lunes a viernes de 14:00 a 18:00 desde el computador, con WhatsApp Web, en la misma cuenta.
- El resto lo responde ella: temprano, a la hora de almuerzo y en la noche. «Contesto en la cama, a las once, doce de la noche.»
- Cata firma cuando se presenta; Rocío no. Desde afuera no se sabe quién respondió.
- Le escriben muchos audios. «Los escucho cuando puedo. Cata no puede en la oficina.»
- El fin de semana largo del 18 no miró el teléfono: «Estaba en la feria y después con mi familia. El lunes tenía una montaña de mensajes.»

LAS REGLAS QUE APLICA Y QUE NO ESTÁN ESCRITAS
- Cambios: «Son 30 días, lo que dice la web. Pero a las clientas de siempre se los acepto hasta dos meses.» No hay una lista de quiénes son.
- Devoluciones: dice que sí las acepta «si la clienta insiste». No sabía que el destacado de Instagram dice «solo cambios». Supo del reclamo en el SERNAC el 22.
- Tallas: «El mom fit viene chico, siempre les digo que pidan una más. El oversize es grande.» Eso no está en la web.
- Reservas: «Si una clienta me pide que le guarde algo, se lo guardo.» No las anota: las recuerda.
- Ventas por fuera de la web: vende por mensaje de Instagram y por WhatsApp a quien no puede usar la página. Lo anota en un cuaderno y le avisa a Nicolás «cuando se acuerda».
- Factura: la web emite solo boleta. Cuando una empresa pide factura, la hace a mano en el sitio del SII.
- Descuentos: los decide ella. No sabía que Cata había ofrecido un 10% a una clienta.
- Canjes con influencers: «Los veo yo por Instagram, pero casi nunca tengo tiempo.»
- Pedidos corporativos: «Me han pedido polerones con logo, pero no sé si me conviene. Nunca lo he calculado.»

LO QUE LE PREOCUPA
- «No puedo seguir respondiendo yo todo.»
- «No quiero que mis clientas sientan que hablan con un robot. Kiltra es cercana.»
- «Cata es buenísima, pero nadie le explicó nada. Aprende preguntándome.»
"""
    nicolas = f"""
NOTAS DE ENTREVISTA — Nicolás Ibarra, socio, bodega y despachos
Martes 29 de septiembre de 2026, 11:00 a 11:35, en el taller de Ñuñoa

EL STOCK
- Lleva la planilla de stock (stock-kiltra.xlsx). La actualiza los lunes: resta lo que vendió la web en la semana y lo que le anotan de la feria y de Instagram.
- La web descuenta sola lo que vende, pero el stock de la web lo carga él a mano desde la planilla, los lunes. «Si algo se vende por otro lado entre lunes y lunes, la web no se entera.»
- La hoja de ventas de la feria del 19 se perdió. «Rocío dice que la dejó en la bolsa. Nunca apareció.» En la feria se vendieron unas {feria_total} prendas, entre ellas todos los polerones canguro burdeo que quedaban.
- El lunes 21 restó las ventas de la web, pero no las de la feria. Ese fin de semana la web vendió 6 polerones burdeo que ya no existían.
- El lunes 28 no alcanzó a actualizar. Hoy en la mañana hizo un conteo físico completo (conteo-fisico-29-septiembre.xlsx).
- La blusa floral terracota la dejó en cero en la web «porque el lote vino con falla», pero en la planilla sigue con stock.
- La parka verde oliva está en preventa en la web y llega el {fecha_corta(caso.PREVENTA_LLEGA)}. «Eso me lo dijo el proveedor por correo.»

LOS DESPACHOS
- Despacha lunes, miércoles y viernes, que es cuando retira el courier. Lo que se compra después del retiro sale en el siguiente.
- La web promete {F['plazo_prometido']['RM']} en Santiago desde la compra. «Eso lo puso Rocío cuando abrimos. Con los días de despacho no da.»
- Los reclamos al courier los hace él, «cuando me llega el aviso». El de Javiera (entregado y no recibido) todavía no lo abre.
- No sabe si se puede enviar a Isla de Pascua: «Nunca nos han pedido.»

LO QUE PIDE
- «Que alguien me diga en el momento cuando se vende algo por fuera.»
- «Una sola planilla. Ahora hay tres: la mía, la de la web y el cuaderno de Rocío.»
"""
    cata = f"""
NOTAS DE ENTREVISTA — Catalina Reyes («Cata»), atención a clientes part-time
Martes 29 de septiembre de 2026, 14:10 a 14:40, por videollamada

SU TRABAJO
- Entró en julio. Trabaja de lunes a viernes de 14:00 a 18:00, desde su casa, con WhatsApp Web en la cuenta de Kiltra.
- No tuvo inducción. «El primer día Rocío me mostró los destacados de Instagram y me dijo que ahí estaba todo.»
- Para el stock mira la web. Para los pedidos tiene acceso al panel de pedidos de la web, sin poder editar.
- No tiene acceso a la planilla de Nicolás ni al cuaderno de Rocío.

LO QUE MÁS LE PREGUNTAN (según ella)
- «Tallas, por lejos. Y si hay stock, y dónde está mi pedido.»
- «Lo que más me cuesta son los reclamos: no sé qué puedo prometer.»

LO QUE NO SABE Y CÓMO LO RESUELVE
- Plazo de cambio: «Yo decía 15 días, porque es lo que dice el Instagram. Después supe que la web dice 30.»
- Devoluciones: «Le dije a una clienta que no hacíamos, por el destacado. Después vino lo del SERNAC.»
- Garantía: no sabía que existía. «Pensé que un polerón de julio ya no tenía cambio.»
- Descuentos: «Una vez ofrecí un 10% para no perder una venta. Rocío me dijo que no lo hiciera más.»
- Cuando no sabe algo, responde «déjame consultarlo» y le pregunta a Rocío por el grupo. «A veces Rocío me responde en la noche y ya me desconecté. Al otro día se me olvida.»
- Lleva una planilla de reclamos (reclamos-2026.xlsx) «cuando me acuerdo».

LO QUE LE PREOCUPA
- «Leí que hay bots para WhatsApp. ¿Me van a reemplazar?»
- «Me gustaría tener un documento con las respuestas. Siempre pregunto lo mismo.»
"""
    return {"rocio": rocio, "nicolas": nicolas, "cata": cata}


# ─────────────────────────── El grupo del equipo ───────────────────────────
def grupo_equipo(lb):
    P = caso.CLAVE_PEDIDO
    R, N, K = "Rocío", "Nico", "Cata"
    ig = "; ".join(f"{q} {caso.PROD[v[0]]['nombre'].lower()} {v[1]}" for v, q in caso.VENTAS_IG.items())
    msgs = [
        (dt.datetime(2026, 9, 14, 9, 2), N, "Planilla actualizada ✅ La web ya tiene el stock de hoy"),
        (dt.datetime(2026, 9, 15, 15, 30), K, "Rocío, una clienta quiere devolver un vestido. Le dije que solo cambios, como dice el insta. Está bien?"),
        (dt.datetime(2026, 9, 15, 22, 48), R, "Sí, pero si insiste mucho avísame"),
        (dt.datetime(2026, 9, 16, 14, 20), K, "Me escribió una empresa que quiere 40 polerones con logo. Les respondo algo?"),
        (dt.datetime(2026, 9, 16, 15, 41), K, "Y otra clienta dice que le prometí despacho gratis sobre 39.990 y le cobraron 😬"),
        (dt.datetime(2026, 9, 17, 13, 20), R, "La señora Gladys me compró por chat el chaleco crudo L y la bufanda gris. Lo anoté en el cuaderno. Nico, despáchalo el lunes"),
        (dt.datetime(2026, 9, 17, 13, 22), N, "👍"),
        (dt.datetime(2026, 9, 19, 18, 40), R, "VENDIMOS TODO EL POLERÓN BURDEO EN LA FERIA 🔥🔥🔥"),
        (dt.datetime(2026, 9, 19, 18, 41), N, "Anotaste todo en la hoja?"),
        (dt.datetime(2026, 9, 19, 18, 45), R, "Sí, está en la bolsa de los cambios"),
        (dt.datetime(2026, 9, 21, 7, 55), R, f"Chiquillos tengo {lb['finde_largo_sin_respuesta_hasta_lunes']} mensajes sin responder del fin de semana 😭 no alcancé a mirar nada"),
        (dt.datetime(2026, 9, 21, 7, 56), R, "No puedo seguir respondiendo yo todo"),
        (dt.datetime(2026, 9, 21, 9, 30), N, "Rocío no encuentro la hoja de la feria. Actualicé la planilla solo con la web"),
        (dt.datetime(2026, 9, 21, 9, 34), N, f"Y hay 6 pedidos de polerón burdeo del fin de semana. No queda ninguno 😳 ({', '.join(P[f'burdeo{i}']['numero'] for i in range(1, 7))})"),
        (dt.datetime(2026, 9, 21, 9, 36), R, "Cómo que la web los siguió vendiendo???"),
        (dt.datetime(2026, 9, 21, 9, 37), N, "Porque la web tenía el stock del lunes pasado. No sabía lo de la feria"),
        (dt.datetime(2026, 9, 21, 9, 40), R, "Ya, yo les escribo a las clientas. Ofrezco gris o devolución"),
        (dt.datetime(2026, 9, 22, 11, 15), R, "Nos llegó un reclamo del SERNAC 😭 de la clienta del vestido camisero"),
        (dt.datetime(2026, 9, 22, 14, 5), K, "Fui yo la que le dijo lo del insta. Perdón 😔"),
        (dt.datetime(2026, 9, 22, 14, 30), R, "No es tu culpa, nadie te explicó. Los destacados están viejos. Le voy a escribir a Trama"),
        (dt.datetime(2026, 9, 22, 15, 20), K, "Otra pregunta: el plazo de cambio son 15 o 30 días? Una clienta dice que la web dice 30"),
        (dt.datetime(2026, 9, 22, 21, 50), R, "30! El insta está malo"),
        (dt.datetime(2026, 9, 23, 10, 10), N, "La parka negra M que estaba apartada, para quién era? Se vendió por la web"),
        (dt.datetime(2026, 9, 23, 22, 30), R, "Uyy era de la Paulina 🙈"),
        (dt.datetime(2026, 9, 24, 13, 5), R, f"Vendí por insta: {ig}. Descuéntalos Nico"),
        (dt.datetime(2026, 9, 24, 15, 0), K, "Me preguntaron si el SMS del courier para pagar aduana es nuestro. Qué le digo?"),
        (dt.datetime(2026, 9, 17, 14, 40), K, "Una empresa pide factura por 6 polerones. Podemos?"),
        (dt.datetime(2026, 9, 17, 21, 55), R, "La factura la hago yo a mano, le escribo yo"),
        (dt.datetime(2026, 9, 24, 22, 15), R, "Lo del SMS no sé, pregúntale a Nico"),
        (dt.datetime(2026, 9, 25, 15, 10), K, "Leí que hay bots para WhatsApp que responden solos... me van a reemplazar? 😅"),
        (dt.datetime(2026, 9, 25, 22, 40), R, "Jajaja nooo. Pero algo tenemos que hacer, esto no da"),
        (dt.datetime(2026, 9, 26, 11, 0), N, "Y si sacamos un número de empresa para el WhatsApp?"),
        (dt.datetime(2026, 9, 26, 21, 5), R, "Noo, todas las clientas tienen este número"),
        (dt.datetime(2026, 9, 28, 8, 30), N, "Hoy no alcanzo a actualizar la planilla, tengo 9 despachos"),
        (dt.datetime(2026, 9, 28, 22, 10), R, "Mañana hagamos un conteo de todo y me siento con ustedes a ordenar esto. Ya no da más"),
    ]
    msgs.sort(key=lambda m: m[0])
    lineas = [f"{msgs[0][0].day}/{msgs[0][0].month}/26, {msgs[0][0].strftime('%H:%M')} - Los mensajes y las llamadas están cifrados de extremo a extremo. Solo las personas en este chat pueden leerlos, escucharlos o compartirlos."]
    for t, quien, tx in msgs:
        lineas.append(f"{t.day}/{t.month}/26, {t.strftime('%H:%M')} - {quien}: {tx}")
    return "\n".join(lineas)


# ─────────────────────────── Planillas y exportaciones ───────────────────────────
NEGRITA = Font(bold=True)
AMARILLO = PatternFill("solid", fgColor="FFF2CC")


def _filas_stock(stock, notas=None):
    filas = []
    for sku, nombre, cat, precio, colores, tallas in caso.PRODUCTOS:
        for c in colores:
            filas.append([sku, nombre, c] + [stock[(sku, c, t)] for t in tallas] + [(notas or {}).get((sku, c), "")])
    return filas


def _libro_stock(ruta, titulo, stock, notas, hoja_extra=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "STOCK"
    ws.append([titulo])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([])
    grupos = {}
    for sku, nombre, cat, precio, colores, tallas in caso.PRODUCTOS:
        grupos.setdefault(tuple(tallas), []).append(sku)
    for tallas, skus in grupos.items():
        ws.append(["SKU", "Producto", "Color"] + list(tallas) + ["Notas"])
        for c in ws[ws.max_row]:
            c.font = NEGRITA
        for sku in skus:
            p = caso.PROD[sku]
            for col in p["colores"]:
                nota = notas.get((sku, col), "")
                ws.append([sku, p["nombre"], col] + [stock[(sku, col, t)] for t in tallas] + [nota])
                if nota:
                    for c in ws[ws.max_row]:
                        c.fill = AMARILLO
        ws.append([])
    ws.column_dimensions["B"].width = 36
    ws.column_dimensions["C"].width = 22
    for col in "DEFGHI":
        ws.column_dimensions[col].width = 7
    ws.column_dimensions["J"].width = 40
    if hoja_extra:
        hoja_extra(wb)
    wb.save(ruta)


def planillas(ins):
    notas_pl = {("PLR-001", "burdeo"): "agotado (feria?)", ("CHA-002", "verde oliva"): "PREVENTA, llega nov",
                ("CAM-003", "floral terracota"): "lote con falla, no vender", ("ACC-001", "mostaza"): "ojo, se vende harto por insta"}

    def hoja_feria(wb):
        ws = wb.create_sheet("FERIA 19-SEP")
        ws.append(["Ventas de la feria de diseño del sábado 19"])
        ws["A1"].font = NEGRITA
        ws.append(["(pendiente: Rocío tiene la hoja)"])

    _libro_stock(os.path.join(ins, "stock-kiltra.xlsx"),
                 f"STOCK KILTRA — actualizado lunes {fecha_corta(caso.PLANILLA_ACTUALIZADA)} (Nico)", caso.STOCK_PLANILLA, notas_pl, hoja_feria)
    notas_cf = {("PLR-001", "burdeo"): "no queda ninguno", ("CHA-002", "verde oliva"): "no ha llegado (preventa)",
                ("CAM-003", "floral terracota"): "están en la caja de fallas"}
    _libro_stock(os.path.join(ins, "conteo-fisico-29-septiembre.xlsx"),
                 f"CONTEO FÍSICO — martes {fecha_corta(caso.HOY)}, 8:00 a 9:30 (Nico y Rocío)", caso.STOCK_REAL, notas_cf)


def export_productos(ins):
    with open(os.path.join(ins, "export-productos-web.csv"), "w", encoding="utf-8", newline="") as f:
        f.write(exportes.csv_productos(exportes.variantes_web()))


def export_pedidos(ins):
    with open(os.path.join(ins, "export-pedidos-web.csv"), "w", encoding="utf-8", newline="") as f:
        f.write(exportes.csv_pedidos(exportes.pedidos_web()))


def reclamos(ins):
    P = caso.CLAVE_PEDIDO
    filas = [
        ("05/08", "Carla G.", "", "talla", "ok", "se le cambió"),
        ("12/08", "?", "", "no llegó", "ok", "estaba en conserjería"),
        ("27/08", "Bastián R.", "KT-0951", "cobro doble", "pendiente", "banco?"),
        ("16/09", "Tomás Contreras", caso.PEDIDO_JULIO["numero"], "falla polerón (julio)", "cerrado", "fuera de plazo de cambio"),
        ("16/09", "Bárbara Saavedra", P["gratis39"]["numero"], "despacho cobrado", "pendiente", "yo le dije 39.990 😬"),
        ("20/09", "Valentina Soto", P["retracto"]["numero"], "SERNAC — devolución", "", "llegó carta el 22"),
        ("21/09", "6 clientas burdeo", "varios", "sin stock", "en curso", "Rocío les escribe"),
        ("22/09", "Javiera Silva", P["no_recibido"]["numero"], "dice entregado, no llegó", "pendiente", "Nico tiene que reclamar al courier"),
        ("23/09", "Ignacio", "", "pago rechazado y cobrado", "", ""),
        ("24/09", "Fernanda Díaz", P["atrasado"]["numero"], "atraso Temuco", "pendiente", "amenaza SERNAC (28/09)"),
        ("25/09", "Paulina C.", "", "reserva vendida", "", "Rocío"),
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "Reclamos"
    ws.append(["Fecha", "Cliente", "Pedido", "Motivo", "Estado", "Comentario"])
    for c in ws[1]:
        c.font = NEGRITA
    for fila in filas:
        ws.append(list(fila))
    for col, ancho in zip("ABCDEF", (8, 20, 10, 28, 11, 38)):
        ws.column_dimensions[col].width = ancho
    wb.save(os.path.join(ins, "reclamos-2026.xlsx"))


def generar(ins, lb):
    _escribir(os.path.join(ins, "preguntas-frecuentes-web.txt"), preguntas_frecuentes())
    _escribir(os.path.join(ins, "destacados-instagram.txt"), destacados_instagram())
    g = guias_tallas()
    _escribir(os.path.join(ins, "guia-tallas-web.txt"), g["web"])
    _escribir(os.path.join(ins, "guia-tallas-proveedor.txt"), g["proveedor"])
    _escribir(os.path.join(ins, "correo-courier-andes.txt"), correo_courier())
    for k, tx in entrevistas(lb).items():
        _escribir(os.path.join(ins, f"entrevista-{k}.txt"), tx)
    _escribir(os.path.join(ins, "grupo-equipo-kiltra.txt"), grupo_equipo(lb))
    planillas(ins)
    export_productos(ins)
    export_pedidos(ins)
    reclamos(ins)
