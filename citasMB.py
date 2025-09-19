# citasMB.py (actualizado)
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import datetime

app = Flask(__name__)

# Diccionario para almacenar estado y datos del usuario
usuarios = {}

# Servicios y subopciones
servicios = {
    "1": {"nombre": "Manicure tradicional", "subopciones": ["Normal", "Francesa", "Nail art"]},
    "2": {"nombre": "Manicure en gel", "subopciones": ["Normal", "Francesa", "Nail art"]},
    "3": {"nombre": "Pedicure", "subopciones": ["Spa", "Normal"]},
    "4": {"nombre": "Paquete completo", "subopciones": ["Manicure + Pedicure", "Manicure + Gel"]}
}

def _es_afirmacion(texto: str) -> bool:
    return texto in ['sí', 'si', 's', 'si,', 'sí,', 'claro', 'si claro', 'si, claro']

def _es_negacion(texto: str) -> bool:
    return texto in ['no', 'n', 'no,', 'nop', 'nope']

@app.route("/whatsapp", methods=['POST'])
def whatsapp_bot():
    numero = request.form.get('From')
    # Twilio envía Body en request.form; también puede venir media
    mensaje = (request.form.get('Body') or "").strip().lower()
    num_media = int(request.form.get('NumMedia') or 0)
    resp = MessagingResponse()

    # Primer contacto
    if numero not in usuarios:
        usuarios[numero] = {'estado': 'inicio', 'media': []}
        resp.message(
            "¡Hola! ¡Estamos felices de tenerte por aquí! 😊\n\n"
            "Soy un asistente virtual de Spa Milena Bravo y estoy lista para ayudarte a conseguir las uñas de tus sueños.\n\n"
            "Para darte una mejor atención, ¿me dices tu nombre, por favor?"
        )
        return str(resp)

    estado = usuarios[numero]['estado']

    # Guardar nombre
    if estado == 'inicio':
        usuarios[numero]['nombre'] = mensaje.title() if mensaje else "Cliente"
        usuarios[numero]['estado'] = 'menu'
        resp.message(
            f"¡Encantada de conocerte, {usuarios[numero]['nombre']}! 😍\n\n"
            "¿En qué puedo ayudarte hoy?\n"
            "1️⃣ Pedir cita\n"
            "2️⃣ Ver dirección\n"
            "3️⃣ Instagram\n"
            "4️⃣ Otra pregunta"
        )
        return str(resp)

    # Menú principal
    if estado == 'menu':
        if mensaje in ['1', 'pedir cita']:
            usuarios[numero]['estado'] = 'cita_servicio'
            resp.message("¡Perfecto! 💅 Vamos a agendar tu cita.\nEstos son nuestros servicios:\n" +
                         "\n".join([f"{k}️⃣ {v['nombre']}" for k, v in servicios.items()]))
        elif mensaje in ['2', 'dirección', 'direccion']:
            resp.message("Nuestra dirección es: Calle 53 #78-61. Barrio Los Colores, Medellín.")
        elif mensaje in ['3', 'instagram']:
            resp.message("Nuestro Instagram es: @milenabravo.co")
        else:
            resp.message("Cuéntame, ¿en qué puedo ayudarte?")
        return str(resp)

    # Selección de servicio
    if estado == 'cita_servicio':
        if mensaje in servicios.keys():
            usuarios[numero]['servicio'] = mensaje
            usuarios[numero]['estado'] = 'cita_subopcion'
            subopc = servicios[mensaje]['subopciones']
            resp.message("Elegiste: " + servicios[mensaje]['nombre'] + "\n"
                         "Ahora elige una opción:\n" +
                         "\n".join([f"{i+1}️⃣ {subopc[i]}" for i in range(len(subopc))]))
        else:
            resp.message("Por favor, selecciona un número válido del servicio.")
        return str(resp)

    # Selección de subopción
    if estado == 'cita_subopcion':
        servicio_id = usuarios[numero]['servicio']
        subopc = servicios[servicio_id]['subopciones']
        if mensaje in [str(i+1) for i in range(len(subopc))] and int(mensaje)-1 < len(subopc):
            usuarios[numero]['subopcion'] = subopc[int(mensaje)-1]
            usuarios[numero]['estado'] = 'cita_diseno'
            # Preguntamos si tiene diseño para saber cuánto tiempo reservar
            resp.message(
                "¿Tienes un diseño o una foto de referencia que puedas compartir para que estimemos el tiempo de la cita? "
                "Responde 'Sí' o 'No'. Si tienes la imagen, también la puedes enviar aquí."
            )
        else:
            resp.message("Por favor, selecciona un número válido de las subopciones.")
        return str(resp)

    # Estado: preguntar si tiene diseño (y dar opción de enviar imagen)
    if estado == 'cita_diseno':
        # Si viene una media (imagen) la guardamos y tratamos como que tiene diseño
        if num_media > 0:
            # Guardamos la URL del media (MediaUrl0). Twilio usa MediaUrl0..MediaUrlN
            media_url = request.form.get('MediaUrl0')
            if media_url:
                usuarios[numero].setdefault('media', []).append(media_url)
            usuarios[numero]['tiene_diseno'] = True
            usuarios[numero]['estado'] = 'cita_fecha'
            resp.message("¡Gracias por la imagen! La recibimos. 💖\nAhora, ¿qué día y hora prefieres para tu cita? (ejemplo: 20/09 15:00)")
            return str(resp)

        # Si el usuario responde texto
        if _es_afirmacion(mensaje):
            usuarios[numero]['tiene_diseno'] = True
            usuarios[numero]['estado'] = 'cita_fecha'
            resp.message("Excelente 💖 Si quieres, también puedes enviarnos la foto del diseño ahora. "
                         "De todas formas, ¿qué día y hora prefieres para tu cita? (ejemplo: 20/09 15:00)")
        elif _es_negacion(mensaje):
            usuarios[numero]['tiene_diseno'] = False
            usuarios[numero]['estado'] = 'cita_fecha'
            resp.message("No hay problema. 👌\nExcelente 💖 Ahora, ¿qué día y hora prefieres para tu cita? (ejemplo: 20/09 15:00)")
        else:
            resp.message("Por favor responde 'Sí' o 'No'. Si tienes la foto, también puedes enviarla aquí.")
        return str(resp)

    # Recepción de fecha y hora
    if estado == 'cita_fecha':
        # Guardar fecha y hora en formato simple
        usuarios[numero]['fecha_hora'] = mensaje
        usuarios[numero]['estado'] = 'cita_confirmacion'
        # Mostrar resumen y pedir confirmación
        servicio_nombre = servicios[usuarios[numero]['servicio']]['nombre'] if 'servicio' in usuarios[numero] else "Servicio"
        resp.message(
            f"Perfecto 😍\nHas solicitado:\n"
            f"Servicio: {servicio_nombre}\n"
            f"Detalle: {usuarios[numero].get('subopcion','')}\n"
            f"Fecha/Hora solicitada: {mensaje}\n\n"
            "Ahora, por favor confirma si quieres que gestionemos esta solicitud escribiendo 'Sí' para que la verifiquemos en el calendario y te confirmemos, o 'No' para cancelar."
        )
        return str(resp)

    # Confirmación: aquí el cliente pide que se agende (pero tú harás la comprobación manual)
    if estado == 'cita_confirmacion':
        if _es_afirmacion(mensaje):
            usuarios[numero]['estado'] = 'espera_confirmacion'
            # Aquí es donde podrías integrar la creación automática en Google Calendar.
            # Por ahora dejamos que el humano (tú) revise disponibilidad y confirme.
            resp.message(
                "✅ Tu solicitud ha sido recibida.\n"
                "Voy a verificar la disponibilidad en el calendario y te confirmaré en este chat cuando esté agendada. "
                "Si nos compartiste una imagen, la hemos guardado y la revisará la manicurista."
            )
            # Opcional: guardar en un log / base de datos para revisar manualmente
        elif _es_negacion(mensaje):
            usuarios[numero]['estado'] = 'menu'
            resp.message("Tu solicitud ha sido cancelada. Si deseas, puedes iniciar de nuevo el proceso.")
        else:
            resp.message("Por favor responde 'Sí' para confirmar la solicitud o 'No' para cancelar.")
        return str(resp)

    # Estado: espera_confirmacion (usuario ya pidió y tú vas a revisar manualmente)
    if estado == 'espera_confirmacion':
        # Opcional: permitir que el cliente pregunte por estado
        if 'estado de la cita' in mensaje or 'confirmar' in mensaje:
            resp.message("Tu solicitud está en revisión. Te avisaremos cuando la cita esté confirmada. 😊")
        else:
            resp.message("Gracias. En cuanto verifiquemos disponibilidad te confirmaremos la cita.")
        return str(resp)

    # Si algo no encaja, volver al menú
    usuarios[numero]['estado'] = 'menu'
    resp.message("Lo siento, no entendí. ¿En qué puedo ayudarte?\n1️⃣ Pedir cita\n2️⃣ Ver dirección\n3️⃣ Instagram\n4️⃣ Otra pregunta")
    return str(resp)

# NOTA: no ejecutamos app.run() aquí — Render (gunicorn) importará "app" desde app.py


