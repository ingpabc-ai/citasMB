from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route('/')
def home():
    return "Chatbot Milena Bravo está en línea 🚀"

@app.route('/whatsapp', methods=['POST'])
def whatsapp_reply():
    # Captura el mensaje entrante
    incoming_msg = request.values.get('Body', '').lower()
    
    # Crea la respuesta
    resp = MessagingResponse()
    
    if 'hola' in incoming_msg:
        resp.message("¡Hola! Gracias por escribir a Milena Bravo. 😊")
    else:
        resp.message("Gracias por tu mensaje. Te responderemos pronto.")
    
    return str(resp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

