from flask import Flask, request, render_template_string, redirect
import requests
import json
import os
from io import BytesIO
from flask import send_file

app = Flask(__name__)

# ---------------- CONFIGURACIÓN ----------------
VERIFY_TOKEN = "159412d596d0d2d06050a502883b08ca"
ACCESS_TOKEN = "EAAMDNH8HasoBQTFY1glfgeZBJd3wVatZA12w7pq4AWSKZCOhYVkAMfahofNLQIYjePGBo9UJTX7Ii9Hu1r4pftQdcm3FqyIb1nAexnxBrOWqkaIDIe48UJ9sCJfMYC1yBPmN5RMkW1XYC2W4L2AbJjb1bTLQnIllIgg8KZABWDAjq3AwyCJg6xCq1xBuUSJvN4JFwivQR8ZAa8RrRAwW3uuLV6P6IYvJDYLzWTwSh4JS1snD5947xRj0VzzQO1ZB2a8ordTpSmYpe5dhIm4pbw"
PHONE_NUMBER_ID = "919152181286061"
NUMERO_PERSONAL = "+543886046052"  # tu número personal en formato internacional
PEDIDOS_FILE = "pedidos.json"

usuarios = {}

PAQUETES = {
    "1": ("100 diamantes", "$1.200 ARS"),
    "2": ("310 diamantes", "$3.200 ARS"),
    "3": ("520 diamantes", "$5.000 ARS"),
    "4": ("1060 diamantes", "$9.800 ARS")
}

# ---------------- FUNCIONES ----------------
def enviar(telefono, texto):
    """Envía mensaje de texto por WhatsApp API"""
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "text": {"body": texto}
    }
    r = requests.post(url, json=payload, headers=headers)
    print("📤 ENVÍO:", r.status_code, r.text)

def guardar_pedido(pedido):
    """Guarda pedido en JSON"""
    if os.path.exists(PEDIDOS_FILE):
        with open(PEDIDOS_FILE, "r") as f:
            pedidos = json.load(f)
    else:
        pedidos = []
    pedidos.append(pedido)
    with open(PEDIDOS_FILE, "w") as f:
        json.dump(pedidos, f, indent=4)

def obtener_url_media(media_id):
    """Obtiene URL temporal del media enviado por el cliente"""
    url = f"https://graph.facebook.com/v18.0/{media_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        return data.get("url")
    return None

def reenviar_a_personal(telefono_cliente, paquete, precio, id_juego, tipo_comprobante, media_id=None):
    """Reenvía pedido y comprobante al número personal"""
    mensaje = f"Nuevo pedido de {telefono_cliente}:\n💎 Paquete: {paquete}\n💰 Precio: {precio}\n🎮 ID: {id_juego}"
    enviar(NUMERO_PERSONAL, mensaje)
    if media_id:
        # reenviamos la URL temporal del comprobante
        media_url = obtener_url_media(media_id)
        if media_url:
            if tipo_comprobante == "image":
                enviar(NUMERO_PERSONAL, f"Comprobante (imagen): {media_url}")
            else:
                enviar(NUMERO_PERSONAL, f"Comprobante (PDF): {media_url}")

