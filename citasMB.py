from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

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

@app.route("/whatsapp", methods=['POST'])
def whatsapp_bot():
    # Debug de lo que llega
    try:
        print("---- INCOMING REQUEST FORM ----")
        for k, v in request.form.items():
            print(f"{k}: {v}")
        print("---- END FORM ----")
    except Exception as e:
        print("Error imprimiendo form:", e)

    numero = request.form.get('From')
    mensaje_raw = request.form.get('Body') or ""
    mensaje = mensaje_raw.strip().lower()
    resp = MessagingResponse()

    # --- Primer contacto (usuario nuevo o saludo) ---
    if numero not in usuarios or mensaje in ["hola", "hi", "buenas"]:
        usuarios[numero] = {'estado': 'inicio'}
        resp.message(
            "¡Hola! ¡Estamos felices de tenerte por aquí! 😊\n\n"
            "Soy Sammy, el asistente virtual de Spa Milena Bravo y estoy lista para ayudarte a conseguir las uñas de tus sueños.\n\n"
            "Para darte una mejor atención, ¿me dices tu nombre, por favor?"
        )
        return Response(str(resp), status=200, mimetype='application/xml')

    estado = usuarios[numero]['estado']

    # Guardar nombre
    if estado == 'inicio':
        usuarios[numero]['nombre'] = mensaje_raw.title()
        usuarios[numero]['estado'] = 'menu'
        resp.message(
            f"¡Encantada de conocerte, {usuarios[numero]['nombre']}! 😍\n\n"
            "¿En qué puedo ayudarte hoy?\n"
            "1️⃣ Pedir cita\n"
            "2️⃣ Ver dirección\n"
            "3️⃣ Dirección Instagram\n"
            "4️⃣ Otra pregunta o servicio"
        )
        return Response(str(resp), status=200, mimetype='application/xml')

    # Menú principal
    if estado == 'menu':
        if mensaje in ['1', 'pedir cita']:
            usuarios[numero]['estado'] = 'cita_servicio'
            resp.message("¡Perfecto! 💅 Vamos a agendar tu cita.\nEstos son nuestros servicios. (Elije un número):\n" +
                         "\n".join([f"{k}️⃣ {v['nombre']}" for k, v in servicios.items()]))
        elif mensaje in ['2', 'dirección', 'direccion']:
            resp.message("Nuestra dirección es: Calle 53 #78-61. Barrio Los Colores, Medellín.")
        elif mensaje in ['3', 'instagram']:
            resp.message("Nuestro Instagram es: @milenabravo.co")
        elif mensaje in ['4', 'otra', 'otro']:
            resp.message("¿En qué podemos ayudarte? ✨ Un asesor continuará contigo manualmente.")
            usuarios[numero]['estado'] = 'manual'
        else:
            resp.message("Por favor, elige una de las opciones con un número (1, 2, 3 o 4) 📌")
        return Response(str(resp), status=200, mimetype='application/xml')

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
        return Response(str(resp), status=200, mimetype='application/xml')

    # Selección de subopción
    if estado == 'cita_subopcion':
        servicio_id = usuarios[numero]['servicio']
        subopc = servicios[servicio_id]['subopciones']
        if mensaje.isdigit() and 1 <= int(mensaje) <= len(subopc):
            usuarios[numero]['subopcion'] = subopc[int(mensaje) - 1]
            usuarios[numero]['estado'] = 'cita_imagen'
            resp.message("¿Tienes un diseño que quieras compartir con nosotras para calcular mejor el tiempo de la cita? (Responde 'Sí' o 'No')")
        else:
            resp.message("Por favor, selecciona un número válido de las subopciones.")
        return Response(str(resp), status=200, mimetype='application/xml')

    # Pregunta si tiene diseño
    if estado == 'cita_imagen':
        if mensaje in ['sí', 'si']:
            usuarios[numero]['estado'] = 'cita_fecha'
            resp.message("Excelente 💖 Ahora, ¿qué día y hora prefieres para tu cita? (ejemplo: 20/09 15:00)")
        elif mensaje == 'no':
            usuarios[numero]['estado'] = 'cita_fecha'
            resp.message("No hay problema 💖. Ahora, ¿qué día y hora prefieres para tu cita? (ejemplo: 20/09 15:00)")
        else:
            resp.message("Por favor responde 'Sí' o 'No'.")
        return Response(str(resp), status=200, mimetype='application/xml')

    # Recepción de fecha y hora
    if estado == 'cita_fecha':
        usuarios[numero]['fecha_hora'] = mensaje_raw
        usuarios[numero]['estado'] = 'cita_confirmacion'
        resp.message(
            "Revisaremos nuestra agenda para verificar disponibilidad 📅.\n"
            "Danos un minuto por favor... 🙏"
        )
        return Response(str(resp), status=200, mimetype='application/xml')

    # Confirmación manual
    if estado == 'cita_confirmacion':
        if mensaje in ['sí', 'si']:
            usuarios[numero]['estado'] = 'menu'
            resp.message(
                f"✅ Tu cita ha sido agendada exitosamente!\n"
                f"Te esperamos el {usuarios[numero]['fecha_hora']} 💖\n"
                f"Gracias por elegir Spa Milena Bravo. Te enviaremos un recordatorio antes de tu cita."
            )
        elif mensaje == 'no':
            usuarios[numero]['estado'] = 'cita_fecha'
            resp.message("No hay problema 💖. Indícanos otra fecha y hora que prefieras.")
        else:
            resp.message("Por favor responde 'Sí' para confirmar o 'No' para reprogramar.")
        return Response(str(resp), status=200, mimetype='application/xml')

    return Response(str(resp), status=200, mimetype='application/xml')


# Endpoint raíz para evitar error 404 en Render
@app.route("/", methods=["GET"])
def home():
    return "Servidor corriendo en Render OK 🚀"


if __name__ == "__main__":
    app.run(port=5000, debug=True)


