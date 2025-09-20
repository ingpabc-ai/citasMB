from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# ------------------------------
# Configuración básica y helpers
# ------------------------------
usuarios = {}

servicios = {
    "1": {"nombre": "Manicure tradicional", "subopciones": ["Normal", "Francesa", "Nail art"]},
    "2": {"nombre": "Manicure en gel", "subopciones": ["Normal", "Francesa", "Nail art"]},
    "3": {"nombre": "Pedicure", "subopciones": ["Spa", "Normal"]},
    "4": {"nombre": "Paquete completo", "subopciones": ["Manicure + Pedicure", "Manicure + Gel"]}
}

GREETINGS = {"hola", "buenas", "buenos días", "buenos dias", "buenas tardes", "buenas noches", "hi", "hello"}
YES = {"si", "sí", "s"}
NO = {"no", "n"}

def is_datetime_like(text: str) -> bool:
    # heurística simple: contiene dígitos y "/" o ":" (ej. 20/09 15:00)
    if not text:
        return False
    text = text.lower()
    contains_digit = any(ch.isdigit() for ch in text)
    contains_sep = ("/" in text) or ("-" in text) or (":" in text)
    return contains_digit and contains_sep

def debug_log(numero, estado, mensaje_raw):
    print(f"[DEBUG] número={numero} | estado={estado} | mensaje='{mensaje_raw}'")

