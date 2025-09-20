from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Diccionario para guardar estados de usuarios
user_state = {}

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "").strip()
    from_number = request.values.get("From")
    
    # Normalizar texto
    clean_msg = incoming_msg.lower().strip()
    
    # Respuesta Twilio
    resp = MessagingResponse()
    msg = resp.message()
    
    # Reinicio manual si el cliente escribe "hola"
    if clean_msg in ["hola", "buenas", "hi"]:
        user_state[from_number] = {"step": "ask_name", "name": None}
    
    # Inicializar estado si no existe
    if from_number not in user_state:
        user_state[from_number] = {"step": "ask_name", "name": None}
    
    state = user_state[from_number]
    
    # Paso 1: Preguntar nombre
    if state["step"] == "ask_name":
        msg.body("¡Hola! ¡Estamos felices de tenerte por aquí! 😊\n\n"
                 "Soy Sammy, el asistente virtual de *Spa Milena Bravo* y estoy lista para ayudarte a conseguir las uñas de tus sueños.\n\n"
                 "Para darte una mejor atención, ¿me dices tu nombre, por favor?")
        state["step"] = "get_name"
        return str(resp)
    
    # Paso 2: Recibir nombre y mostrar menú
    elif state["step"] == "get_name":
        # Guardar nombre con primera letra mayúscula
        name = incoming_msg.strip().title()
        state["name"] = name
        state["step"] = "menu"
        msg.body(f"¡Encantada de conocerte, {state['name']}! 😍\n\n"
                 "¿En qué puedo ayudarte hoy?\n"
                 "1️⃣ Pedir cita\n"
                 "2️⃣ Ver dirección\n"
                 "3️⃣ Dirección Instagram\n"
                 "4️⃣ Otra pregunta o servicio")
        return str(resp)
    
    # Paso 3: Procesar elección del menú
    elif state["step"] == "menu":
        if clean_msg == "1":
            msg.body("Perfecto ✨. Para agendar tu cita, por favor indícanos:\n"
                     "- El servicio que deseas\n"
                     "- Día y hora de preferencia\n\n"
                     "Te confirmaremos la disponibilidad enseguida 💅")
        elif clean_msg == "2":
            msg.body("📍 Nuestra dirección es: *Cra 15 # 10-25, Cali*. ¡Te esperamos!")
        elif clean_msg == "3":
            msg.body("Síguenos en Instagram 📸: https://instagram.com/spamilenabravo")
        elif clean_msg == "4":
            msg.body("Claro 😊, ¿en qué podemos ayudarte?")
            state["step"] = "manual"  # se deja abierto para atención humana
        else:
            msg.body("Por favor elige una de las opciones enviando el número correspondiente (1, 2, 3 o 4).")
        return str(resp)
    
    # Paso 4: Atención manual
    elif state["step"] == "manual":
        msg.body("Gracias por tu mensaje 🙌. Un asesor te responderá en breve.")
        return str(resp)
    
    # Seguridad por si acaso
    else:
        msg.body("Lo siento, no entendí tu mensaje. Escribe 'hola' para empezar de nuevo 😊")
        user_state[from_number] = {"step": "ask_name", "name": None}
        return str(resp)


if __name__ == "__main__":
    app.run(port=10000, debug=True)






