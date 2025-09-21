import os
import json
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

import firebase_admin
from firebase_admin import credentials, firestore

# -------------------------------
# Configuración
# -------------------------------
GREETINGS = {"hola", "buenas", "buenos días", "buenos dias", "buenas tardes", "buenas noches", "hi", "hello"}
YES = {"si", "sí", "s"}
NO = {"no", "n"}

# Definición del árbol de menús
menu = {
    "1": {
        "texto": "Pedir cita manos y/o pies",
        "sub": {
            "1": {
                "texto": "Solamente manos",
                "sub": {
                    "1": {"texto": "Tradicional", "tipo": "fecha"},
                    "2": {"texto": "Semipermanentes", "tipo": "diseño"},
                    "3": {"texto": "Acrílicas", "tipo": "diseño"}
                }
            },
            "2": {
                "texto": "Solamente pies",
                "sub": {
                    "1": {"texto": "Tradicional", "tipo": "fecha"},
                    "2": {"texto": "Semipermanentes", "tipo": "diseño"}
                }
            },
            "3": {
                "texto": "Manos y pies",
                "sub": {
                    "1": {"texto": "Manos y pies tradicional", "tipo": "fecha"},
                    "2": {"texto": "Manos y pies semipermanentes", "tipo": "diseño"},
                    "3": {"texto": "Manos semipermanentes y pies tradicional", "tipo": "diseño"},
                    "4": {"texto": "Manos tradicional y pies semipermanente", "tipo": "fecha"},
                    "5": {"texto": "Manos acrílicas o en poligel y pies tradicional", "tipo": "diseño"},
                    "6": {"texto": "Manos acrílicas o en poligel y semipermanentes", "tipo": "diseño"}
                }
            }
        }
    },
    "2": {"texto": "Pedir cita otros servicios", "tipo": "otros"},
    "3": {"texto": "Ver dirección", "tipo": "direccion"},
    "4": {"texto": "Instagram", "tipo": "instagram"},
    "5": {"texto": "Tengo una consulta", "tipo": "consulta"}
}


def is_datetime_like(text: str) -> bool:
    if not text:
        return False
    contains_digit = any(ch.isdigit() for ch in text)
    contains_sep = ("/" in text) or ("-" in text) or (":" in text) or (" " in text)
    return contains_digit and contains_sep


def debug_log(numero, estado, mensaje_raw):
    print(f"[DEBUG] número={numero} | estado={estado} | mensaje='{mensaje_raw}'")


# -------------------------------
# Flask + Firebase
# -------------------------------
app = Flask(__name__)

try:
    firebase_service_key_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY")
    if firebase_service_key_json:
        cred = credentials.Certificate(json.loads(firebase_service_key_json))
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase inicializado.")
    else:
        print("ADVERTENCIA: no se encontró FIREBASE_SERVICE_ACCOUNT_KEY")
        db = None
except Exception as e:
    print(f"Error Firebase: {e}")
    db = None


# -------------------------------
# Funciones de ayuda
# -------------------------------
def render_menu(nodo):
    """Construye el texto de un menú dado un nodo"""
    if "sub" not in nodo:
        return None
    opciones = []
    for k, v in nodo["sub"].items():
        opciones.append(f"{k}️⃣ {v['texto']}")
    return "\n".join(opciones)


