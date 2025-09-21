import os
import json
import re
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import firebase_admin
from firebase_admin import credentials, firestore

# Configuración
GREETINGS = {"hola", "buenas", "buenos días", "buenos dias", "buenas tardes", "buenas noches", "hi", "hello"}
YES = {"si", "sí", "s"}
NO = {"no", "n"}

# Árbol de menús
menu = {
    "1": {
        "texto": "Pedir cita manos y/o pies",
        "sub": {
            "1": {
                "texto": "Solamente manos",
                "sub": {
                    "1": {"texto": "Tradicional", "tipo": "fecha"},
                    "2": {"texto": "Semipermanentes", "tipo": "diseño"},
                    "3": {"texto": "Acrílicas o en polygel", "tipo": "diseño"}
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
    "5": {"texto": "Tengo una consulta", "tipo": "consulta"},
    "6": {"texto": "Reprogramar una cita", "tipo": "reprogramar"}
}

# Funciones de ayuda
def debug_log(numero, estado, mensaje_raw, additional_info=None):
    print(f"[DEBUG] número={numero} | estado={estado} | mensaje='{mensaje_raw}' | info={additional_info}")

def is_valid_date_format(date_str):
    pattern = r"^\d{2}/\d{2}\s+\d{2}:\d{2}$"
    return bool(re.match(pattern, date_str))

def is_valid_ruta(ruta, menu):
    current = menu
    for step in ruta:
        if "sub" not in current or step not in current["sub"]:
            return False
        current = current["sub"][step]
    return True

def render_menu(nodo):
    if "sub" not in nodo:
        return None
    opciones = [f"{k}️⃣ {v['texto']}" for k, v in nodo["sub"].items()]
    return "\n".join(opciones)

def send_to_manual(user_data, user_ref, twiml):
    user_data["estado"] = "manual"
    twiml.message("Revisaremos nuestra agenda para verificar disponibilidad 📅. Danos un momento, en breve te enviaremos una propuesta.")
    try:
        user_ref.set(user_data)
    except Exception as e:
        print(f"Error al guardar en Firestore: {e}")
        twiml.message("Lo sentimos, ocurrió un error al procesar tu solicitud. Intenta de nuevo.")

def send_to_manual_reprogram(user_data, user_ref, twiml):
    user_data["estado"] = "manual"
    twiml.message("Revisaremos nuestra agenda para verificar disponibilidad 📅.\nDanos un momento, en breve te enviaremos una propuesta.")
    try:
        user_ref.set(user_data)
    except Exception as e:
        print(f"Error al guardar en Firestore: {e}")
        twiml.message("Lo sentimos, ocurrió un error al procesar tu solicitud. Intenta de nuevo.")

# Flask + Firebase
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

# Webhook WhatsApp
@app.route("/whatsapp", methods=["POST"])
def whatsapp_bot():
    twiml = MessagingResponse()
    
    try:
        numero = request.values.get("From", "").replace("whatsapp:", "").strip()
        mensaje_raw = (request.values.get("Body", "") or "").strip()
        mensaje = mensaje_raw.lower()
        media_url = request.values.get("MediaUrl0")

        if not db:
            twiml.message("Disculpa, nuestro asistente está en mantenimiento. Intenta más tarde 🙏")
            return Response(str(twiml), 200, mimetype="application/xml")

        user_ref = db.collection("users").document(numero)
        user_doc = user_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
        else:
            user_data = {"estado": "awaiting_name", "nombre": None, "ruta": [], "fecha": None}
            try:
                user_ref.set(user_data)
            except Exception as e:
                print(f"Error al guardar nuevo usuario en Firestore: {e}")
                twiml.message("Lo sentimos, ocurrió un error al procesar tu solicitud. Intenta de nuevo.")
                return Response(str(twiml), 200, mimetype="application/xml")

        estado = user_data["estado"]
        debug_log(numero, estado, mensaje_raw, f"ruta={user_data['ruta']}")

        if mensaje in GREETINGS:
            if user_data.get("nombre"):
                user_data["estado"] = "menu"
                user_data["ruta"] = []
                menu_txt = render_menu({"sub": menu})
                twiml.message(f"¡Hola de nuevo, {user_data['nombre']}!👋 Soy Sammy, 🤖 el asistente virtual de Spa Milena Bravo💅, donde hacemos tus sueños realidad.\n\n{menu_txt}\n\nPor favor elige una opción.")
            else:
                user_data["estado"] = "awaiting_name"
                twiml.message("¡Hola! Soy Sammy, 🤖 el asistente virtual de Spa Milena Bravo💅, donde hacemos tus sueños realidad. ¿Me dices tu nombre?")
            try:
                user_ref.set(user_data)
            except Exception as e:
                print(f"Error al guardar en Firestore: {e}")
                twiml.message("Lo sentimos, ocurrió un error al procesar tu solicitud. Intenta de nuevo.")
        elif estado == "awaiting_name":
            nombre = mensaje_raw.title()
            user_data["nombre"] = nombre
            user_data["estado"] = "menu"
            menu_txt = render_menu({"sub": menu})
            twiml.message(f"¡Encantada de conocerte, {nombre}! 😍\n\n{menu_txt}\n\nResponde con un número.")
            try:
                user_ref.set(user_data)
            except Exception as e:
                print(f"Error al guardar en Firestore: {e}")
                twiml.message("Lo sentimos, ocurrió un error al procesar tu solicitud. Intenta de nuevo.")
        elif estado == "menu" or estado == "submenu":
            if not is_valid_ruta(user_data["ruta"], menu):
                user_data["ruta"] = []
                user_data["estado"] = "menu"
                try:
                    user_ref.set(user_data)
                except Exception as e:
                    print(f"Error al guardar en Firestore: {e}")
                    twiml.message("Lo sentimos, ocurrió un error al procesar tu solicitud. Intenta de nuevo.")
                twiml.message("Ocurrió un error. Por favor elige una opción del menú principal.")
                return Response(str(twiml), 200, mimetype="application/xml")
                
            current_node = menu
            for step in user_data["ruta"]:
                current_node = current_node["sub"][step]
            
            if mensaje in current_node:
                elegido = current_node[mensaje]
                if "sub" in elegido:
                    user_data["ruta"].append(mensaje)
                    user_data["estado"] = "submenu"
                    opciones = render_menu(elegido)
                    twiml.message(f"Elegiste: {elegido['texto']}\n\n{opciones}\n\nElige una opción.")
                else:
                    tipo = elegido.get("tipo")
                    user_data["ruta"].append(mensaje)
                    if tipo == "otros":
                        twiml.message("¿En qué servicio estás interesada? Danos un momento, en breve te brindaremos asesoría.")
                        user_data["estado"] = "manual"
                    elif tipo == "direccion":
                        twiml.message("📍 Nuestra dirección es: Calle 53 #78-61. Barrio Los Colores, Medellín.")
                        user_data["estado"] = "menu"
                        user_data["ruta"] = []
                    elif tipo == "instagram":
                        twiml.message("✨ Nuestro Instagram es: @milenabravo.co")
                        user_data["estado"] = "menu"
                        user_data["ruta"] = []
                    elif tipo == "consulta":
                        twiml.message("Cuéntanos cuál es tu consulta. Danos un momento, en breve te daremos una respuesta.")
                        user_data["estado"] = "manual"
                    elif tipo == "reprogramar":
                        user_data["estado"] = "awaiting_reprogram_date"
                        twiml.message("Señala para cuándo tenías agendada tu cita?")
                    elif tipo == "fecha":
                        user_data["estado"] = "cita_fecha"
                        twiml.message("Favor indícanos el día y hora que prefieres para tu cita (ejemplo: 20/09 15:00).")
                    elif tipo == "diseño":
                        user_data["estado"] = "cita_design"
                        twiml.message("¿Tienes un diseño que quieras compartir con nosotras para calcular mejor el tiempo de la cita? (Responde 'Sí' o 'No').")
                    try:
                        user_ref.set(user_data)
                    except Exception as e:
                        print(f"Error al guardar en Firestore: {e}")
                        twiml.message("Lo sentimos, ocurrió un error al procesar tu solicitud. Intenta de nuevo.")
            else:
                twiml.message("Por favor elige una opción válida con un número.")
        elif estado == "awaiting_reprogram_date":
            user_data["estado"] = "awaiting_new_date"
            twiml.message("¡Perfecto! Cuéntanos para cuándo deseas reprogramar tu cita?")
            try:
                user_ref.set(user_data)
            except Exception as e:
                print(f"Error al guardar en Firestore: {e}")
                twiml.message("Lo sentimos, ocurrió un error al procesar tu solicitud. Intenta de nuevo.")
        elif estado == "awaiting_new_date":
            send_to_manual_reprogram(user_data, user_ref, twiml)
        elif estado == "cita_design":
            if mensaje in YES:
                user_data["estado"] = "awaiting_design"
                twiml.message("Perfecto 💖. Por favor adjunta tu diseño o la descripción de lo que deseas.")
            elif mensaje in NO:
                user_data["estado"] = "cita_fecha_no_design"
                twiml.message("No hay problema 💖. Por favor indícanos el día y hora que prefieres para tu cita (ejemplo: 20/09 15:00).")
            else:
                twiml.message("Por favor responde 'Sí' o 'No'.")
            try:
                user_ref.set(user_data)
            except Exception as e:
                print(f"Error al guardar en Firestore: {e}")
                twiml.message("Lo sentimos, ocurrió un error al procesar tu solicitud. Intenta de nuevo.")
        elif estado == "awaiting_design":
            if media_url:
                user_data["design_url"] = media_url
            user_data["estado"] = "cita_fecha"
            twiml.message("Perfecto 💖. Por favor indícanos el día y hora que prefieres para tu cita (ejemplo: 20/09 15:00).")
            try:
                user_ref.set(user_data)
            except Exception as e:
                print(f"Error al guardar en Firestore: {e}")
                twiml.message("Lo sentimos, ocurrió un error al procesar tu solicitud. Intenta de nuevo.")
        elif estado == "cita_fecha" or estado == "cita_fecha_no_design":
            if is_valid_date_format(mensaje):
                send_to_manual(user_data, user_ref, twiml)
            else:
                twiml.message("Por favor, ingresa una fecha válida en el formato DD/MM HH:MM (ejemplo: 20/09 15:00).")
                try:
                    user_ref.set(user_data)
                except Exception as e:
                    print(f"Error al guardar en Firestore: {e}")
                    twiml.message("Lo sentimos, ocurrió un error al procesar tu solicitud. Intenta de nuevo.")
        else:
            twiml.message("Lo siento, no entendí tu mensaje 🙏. Escribe 'hola' para empezar de nuevo.")

    except Exception as e:
        print(f"Error inesperado en el webhook: {e}")
        twiml = MessagingResponse()
        twiml.message("Lo sentimos, se ha producido un error inesperado. Por favor, inténtalo de nuevo más tarde.")

    return Response(str(twiml), 200, mimetype="application/xml")

@app.route("/", methods=["GET"])
def home():
    return "Chatbot Milena Bravo ✅"

if __name__ == "__main__":
    app.run(port=5000, debug=True)