# ---------------- PANEL HTML ----------------
PANEL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Panel Modo Humano</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f0f2f5; margin: 20px; }
        h2 { text-align: center; color: #333; }
        .cliente { border-radius: 12px; background-color: #fff; padding: 15px; margin-bottom: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
        .cliente h3 { color: #0d6efd; }
        .mensajes { max-height: 200px; overflow-y: auto; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background-color: #f9f9f9; margin-bottom: 10px; }
        .mensaje-cliente { color: #333; margin: 5px 0; }
        .mensaje-tu { color: #0d6efd; font-weight: bold; margin: 5px 0; }
        input[type="text"] { width: 70%; padding: 8px; border-radius: 8px; border: 1px solid #ccc; margin-right: 5px; }
        button { padding: 8px 15px; border: none; background-color: #0d6efd; color: white; border-radius: 8px; cursor: pointer; }
        button:hover { background-color: #0056b3; }
        img { max-width: 200px; border-radius: 8px; margin-top: 5px; }
    </style>
</head>
<body>
<h2>Modo Humano - Responder a Clientes</h2>
{% for tel, data in usuarios.items() %}
    {% if data.estado == 'HUMANO' %}
    <div class="cliente">
        <h3>Cliente: {{ tel }}</h3>
        <div class="mensajes">
            {% for msg in data.get('mensajes_humanos', []) %}
                {% if msg.startswith("Tú:") %}
                    <div class="mensaje-tu">{{ msg }}</div>
                {% else %}
                    <div class="mensaje-cliente">{{ msg }}</div>
                {% endif %}
            {% endfor %}
        </div>
        {% if data.get('comprobante') %}
            <p><strong>Comprobante:</strong></p>
            {% if data.comprobante.tipo_comprobante == 'image' %}
                <img src="/media/{{ data.comprobante.media_id }}">
            {% elif data.comprobante.tipo_comprobante == 'document' %}
                <a href="/media/{{ data.comprobante.media_id }}" target="_blank">Ver PDF</a>
            {% endif %}
        {% endif %}
        <form action="/responder" method="post">
            <input type="hidden" name="telefono" value="{{ tel }}">
            <input type="text" name="mensaje" placeholder="Escribí tu respuesta">
            <button type="submit">Enviar</button>
        </form>
    </div>
    {% endif %}
{% endfor %}
</body>
</html>
"""

# ---------------- MEDIA ROUTE ----------------
@app.route("/media/<media_id>")
def media(media_id):
    # Descarga el media desde WhatsApp Cloud API
    url = f"https://graph.facebook.com/v18.0/{media_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return "No se pudo obtener el media", 404
    media_url = r.json().get("url")
    
    media_r = requests.get(media_url, headers=headers)
    if media_r.status_code != 200:
        return "No se pudo descargar el media", 404

    return send_file(BytesIO(media_r.content), mimetype=media_r.headers.get('Content-Type'))

# ---------------- WEBHOOK ----------------
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Forbidden", 403

    data = request.get_json()
    print("📥 DATA:", data)

    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        telefono = msg["from"]
        texto = msg.get("text", {}).get("body", "").strip().lower()
        estado = usuarios.get(telefono, {}).get("estado", "INICIO")

        if telefono not in usuarios:
            usuarios[telefono] = {"estado": "INICIO"}
            estado = "INICIO"

        # ---------- Flujo automático ----------
        if estado == "INICIO":
            enviar(
                telefono,
                "💎 *Diamantes Free Fire*\n\n"
                "Elegí una opción:\n"
                "1️⃣ 100 diamantes – $1.200\n"
                "2️⃣ 310 diamantes – $3.200\n"
                "3️⃣ 520 diamantes – $5.000\n"
                "4️⃣ 1060 diamantes – $9.800"
            )
            usuarios[telefono]["estado"] = "MENU"

        elif estado == "MENU" and texto in PAQUETES:
            paquete, precio = PAQUETES[texto]
            usuarios[telefono].update({
                "estado": "ID",
                "paquete": paquete,
                "precio": precio
            })
            enviar(telefono, "📲 Enviá tu *ID de Free Fire* (solo números):")

        elif estado == "ID":
            usuarios[telefono]["id_juego"] = texto
            usuarios[telefono]["estado"] = "CONFIRMAR"
            enviar(
                telefono,
                f"✅ *Confirmación del pedido*\n\n"
                f"💎 Paquete: {usuarios[telefono]['paquete']}\n"
                f"💰 Precio: {usuarios[telefono]['precio']}\n"
                f"🎮 ID: {texto}\n\n"
                f"Escribí *SI* para confirmar"
            )

        elif estado == "CONFIRMAR" and texto == "si":
            enviar(
                telefono,
                "💰 *Pedido confirmado*\n"
                "📎 Enviá ahora el *comprobante de pago* (foto o PDF)."
            )
            usuarios[telefono]["estado"] = "COMPROBANTE"

        elif estado == "COMPROBANTE":
            tipo = msg.get("type")
            media_id = None
            if tipo == "image":
                media_id = msg["image"]["id"]
            elif tipo == "document":
                media_id = msg["document"]["id"]
            
            if media_id:
                pedido = {
                    "cliente": telefono,
                    "paquete": usuarios[telefono]['paquete'],
                    "precio": usuarios[telefono]['precio'],
                    "id_juego": usuarios[telefono]['id_juego'],
                    "tipo_comprobante": tipo,
                    "media_id": media_id
                }
                guardar_pedido(pedido)
                usuarios[telefono]["estado"] = "HUMANO"
                usuarios[telefono]["comprobante"] = pedido
                if "mensajes_humanos" not in usuarios[telefono]:
                    usuarios[telefono]["mensajes_humanos"] = []
                enviar(
                    telefono,
                    "✅ *Comprobante recibido*\n"
                    "💎 Tu pedido será validado y recibirás los diamantes pronto.\n"
                    "Ahora podés hacer consultas y responderemos manualmente desde el panel."
                )
                # Reenviar al número personal
                reenviar_a_personal(
                    telefono_cliente=telefono,
                    paquete=usuarios[telefono]['paquete'],
                    precio=usuarios[telefono]['precio'],
                    id_juego=usuarios[telefono]['id_juego'],
                    tipo_comprobante=tipo,
                    media_id=media_id
                )
            else:
                enviar(telefono, "⚠️ Enviá el *comprobante* como foto o PDF.")

        elif estado == "HUMANO":
            if "mensajes_humanos" not in usuarios[telefono]:
                usuarios[telefono]["mensajes_humanos"] = []
            usuarios[telefono]["mensajes_humanos"].append(f"Cliente: {texto}")

    except Exception as e:
        print("❌ ERROR:", e)

    return "EVENT_RECEIVED", 200

# ---------------- PANEL HUMANO ----------------
@app.route("/panel")
def panel():
    return render_template_string(PANEL_HTML, usuarios=usuarios)

@app.route("/responder", methods=["POST"])
def responder():
    telefono = request.form["telefono"]
    mensaje = request.form["mensaje"]
    if telefono and mensaje:
        enviar(telefono, mensaje)
        if "mensajes_humanos" not in usuarios[telefono]:
            usuarios[telefono]["mensajes_humanos"] = []
        usuarios[telefono]["mensajes_humanos"].append(f"Tú: {mensaje}")
    return redirect("/panel")

# ---------------- EJECUCIÓN ----------------
if __name__ == "__main__":
    app.run(port=5000, use_reloader=False)
