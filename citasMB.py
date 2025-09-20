import os
import json
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

# Librerías de Firebase Admin para Python
import firebase_admin
from firebase_admin import credentials, firestore

# Configuración y helpers
usuarios = {} # Este diccionario ya no se usa para la persistencia

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
    if not text:
        return False
    text = text.lower()
    contains_digit = any(ch.isdigit() for ch in text)
    contains_sep = ("/" in text) or ("-" in text) or (":" in text)
    return contains_digit and contains_sep

def debug_log(numero, estado, mensaje_raw):
    print(f"[DEBUG] número={numero} | estado={estado} | mensaje='{mensaje_raw}'")

# Inicialización de la aplicación Flask
app = Flask(__name__)

# ------------------------------
# Configuración de Firebase Admin SDK
# ------------------------------
# La clave de Firebase debe ser una variable de entorno en Render
try:
    firebase_service_key_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY")
    if firebase_service_key_json:
        # Usar la clave de entorno para la autenticación
        cred = credentials.Certificate(json.loads(firebase_service_key_json))
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase Admin SDK inicializado correctamente.")
    else:
        # Fallback para desarrollo local (requiere el archivo de clave)
        # Esto no funcionará en Render sin la variable de entorno
        print("ADVERTENCIA: La variable de entorno FIREBASE_SERVICE_ACCOUNT_KEY no se encontró.")
        db = None # Firestore no estará disponible
except Exception as e:
    print(f"Error al inicializar Firebase: {e}")
    db = None

