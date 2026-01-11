from flask import Flask, request, render_template_string, redirect, send_file
import requests
import json
import os
from io import BytesIO

app = Flask(__name__)

# ---------------- CONFIGURACIÓN ----------------
VERIFY_TOKEN = "159412d596d0d2d06050a502883b08ca"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = "919152181286061"
NUMERO_PERSONAL = "+543886046052"

PEDIDOS_FILE = "pedidos.json"
USUARIOS_FILE = "usuarios.json"

PAQUETES = {
    "1": ("100 diamantes", "$3400 ARS"),
    "2": ("310 diamantes", "$3.200 ARS"),
    "3": ("520 diamantes", "$5.000 ARS"),
    "4": ("1060 diamantes", "$9.800 ARS")
}

# ---------------- PERSISTENCIA ----------------
def cargar_usuarios():
    if os.path.exists(USUARIOS_FILE):
        with open(USUARIOS_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_usuarios():
    with open(USUARIOS_FILE, "w") as f:
        json.dump(usuarios, f, indent=4)

usuarios = cargar_usuarios()

# ---------------- FUNCIONES ----------------
def enviar(telefono, texto):
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
    pedidos = []
    if os.path.exists(PEDIDOS_FILE):
        with open(PEDIDOS_FILE, "r") as f:
            pedidos = json.load(f)
    pedidos.append(pedido)
    with open(PEDIDOS_FILE, "w") as f:
        json.dump(pedidos, f, indent=4)

def obtener_url_media(media_id):
    url = f"https://graph.facebook.com/v18.0/{media_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get("url")
    return None

def reenviar_a_personal(telefono_cliente, paquete, precio, id_juego, tipo_comprobante, media_id=None):
    enviar(
        NUMERO_PERSONAL,
        f"📦 Nuevo pedido\nCliente: {telefono_cliente}\n💎 {paquete}\n💰 {precio}\n🎮 ID: {id_juego}"
    )
    if media_id:
        media_url = obtener_url_media(media_id)
        if media_url:
            enviar(NUMERO_PERSONAL, f"📎 Comprobante: {media_url}")

# ---------------- PANEL HTML ----------------
PANEL_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Panel Modo Humano</title>
<style>
body { font-family: Arial; background:#f0f2f5; padding:20px; }
.cliente { background:#fff; padding:15px; margin-bottom:20px; border-radius:12px; }
.mensajes { max-height:200px; overflow:auto; background:#fafafa; padding:10px; border-radius:8px; }
.mensaje-tu { color:#0d6efd; font-weight:bold; }
img { max-width:200px; margin-top:10px; border-radius:8px; }
</style>
</head>
<body>
<h2>Modo Humano</h2>
{% for tel, data in usuarios.items() %}
{% if data.estado == 'HUMANO' %}
<div class="cliente">
<h3>{{ tel }}</h3>
<div class="mensajes">
{% for m in data.get('mensajes_humanos', []) %}
<div class="{{ 'mensaje-tu' if m.startswith('Tú:') else '' }}">{{ m }}</div>
{% endfor %}
</div>

{% if data.get('comprobante') %}
<p><strong>Comprobante:</strong></p>
<img src="/media/{{ data.comprobante.media_id }}">
{% endif %}

<form action="/responder" method="post">
<input type="hidden" name="telefono" value="{{ tel }}">
<input type="text" name="mensaje" placeholder="Responder">
<button>Enviar</button>
</form>
</div>
{% endif %}
{% endfor %}
</body>
</html>
"""

# ---------------- MEDIA ----------------
@app.route("/media/<media_id>")
def media(media_id):
    url = f"https://graph.facebook.com/v18.0/{media_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return "Error", 404
    media_url = r.json().get("url")
    media_r = requests.get(media_url, headers=headers)
    return send_file(BytesIO(media_r.content), mimetype=media_r.headers.get("Content-Type"))

# ---------------- WEBHOOK ----------------
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Forbidden", 403

    data = request.get_json()
    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        telefono = msg["from"]
        texto = msg.get("text", {}).get("body", "").strip().lower()

        if telefono not in usuarios:
            usuarios[telefono] = {"estado": "INICIO"}
            guardar_usuarios()

        estado = usuarios[telefono]["estado"]

        if estado == "INICIO":
            enviar(telefono,
                "💎 Diamantes Free Fire\n\n"
                "1️⃣ 100 – $1.200\n"
                "2️⃣ 310 – $3.200\n"
                "3️⃣ 520 – $5.000\n"
                "4️⃣ 1060 – $9.800")
            usuarios[telefono]["estado"] = "MENU"
            guardar_usuarios()

        elif estado == "MENU" and texto in PAQUETES:
            paquete, precio = PAQUETES[texto]
            usuarios[telefono].update({"estado": "ID", "paquete": paquete, "precio": precio})
            guardar_usuarios()
            enviar(telefono, "📲 Enviá tu ID de Free Fire")

        elif estado == "ID":
            usuarios[telefono].update({"estado": "CONFIRMAR", "id_juego": texto})
            guardar_usuarios()
            enviar(telefono, f"Confirmar pedido {usuarios[telefono]['paquete']} por {usuarios[telefono]['precio']}.\nEscribí SI")

        elif estado == "CONFIRMAR" and texto == "si":
            usuarios[telefono]["estado"] = "COMPROBANTE"
            guardar_usuarios()
            enviar(telefono, "📎 Enviá el comprobante")

        elif estado == "COMPROBANTE":
            tipo = msg.get("type")
            media_id = msg.get(tipo, {}).get("id") if tipo in ["image", "document"] else None
            if media_id:
                pedido = {
                    "cliente": telefono,
                    "paquete": usuarios[telefono]["paquete"],
                    "precio": usuarios[telefono]["precio"],
                    "id_juego": usuarios[telefono]["id_juego"],
                    "tipo_comprobante": tipo,
                    "media_id": media_id
                }
                guardar_pedido(pedido)
                usuarios[telefono].update({
                    "estado": "HUMANO",
                    "comprobante": pedido,
                    "mensajes_humanos": []
                })
                guardar_usuarios()
                reenviar_a_personal(**pedido)
                enviar(telefono, "✅ Comprobante recibido. Te atendemos manualmente.")

        elif estado == "HUMANO":
            usuarios[telefono].setdefault("mensajes_humanos", []).append(f"Cliente: {texto}")
            guardar_usuarios()

    except Exception as e:
        print("ERROR:", e)

    return "EVENT_RECEIVED", 200

# ---------------- PANEL ----------------
@app.route("/panel")
def panel():
    return render_template_string(PANEL_HTML, usuarios=usuarios)

@app.route("/responder", methods=["POST"])
def responder():
    tel = request.form["telefono"]
    msg = request.form["mensaje"]
    enviar(tel, msg)
    usuarios[tel]["mensajes_humanos"].append(f"Tú: {msg}")
    guardar_usuarios()
    return redirect("/panel")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))




