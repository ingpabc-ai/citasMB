# citasMB.py (actualizado para flujo de revisión manual + propuesta por admin)
import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client as TwilioClient

app = Flask(__name__)

# Diccionario para almacenar estado y datos del usuario
usuarios = {}

# Servicios y subopciones (tu data original)
servicios = {
    "1": {"nombre": "Manicure tradicional", "subopciones": ["Normal", "Francesa", "Nail art"]},
    "2": {"nombre": "Manicure en gel", "subopciones": ["Normal", "Francesa", "Nail art"]},
    "3": {"nombre": "Pedicure", "subopciones": ["Spa", "Normal"]},
    "4": {"nombre": "Paquete completo", "subopciones": ["Manicure + Pedicure", "Manicure + Gel"]}
}

# Twilio REST client (para enviar mensajes proactivos desde el bot)
TW_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TW_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TW_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_NUMBER")  # ejemplo: "whatsapp:+1415..."
tw_client = None
if TW_SID and TW_TOKEN:
    tw_client = TwilioClient(TW_SID, TW_TOKEN)

# Números admin autorizados (opcional)
ADMIN_NUMBERS = [n.strip() for n in (os.environ.get("ADMIN_NUMBERS","").split(",") if os.environ.get("ADMIN_NUMBERS") else []) if n.strip()]

def _es_afirmacion(texto: str) -> bool:
    return texto.lower() in ['sí', 'si', 's', 'claro', 'si,', 'sí,', 'si claro', 'sí claro']

def _es_negacion(texto: str) -> bool:
    return texto.lower() in ['no', 'n', 'nop', 'nope', 'no,']

def _normalize_phone(p):
    """Normaliza número para Twilio: acepta +57300... o whatsapp:+57300... -> devuelve whatsapp:+57300..."""
    if not p:
        return p
    p = p.strip()
    if p.startswith("whatsapp:"):
        return p
    if p.startswith("+"):
        return "whatsapp:" + p
    # si viene sin +, intenta dejar como está (no ideal)
    return p

def _send_whatsapp_message(to_whatsapp, body):
    """Envía un mensaje proactivo vía Twilio REST. Devuelve True/False."""
    if not tw_client or not TW_WHATSAPP_FROM:
        # no configurado
        print("Twilio REST no configurado. No se pudo enviar mensaje proactivo.")
        return False
    try:
        tw_client.messages.create(
            body=body,
            from_=TW_WHATSAPP_FROM,
            to=_normalize_phone(to_whatsapp)
        )
        return True
    except Exception as e:
        print("Error al enviar mensaje por Twilio REST:", e)
        return False