# ------------------------------
# Endpoint webhook WhatsApp
# ------------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp_bot():
    raw_from = request.values.get("From", "") or ""
    numero = raw_from.replace("whatsapp:", "").strip()
    mensaje_raw = (request.values.get("Body", "") or "").strip()
    mensaje = mensaje_raw.lower().strip()

    twiml = MessagingResponse()

    # Si la base de datos no está disponible, enviar un mensaje de error y salir
    if not db:
        twiml.message("Disculpa, nuestro asistente virtual está en mantenimiento. Inténtalo de nuevo más tarde.")
        return Response(str(twiml), status=200, mimetype="application/xml")

    # Obtener o inicializar los datos del usuario desde Firestore
    user_ref = db.collection("users").document(numero)
    user_doc = user_ref.get()

    if user_doc.exists:
        user_data = user_doc.to_dict()
    else:
        user_data = {
            "estado": "awaiting_name",
            "nombre": None,
            "servicio": None,
            "subopcion": None,
            "fecha_solicitada": None,
            "fecha_confirmada": None
        }
        user_ref.set(user_data) # Crear el documento inicial

    estado = user_data["estado"]
    debug_log(numero, estado, mensaje_raw)

    # 1) Si envían un saludo (hola) en cualquier momento -> reiniciar
    if mensaje in GREETINGS:
        if user_data["nombre"]:
            user_data["estado"] = "menu"
            twiml.message(
                f"¡Hola de nuevo, {user_data['nombre']}! 👋\n\n"
                "¿En qué más puedo ayudarte hoy?\n"
                "1️⃣ Pedir cita\n"
                "2️⃣ Ver dirección\n"
                "3️⃣ Instagram\n"
                "4️⃣ Otra pregunta o servicio\n\n"
                "Por favor responde con el número de la opción."
            )
        else:
            user_data = {
                "estado": "awaiting_name",
                "nombre": None,
                "servicio": None,
                "subopcion": None,
                "fecha_solicitada": None,
                "fecha_confirmada": None
            }
            twiml.message(
                "¡Hola! ¡Estamos felices de tenerte por aquí! 😊\n\n"
                "Soy Sammy, el asistente virtual de Spa Milena Bravo y estoy lista para ayudarte a conseguir las uñas de tus sueños.\n\n"
                "Para darte una mejor atención, ¿me dices tu nombre, por favor?"
            )
        user_ref.set(user_data) # Guardar los cambios
        return Response(str(twiml), status=200, mimetype="application/xml")

    # Si el estado es "manual", no se hace nada más
    if estado == "manual":
        twiml.message("Un asesor humano ya está al tanto de tu conversación y te responderá en breve. 🙌")
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 2) Si estamos esperando nombre
    if estado == "awaiting_name":
        if not mensaje_raw:
            twiml.message("No entendí tu nombre. Por favor, escribe tu nombre para que te atienda.")
        else:
            nombre = mensaje_raw.title()
            user_data["nombre"] = nombre
            user_data["estado"] = "menu"
            twiml.message(
                f"¡Encantada de conocerte, {nombre}! 😍\n\n"
                "¿En qué puedo ayudarte hoy?\n"
                "1️⃣ Pedir cita\n"
                "2️⃣ Ver dirección\n"
                "3️⃣ Instagram\n"
                "4️⃣ Otra pregunta o servicio\n\n"
                "Por favor responde con el número de la opción."
            )
            debug_log(numero, user_data["estado"], f"guardado nombre: {nombre}")
        user_ref.update(user_data)
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 3) Menú principal
    if estado == "menu":
        if mensaje in {"1", "pedir cita"}:
            user_data["estado"] = "cita_servicio"
            opciones = "\n".join([f"{k}️⃣ {v['nombre']}" for k, v in servicios.items()])
            twiml.message("¡Perfecto! 💅 Vamos a agendar tu cita.\nEstos son nuestros servicios:\n" + opciones + "\n\nPor favor selecciona el número del servicio.")
        elif mensaje in {"2", "direccion", "dirección"}:
            twiml.message("Nuestra dirección es: Calle 53 #78-61. Barrio Los Colores, Medellín.")
        elif mensaje in {"3", "instagram"}:
            twiml.message("Nuestro Instagram es: @milenabravo.co")
        elif mensaje in {"4", "otra", "otra pregunta", "otro"}:
            user_data["estado"] = "manual"
            twiml.message("¡Claro! Con gusto. ✨ Un asesor humano continuará la conversación contigo.")
        else:
            twiml.message("Por favor, elige una opción válida escribiendo un número (1, 2, 3 o 4).")
        user_ref.update(user_data)
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 4) Selección de servicio
    if estado == "cita_servicio":
        if mensaje in servicios.keys():
            user_data["servicio"] = mensaje
            user_data["estado"] = "cita_subopcion"
            subopc = servicios[mensaje]["subopciones"]
            opciones = "\n".join([f"{i+1}️⃣ {subopc[i]}" for i in range(len(subopc))])
            twiml.message(f"Elegiste: {servicios[mensaje]['nombre']}\nAhora elige una subopción:\n{opciones}")
        else:
            twiml.message("Por favor, selecciona un número válido del servicio (ej. 1, 2, 3 o 4).")
        user_ref.update(user_data)
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 5) Selección de subopción
    if estado == "cita_subopcion":
        servicio_id = user_data.get("servicio")
        if not servicio_id or servicio_id not in servicios:
            user_data["estado"] = "cita_servicio"
            twiml.message("Ocurrió un error. Por favor selecciona de nuevo el servicio (1,2,3 o 4).")
        else:
            subopc = servicios[servicio_id]["subopciones"]
            if mensaje.isdigit() and 1 <= int(mensaje) <= len(subopc):
                user_data["subopcion"] = subopc[int(mensaje) - 1]
                user_data["estado"] = "cita_design"
                twiml.message("¿Tienes un diseño que quieras compartir con nosotras para calcular mejor el tiempo de la cita? (Responde 'Sí' o 'No')")
            else:
                twiml.message("Por favor, selecciona una subopción válida con su número.")
        user_ref.update(user_data)
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 6) Pregunta si tiene diseño (si/no)
    if estado == "cita_design":
        if mensaje in YES:
            user_data["estado"] = "cita_fecha"
            twiml.message("Perfecto 💖. Por favor indícanos ahora qué día y hora prefieres para tu cita (ejemplo: 20/09 15:00).")
        elif mensaje in NO:
            user_data["estado"] = "cita_fecha"
            twiml.message("No hay problema 💖. Entonces indícanos qué día y hora prefieres para tu cita (ejemplo: 20/09 15:00).")
        else:
            twiml.message("Por favor responde 'Sí' o 'No' para que podamos continuar.")
        user_ref.update(user_data)
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 7) Recepción de fecha y hora solicitada por el cliente
    if estado == "cita_fecha":
        user_data["fecha_solicitada"] = mensaje_raw
        user_data["estado"] = "esperando_revision"
        twiml.message(
            "Revisaremos nuestra agenda para verificar disponibilidad 📅.\n"
            "Danos un momento, en breve te enviaremos una propuesta. Cuando te indiquemos una opción, por favor responde 'Sí' para confirmar o 'No' para reprogramar."
        )
        debug_log(numero, user_data["estado"], f"fecha_solicitada={mensaje_raw}")
        user_ref.update(user_data)
        return Response(str(twiml), status=200, mimetype="application/xml")

    # 8) Estado: esperando_revision -> ahora el cliente puede responder con confirmación
    if estado == "esperando_revision":
        if mensaje in YES:
            if user_data.get("fecha_confirmada"):
                user_data["estado"] = "menu"
                fecha = user_data["fecha_confirmada"]
                twiml.message(f"✅ Tu cita ha sido agendada exitosamente!\nTe esperamos el {fecha} 💖\nGracias por elegir Spa Milena Bravo. Te enviaremos un recordatorio antes de tu cita.")
            else:
                twiml.message("Gracias. Por favor indica la fecha y hora que deseas confirmar (ejemplo: 19/09 18:00) o espera nuestra propuesta.")
        elif is_datetime_like(mensaje_raw):
            user_data["fecha_confirmada"] = mensaje_raw
            user_data["estado"] = "menu"
            fecha = user_data["fecha_confirmada"]
            twiml.message(f"✅ Tu cita ha sido agendada exitosamente!\nTe esperamos el {fecha} 💖\nGracias por elegir Spa Milena Bravo. Te enviaremos un recordatorio antes de tu cita.")
        elif mensaje in NO:
            user_data["estado"] = "cita_fecha"
            twiml.message("No hay problema 💖. Indícanos otra fecha y hora que prefieras.")
        else:
            twiml.message("Estamos procesando tu solicitud. Si ya confirmaste con el asesor, por favor responde con la fecha/hora (ej: 19/09 18:00) o responde 'Sí' cuando quieras confirmar.")
        user_ref.update(user_data)
        return Response(str(twiml), status=200, mimetype="application/xml")

    # Default safety net
    twiml.message("Lo siento, no entendí tu mensaje. Escribe 'hola' para comenzar de nuevo.")
    user_data["estado"] = "awaiting_name"
    user_ref.update(user_data)
    return Response(str(twiml), status=200, mimetype="application/xml")

# endpoint raíz opcional para chequear
@app.route("/", methods=["GET"])
def home():
    return "Chatbot Milena Bravo — Servicio en línea ✅"

if __name__ == "__main__":
    app.run(port=5000, debug=True)