# -------------------------------
# Webhook WhatsApp
# -------------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp_bot():
    numero = request.values.get("From", "").replace("whatsapp:", "").strip()
    mensaje_raw = (request.values.get("Body", "") or "").strip()
    mensaje = mensaje_raw.lower()

    twiml = MessagingResponse()

    if not db:
        twiml.message("Disculpa, nuestro asistente está en mantenimiento. Intenta más tarde 🙏")
        return Response(str(twiml), 200, mimetype="application/xml")

    # Obtener usuario
    user_ref = db.collection("users").document(numero)
    user_doc = user_ref.get()
    if user_doc.exists:
        user_data = user_doc.to_dict()
    else:
        user_data = {"estado": "awaiting_name", "nombre": None, "ruta": [], "fecha": None}
        user_ref.set(user_data)

    estado = user_data["estado"]
    debug_log(numero, estado, mensaje_raw)

    # Reinicio con saludo
    if mensaje in GREETINGS:
        if user_data["nombre"]:
            user_data["estado"] = "menu"
            user_data["ruta"] = []
            menu_txt = render_menu({"sub": menu})
            twiml.message(f"¡Hola de nuevo, {user_data['nombre']}! 👋\n\n{menu_txt}\n\nPor favor elige una opción.")
        else:
            user_data["estado"] = "awaiting_name"
            twiml.message("¡Hola! Soy Sammy 🤖 de Spa Milena Bravo 💅.\n\n¿Me dices tu nombre?")
        user_ref.set(user_data)
        return Response(str(twiml), 200, mimetype="application/xml")

    # Nombre
    if estado == "awaiting_name":
        nombre = mensaje_raw.title()
        user_data["nombre"] = nombre
        user_data["estado"] = "menu"
        menu_txt = render_menu({"sub": menu})
        twiml.message(f"¡Encantada de conocerte, {nombre}! 😍\n\n{menu_txt}\n\nResponde con un número.")
        user_ref.set(user_data)
        return Response(str(twiml), 200, mimetype="application/xml")

    # Menú dinámico
    if estado == "menu" or estado == "submenu":
        nodo = menu
        for step in user_data["ruta"]:
            nodo = nodo["sub"][step]

        if mensaje in nodo.get("sub", {}):
            elegido = nodo["sub"][mensaje]
            user_data["ruta"].append(mensaje)

            # Si aún tiene submenús
            if "sub" in elegido:
                user_data["estado"] = "submenu"
                opciones = render_menu(elegido)
                twiml.message(f"Elegiste: {elegido['texto']}\n\n{opciones}\n\nElige una opción.")
            else:
                tipo = elegido.get("tipo")
                if tipo == "otros":
                    user_data["estado"] = "otros"
                    twiml.message("¿En qué servicio estás interesada?")
                elif tipo == "direccion":
                    twiml.message("📍 Nuestra dirección es: Calle 53 #78-61. Barrio Los Colores, Medellín.")
                    user_data["estado"] = "menu"
                    user_data["ruta"] = []
                elif tipo == "instagram":
                    twiml.message("✨ Nuestro Instagram es: @milenabravo.co")
                    user_data["estado"] = "menu"
                    user_data["ruta"] = []
                elif tipo == "consulta":
                    user_data["estado"] = "consulta"
                    twiml.message("Cuéntanos cuál es tu consulta.")
                elif tipo == "fecha":
                    user_data["estado"] = "cita_fecha"
                    twiml.message("Favor indícanos el día y hora que prefieres para tu cita (ejemplo: 20/09 15:00).")
                elif tipo == "diseño":
                    user_data["estado"] = "cita_design"
                    twiml.message("¿Tienes un diseño que quieras compartir con nosotras para calcular mejor el tiempo de la cita? (Responde 'Sí' o 'No').")
            user_ref.set(user_data)
            return Response(str(twiml), 200, mimetype="application/xml")
        else:
            twiml.message("Por favor elige una opción válida con número.")
            return Response(str(twiml), 200, mimetype="application/xml")

    # Otros servicios
    if estado == "otros":
        user_data["estado"] = "manual"
        twiml.message("Danos un momento, en breve te brindaremos asesoría 🙌.")
        user_ref.set(user_data)
        return Response(str(twiml), 200, mimetype="application/xml")

    # Consulta
    if estado == "consulta":
        user_data["estado"] = "manual"
        twiml.message("Danos un momento, en breve te daremos una respuesta 🙌.")
        user_ref.set(user_data)
        return Response(str(twiml), 200, mimetype="application/xml")

    # Diseño
    if estado == "cita_design":
        if mensaje in YES:
            user_data["estado"] = "awaiting_design"
            twiml.message("Perfecto 💖. Por favor adjunta tu diseño o la descripción de lo que deseas.")
        elif mensaje in NO:
            user_data["estado"] = "cita_fecha_no_design"
            twiml.message("No hay problema 💖. Por favor indícanos el día y hora que prefieres para tu cita (ejemplo: 20/09 15:00).")
        else:
            twiml.message("Por favor responde 'Sí' o 'No'.")
        user_ref.set(user_data)
        return Response(str(twiml), 200, mimetype="application/xml")

    if estado == "awaiting_design":
        user_data["estado"] = "cita_fecha"
        twiml.message("Perfecto 💖. Por favor indícanos el día y hora que prefieres para tu cita (ejemplo: 20/09 15:00).")
        user_ref.set(user_data)
        return Response(str(twiml), 200, mimetype="application/xml")
    
    # Fecha
    if estado == "cita_fecha" or estado == "cita_fecha_no_design":
        # Se asume que cualquier texto es una fecha/hora, ya que la validación manual
        # se hará por un asesor.
        user_data["estado"] = "manual"
        twiml.message("Revisaremos nuestra agenda para verificar disponibilidad 📅. Danos un momento, en breve te enviaremos una propuesta.")
        user_ref.set(user_data)
        return Response(str(twiml), 200, mimetype="application/xml")

    # Fallback
    twiml.message("Lo siento, no entendí tu mensaje 🙏. Escribe 'hola' para empezar de nuevo.")
    return Response(str(twiml), 200, mimetype="application/xml")


@app.route("/", methods=["GET"])
def home():
    return "Chatbot Milena Bravo ✅"


if __name__ == "__main__":
    app.run(port=5000, debug=True)