# ------------------------------
# Endpoint webhook WhatsApp
# ------------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp_bot():
    # Normalizar número y mensaje
    raw_from = request.values.get("From", "") or ""
    numero = raw_from.replace("whatsapp:", "").strip()
    mensaje_raw = (request.values.get("Body", "") or "").strip()
    mensaje = mensaje_raw.lower().strip()

    # Response builder
    twiml = MessagingResponse()

    # Inicializar sesión si no existe
    if numero not in usuarios:
        usuarios[numero] = {
            "estado": "awaiting_name",  # awaiting_name -> cuando aún no tenemos el nombre
            "nombre": None,
            "servicio": None,
            "subopcion": None,
            "fecha_solicitada": None,
            "fecha_confirmada": None
        }

    estado = usuarios[numero]["estado"]
    debug_log(numero, estado, mensaje_raw)

    # 1) Si envían un saludo (hola) en cualquier momento -> reiniciar y pedir nombre
    if mensaje in GREETINGS:
        usuarios[numero].update({
            "estado": "awaiting_name",
            "nombre": None,
            "servicio": None,
            "subopcion": None,
            "fecha_solicitada": None,
            "fecha_confirmada": None
        })
        twiml.message(
            "¡Hola! ¡Estamos felices de tenerte por aquí! 😊\n\n"
            "Soy Sammy, el asistente virtual de Spa Milena Bravo y estoy lista para ayudarte a conseguir las uñas de tus sueños.\n\n"
            "Para darte una mejor atención, ¿me dices tu nombre, por favor?"
        )
        return Response(str(twiml), status=200, mimetype="application/xml")

    # Refrescar estado (por si no existía)
    estado = usuarios[numero]["estado"]

    # 2) Si estamos esperando nombre
    if estado == "awaiting_name":
        # Si el usuario respondió con algo, lo tomamos como nombre
        if mensaje_raw == "":
            twiml.message("No entendí tu nombre. Por favor, escribe tu nombre para que te atienda.")
            return Response(str(twiml), status=200, mimetype="application/xml")

        nombre = mensaje_raw.title()
        usuarios[numero]["nombre"] = nombre
        usuarios[numero]["estado"] = "menu"
        twiml.message(
            f"¡Encantada de conocerte, {nombre}! 😍\n\n"
            "¿En qué puedo ayudarte hoy?\n"
            "1️⃣ Pedir cita\n"
            "2️⃣ Ver dirección\n"
            "3️⃣ Instagram\n"
            "4️⃣ Otra pregunta o servicio\n\n"
            "Por favor responde con el número de la opción."
        )
        debug_log(numero, usuarios[numero]["estado"], f"guardado nombre: {nombre}")
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 3) Menú principal
    if estado == "menu":
        if mensaje in {"1", "pedir cita"}:
            usuarios[numero]["estado"] = "cita_servicio"
            opciones = "\n".join([f"{k}️⃣ {v['nombre']}" for k, v in servicios.items()])
            twiml.message("¡Perfecto! 💅 Vamos a agendar tu cita.\nEstos son nuestros servicios:\n" + opciones + "\n\nPor favor selecciona el número del servicio.")
        elif mensaje in {"2", "direccion", "dirección"}:
            twiml.message("Nuestra dirección es: Calle 53 #78-61. Barrio Los Colores, Medellín.")
        elif mensaje in {"3", "instagram"}:
            twiml.message("Nuestro Instagram es: @milenabravo.co")
        elif mensaje in {"4", "otra", "otra pregunta", "otro"}:
            usuarios[numero]["estado"] = "manual"
            twiml.message("¿En qué podemos ayudarte? ✨ Un asesor humano continuará la conversación contigo.")
        else:
            twiml.message("Por favor, elige una opción válida escribiendo un número (1, 2, 3 o 4).")
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 4) Selección de servicio (cliente ya eligió pedir cita y ahora elige cuál)
    if estado == "cita_servicio":
        if mensaje in servicios.keys():
            usuarios[numero]["servicio"] = mensaje
            usuarios[numero]["estado"] = "cita_subopcion"
            subopc = servicios[mensaje]["subopciones"]
            opciones = "\n".join([f"{i+1}️⃣ {subopc[i]}" for i in range(len(subopc))])
            twiml.message(f"Elegiste: {servicios[mensaje]['nombre']}\nAhora elige una subopción:\n{opciones}")
        else:
            twiml.message("Por favor, selecciona un número válido del servicio (ej. 1, 2, 3 o 4).")
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 5) Selección de subopción
    if estado == "cita_subopcion":
        servicio_id = usuarios[numero].get("servicio")
        if not servicio_id or servicio_id not in servicios:
            usuarios[numero]["estado"] = "cita_servicio"
            twiml.message("Ocurrió un error. Por favor selecciona de nuevo el servicio (1,2,3 o 4).")
            return Response(str(twiml), status=200, mimetype="application/xml")

        subopc = servicios[servicio_id]["subopciones"]
        if mensaje.isdigit() and 1 <= int(mensaje) <= len(subopc):
            usuarios[numero]["subopcion"] = subopc[int(mensaje) - 1]
            usuarios[numero]["estado"] = "cita_design"
            twiml.message("¿Tienes un diseño que quieras compartir con nosotras para calcular mejor el tiempo de la cita? (Responde 'Sí' o 'No')")
        else:
            twiml.message("Por favor, selecciona una subopción válida con su número.")
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 6) Pregunta si tiene diseño (si/no)
    if estado == "cita_design":
        if mensaje in YES:
            usuarios[numero]["estado"] = "cita_fecha"
            twiml.message("Perfecto 💖. Por favor indícanos ahora qué día y hora prefieres para tu cita (ejemplo: 20/09 15:00).")
        elif mensaje in NO:
            usuarios[numero]["estado"] = "cita_fecha"
            twiml.message("No hay problema 💖. Entonces indícanos qué día y hora prefieres para tu cita (ejemplo: 20/09 15:00).")
        else:
            twiml.message("Por favor responde 'Sí' o 'No' para que podamos continuar.")
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 7) Recepción de fecha y hora solicitada por el cliente
    if estado == "cita_fecha":
        # guardar lo que el cliente escribió como fecha solicitada (texto libre)
        usuarios[numero]["fecha_solicitada"] = mensaje_raw
        usuarios[numero]["estado"] = "esperando_revision"
        # Mensaje que indica que tú verificarás calendario manualmente
        twiml.message(
            "Revisaremos nuestra agenda para verificar disponibilidad 📅.\n"
            "Danos un momento, en breve te enviaremos una propuesta. Cuando te indiquemos una opción, por favor responde 'Sí' para confirmar o 'No' para reprogramar."
        )
        debug_log(numero, usuarios[numero]["estado"], f"fecha_solicitada={mensaje_raw}")
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 8) Estado: esperando_revision -> ahora el cliente puede responder con confirmación
    #    En la práctica: tú (admin) revisas el calendario fuera del bot y propones una fecha al cliente;
    #    cuando el cliente responde con la fecha (ej. "19/09 18:00") o dice "sí", el bot confirmará.
    if estado == "esperando_revision":
        # Si el cliente responde "sí" pero no hay fecha_confirmada -> pedir fecha (porque el admin no puso fecha)
        if mensaje in YES:
            # If admin has not set fecha_confirmada, but client says "si", ask to provide the date/time to confirm
            if usuarios[numero].get("fecha_confirmada"):
                usuarios[numero]["estado"] = "menu"
                fecha = usuarios[numero]["fecha_confirmada"]
                twiml.message(f"✅ Tu cita ha sido agendada exitosamente!\nTe esperamos el {fecha} 💖\nGracias por elegir Spa Milena Bravo. Te enviaremos un recordatorio antes de tu cita.")
            else:
                twiml.message("Gracias. Por favor indica la fecha y hora que deseas confirmar (ejemplo: 19/09 18:00) o espera nuestra propuesta.")
        elif is_datetime_like(mensaje_raw):
            # Si el cliente manda una fecha/hora (ej. tras propuesta humana), la tomamos como confirmación
            usuarios[numero]["fecha_confirmada"] = mensaje_raw
            usuarios[numero]["estado"] = "menu"
            fecha = usuarios[numero]["fecha_confirmada"]
            twiml.message(f"✅ Tu cita ha sido agendada exitosamente!\nTe esperamos el {fecha} 💖\nGracias por elegir Spa Milena Bravo. Te enviaremos un recordatorio antes de tu cita.")
        elif mensaje in NO:
            usuarios[numero]["estado"] = "cita_fecha"
            twiml.message("No hay problema 💖. Indícanos otra fecha y hora que prefieras.")
        else:
            twiml.message("Estamos procesando tu solicitud. Si ya confirmaste con el asesor, por favor responde con la fecha/hora (ej: 19/09 18:00) o responde 'Sí' cuando quieras confirmar.")
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 9) Estado manual -> atención humana (el bot no gestiona más)
    if estado == "manual":
        twiml.message("Un asesor humano tomará el chat y te responderá en breve. 🙌")
        return Response(str(twiml), status=200, mimetype="application/xml")

    # Default safety net
    twiml.message("Lo siento, no entendí tu mensaje. Escribe 'hola' para comenzar de nuevo.")
    usuarios[numero]["estado"] = "awaiting_name"
    return Response(str(twiml), status=200, mimetype="application/xml")

# endpoint raíz opcional para chequear
@app.route("/", methods=["GET"])
def home():
    return "Chatbot Milena Bravo — Servicio en línea ✅"

if __name__ == "__main__":
    app.run(port=5000, debug=True)







