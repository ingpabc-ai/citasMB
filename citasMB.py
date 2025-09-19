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

@app.route("/whatsapp", methods=['POST'])
def whatsapp_bot():
    numero = request.form.get('From')
    mensaje = request.form.get('Body').strip().lower()
    resp = MessagingResponse()

    # Primer contacto
    if numero not in usuarios:
        usuarios[numero] = {'estado': 'inicio'}
        resp.message(
            "¡Hola! ¡Estamos felices de tenerte por aquí! 😊\n\n"
            "Soy un asistente virtual de Spa Milena Bravo y estoy lista para ayudarte a conseguir las uñas de tus sueños.\n\n"
            "Para darte una mejor atención, ¿me dices tu nombre, por favor?"
        )
        return str(resp)

    estado = usuarios[numero]['estado']

    # Guardar nombre
    if estado == 'inicio':
        usuarios[numero]['nombre'] = mensaje.title()
        usuarios[numero]['estado'] = 'menu'
        resp.message(
            f"¡Encantada de conocerte, {mensaje.title()}! 😍\n\n"
            "¿En qué puedo ayudarte hoy?\n"
            "1️⃣ Pedir cita\n"
            "2️⃣ Ver dirección\n"
            "3️⃣ Instagram\n"
            "4️⃣ Otra pregunta"
        )
    
    # Menú principal
    elif estado == 'menu':
        if mensaje in ['1', 'pedir cita']:
            usuarios[numero]['estado'] = 'cita_servicio'
            resp.message("¡Perfecto! 💅 Vamos a agendar tu cita.\nEstos son nuestros servicios:\n" +
                         "\n".join([f"{k}️⃣ {v['nombre']}" for k,v in servicios.items()]))
        elif mensaje in ['2', 'dirección']:
            resp.message("Nuestra dirección es: Calle 53 #78-61. Barrio Los Colores, Medellín.")
        elif mensaje in ['3', 'instagram']:
            resp.message("Nuestro Instagram es: @milenabravo.co")
        else:
            resp.message("Cuéntame, ¿en qué puedo ayudarte?")

    # Selección de servicio
    elif estado == 'cita_servicio':
        if mensaje in servicios.keys():
            usuarios[numero]['servicio'] = mensaje
            usuarios[numero]['estado'] = 'cita_subopcion'
            subopc = servicios[mensaje]['subopciones']
            resp.message("Elegiste: " + servicios[mensaje]['nombre'] + "\n"
                         "Ahora elige una opción:\n" +
                         "\n".join([f"{i+1}️⃣ {subopc[i]}" for i in range(len(subopc))]))
        else:
            resp.message("Por favor, selecciona un número válido del servicio.")

    # Selección de subopción
    elif estado == 'cita_subopcion':
        servicio_id = usuarios[numero]['servicio']
        subopc = servicios[servicio_id]['subopciones']
        if mensaje in ['1', '2', '3', '4'] and int(mensaje)-1 < len(subopc):
            usuarios[numero]['subopcion'] = subopc[int(mensaje)-1]
            usuarios[numero]['estado'] = 'cita_fecha'
            resp.message("Excelente 💖 Ahora, ¿qué día y hora prefieres para tu cita? (ejemplo: 20/09 15:00)")
        else:
            resp.message("Por favor, selecciona un número válido de las subopciones.")

    # Recepción de fecha y hora
    elif estado == 'cita_fecha':
        # Guardar fecha y hora en formato simple
        usuarios[numero]['fecha_hora'] = mensaje
        usuarios[numero]['estado'] = 'cita_confirmacion'
        resp.message(
            f"Perfecto 😍\nHas solicitado:\n"
            f"Servicio: {servicios[usuarios[numero]['servicio']]['nombre']}\n"
            f"Detalle: {usuarios[numero]['subopcion']}\n"
            f"Fecha/Hora: {mensaje}\n\n"
            "Ahora, por favor confirma si quieres agendar esta cita escribiendo 'Sí', o 'No' para cancelar."
        )

    # Confirmación manual
    elif estado == 'cita_confirmacion':
        if mensaje in ['sí', 'si']:
            usuarios[numero]['estado'] = 'menu'
            # Aquí podrías integrar la creación de evento en Google Calendar
            resp.message(
                f"✅ Tu cita ha sido agendada exitosamente!\n"
                f"Te esperamos el {usuarios[numero]['fecha_hora']} 💖\n"
                f"Gracias por elegir Spa Milena Bravo. Te enviaremos un recordatorio antes de tu cita."
            )
        else:
            usuarios[numero]['estado'] = 'menu'
            resp.message("Tu cita ha sido cancelada. Si deseas, puedes iniciar de nuevo el proceso.")

    return str(resp)

if __name__ == "__main__":
    app.run(port=5000, debug=True)