@app.route("/whatsapp", methods=['POST'])
def whatsapp_bot():
    numero = request.form.get('From')  # viene como 'whatsapp:+57...'
    mensaje = (request.form.get('Body') or "").strip()
    mensaje_low = mensaje.lower()
    num_media = int(request.form.get('NumMedia') or 0)
    resp = MessagingResponse()

    # ---- Primer contacto ----
    if numero not in usuarios:
        usuarios[numero] = {'estado': 'inicio', 'media': []}
        resp.message(
            "¡Hola! ¡Estamos felices de tenerte por aquí! 😊\n\n"
            "Soy un asistente virtual de Spa Milena Bravo y estoy lista para ayudarte a conseguir las uñas de tus sueños.\n\n"
            "Para darte una mejor atención, ¿me dices tu nombre, por favor?"
        )
        return str(resp)

    # Admin command: PROPUESTA <cliente_num> <fecha_hora>
    # Ejemplo (desde un número admin autorizado): PROPUESTA whatsapp:+573001234567 19/09 18:00
    # o PROPUESTA +573001234567 19/09 18:00
    if numero in ADMIN_NUMBERS:
        # permitir comandos administrativos
        if mensaje_low.startswith("propuesta "):
            parts = mensaje.split(None, 2)  # ["PROPUESTA", "<num>", "<fecha...>"]
            if len(parts) >= 3:
                cliente_raw = parts[1].strip()
                propuesta_fecha = parts[2].strip()
                cliente_wh = _normalize_phone(cliente_raw)
                # asegúrate que el cliente exista en usuarios (si no, inicializa)
                usuarios.setdefault(cliente_wh, {'estado': 'menu', 'media': []})
                usuarios[cliente_wh]['fecha_hora_propuesta'] = propuesta_fecha
                usuarios[cliente_wh]['estado'] = 'confirmar_agendamiento'
                # enviar propuesta al cliente vía Twilio REST
                texto_propuesta = (
                    f"Hemos revisado nuestra agenda y proponemos la fecha/hora: {propuesta_fecha}.\n\n"
                    "Por favor *confirma* con 'Sí' para que agendemos, o responde 'No' para reprogramar."
                )
                ok = _send_whatsapp_message(cliente_wh, texto_propuesta)
                if ok:
                    resp.message(f"✅ Propuesta enviada a {cliente_wh}: {propuesta_fecha}")
                else:
                    resp.message("❌ Error: no se pudo enviar la propuesta al cliente (revisa configuración de Twilio).")
                return str(resp)
            else:
                resp.message("Formato inválido. Usa: PROPUESTA <tel_cliente> <fecha y hora>")
                return str(resp)

    estado = usuarios[numero].get('estado', 'menu')

    # ---- Estado: menu ----
    if estado == 'menu':
        if mensaje_low in ['1', 'pedir cita']:
            usuarios[numero]['estado'] = 'cita_servicio'
            resp.message("¡Perfecto! 💅 Vamos a agendar tu cita.\nEstos son nuestros servicios:\n" +
                         "\n".join([f"{k}️⃣ {v['nombre']}" for k, v in servicios.items()]))
        elif mensaje_low in ['2', 'dirección', 'direccion']:
            resp.message("Nuestra dirección es: Calle 53 #78-61. Barrio Los Colores, Medellín.")
        elif mensaje_low in ['3', 'instagram']:
            resp.message("Nuestro Instagram es: @milenabravo.co")
        else:
            resp.message("Cuéntame, ¿en qué puedo ayudarte?\n1️⃣ Pedir cita\n2️⃣ Ver dirección\n3️⃣ Instagram\n4️⃣ Otra pregunta")
        return str(resp)

    # ---- Selección de servicio ----
    if estado == 'cita_servicio':
        if mensaje_low in servicios.keys():
            usuarios[numero]['servicio'] = mensaje_low
            usuarios[numero]['estado'] = 'cita_subopcion'
            subopc = servicios[mensaje_low]['subopciones']
            resp.message("Elegiste: " + servicios[mensaje_low]['nombre'] + "\n"
                         "Ahora elige una opción:\n" +
                         "\n".join([f"{i+1}️⃣ {subopc[i]}" for i in range(len(subopc))]))
        else:
            resp.message("Por favor, selecciona un número válido del servicio.")
        return str(resp)

    # ---- Selección de subopción ----
    if estado == 'cita_subopcion':
        servicio_id = usuarios[numero]['servicio']
        subopc = servicios[servicio_id]['subopciones']
        valid_choices = [str(i+1) for i in range(len(subopc))]
        if mensaje in valid_choices and int(mensaje)-1 < len(subopc):
            usuarios[numero]['subopcion'] = subopc[int(mensaje)-1]
            usuarios[numero]['estado'] = 'cita_diseno'
            resp.message(
                "¿Tienes un diseño o una foto de referencia que puedas compartir para que estimemos el tiempo de la cita? "
                "Responde 'Sí' o 'No'. Si tienes la imagen, también la puedes enviar aquí."
            )
        else:
            resp.message("Por favor, selecciona un número válido de las subopciones.")
        return str(resp)

    # ---- Estado: cita_diseno ----
    if estado == 'cita_diseno':
        # Si se envió media, manejamos como que tiene diseño automáticamente
        if num_media > 0:
            media_url = request.form.get('MediaUrl0')
            if media_url:
                usuarios[numero].setdefault('media', []).append(media_url)
            usuarios[numero]['tiene_diseno'] = True
            usuarios[numero]['estado'] = 'cita_fecha'
            resp.message("¡Gracias por la imagen! La recibimos. 💖\nAhora, ¿qué día y hora prefieres para tu cita? (ejemplo: 20/09 15:00)")
            return str(resp)

        # Si responde texto sí/no
        if _es_afirmacion(mensaje_low):
            usuarios[numero]['tiene_diseno'] = True
            usuarios[numero]['estado'] = 'cita_fecha'
            resp.message(
                "Excelente 💖 Si quieres, puedes enviarnos la foto ahora. De todas formas, ¿qué día y hora prefieres para tu cita? (ejemplo: 20/09 15:00)"
            )
        elif _es_negacion(mensaje_low):
            usuarios[numero]['tiene_diseno'] = False
            usuarios[numero]['estado'] = 'cita_fecha'
            resp.message(
                "No hay problema. 👌\nRevisaremos nuestra agenda para verificar disponibilidad. En breve te propondré opciones por este chat."
            )
            # Note: si no tiene diseño, aún pedimos día/hora (según tu flujo original pediste que aun pregunte)
            resp.message("Mientras tanto, ¿qué día y hora prefieres para tu cita? (ejemplo: 20/09 15:00)")
        else:
            resp.message("Por favor responde 'Sí' o 'No'. Si tienes la foto, también puedes enviarla aquí.")
        return str(resp)

    # ---- Estado: cita_fecha (cliente sugiere una fecha/hora) ----
    if estado == 'cita_fecha':
        usuarios[numero]['fecha_hora_solicitada'] = mensaje  # guardamos lo que solicitó el cliente
        usuarios[numero]['estado'] = 'espera_revision'
        resp.message(
            "Gracias. Revisaremos nuestra agenda para verificar disponibilidad. En breve (un momento) te propondré opciones concretas "
            "por este chat. Mientras reviso, por favor espera un momento."
        )
        # Nota: tú como admin deberás revisar el calendario y luego usar el comando admin PROPUESTA para proponer una fecha/hora
        return str(resp)

    # ---- Estado: espera_revision (cliente espera la propuesta del admin) ----
    if estado == 'espera_revision':
        # El cliente puede escribir para pedir estado
        if 'estado' in mensaje_low or 'confirmar' in mensaje_low or '¿' in mensaje_low:
            resp.message("Tu solicitud está en revisión. En breve te propondré las fechas disponibles. 😊")
        else:
            resp.message("Estamos revisando la disponibilidad. En cuanto tengamos una propuesta te escribiremos por este chat.")
        return str(resp)

    # ---- Estado: confirmar_agendamiento (el bot ya envió una propuesta y espera Sí/No del cliente) ----
    if estado == 'confirmar_agendamiento':
        if _es_afirmacion(mensaje_low):
            # Confirmación final: usamos la fecha propuesta si existe, si no usamos la solicitada
            fecha_confirmada = usuarios[numero].get('fecha_hora_propuesta') or usuarios[numero].get('fecha_hora_solicitada')
            usuarios[numero]['estado'] = 'menu'
            resp.message(
                f"✅ Tu cita ha sido agendada exitosamente!\n"
                f"Te esperamos el {fecha_confirmada} 💖\n"
                f"Gracias por elegir Spa Milena Bravo. Te enviaremos un recordatorio antes de tu cita."
            )
            # Aquí podrías: crear el evento en Google Calendar (si implementas la integración)
        elif _es_negacion(mensaje_low):
            usuarios[numero]['estado'] = 'espera_revision'
            resp.message(
                "Entendido. Vamos a reprogramar. Por favor espera mientras revisamos otras opciones, o indica qué día/hora prefieres ahora."
            )
        else:
            resp.message("Por favor responde 'Sí' para confirmar la agenda o 'No' para reprogramar.")
        return str(resp)

    # ---- Otros casos: volver al menú ----
    usuarios[numero]['estado'] = 'menu'
    resp.message("Lo siento, no entendí. ¿En qué puedo ayudarte?\n1️⃣ Pedir cita\n2️⃣ Ver dirección\n3️⃣ Instagram\n4️⃣ Otra pregunta")
    return str(resp)

# NOTA: no ejecutamos app.run() aquí. Render / gunicorn importarán "app" desde app.py
