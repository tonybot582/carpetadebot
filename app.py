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
NUMERO_PERSONAL = "543886046052"

PEDIDOS_FILE = "pedidos.json"
USUARIOS_FILE = "usuarios.json"

PAQUETES = {
    "1": ("100 diamantes", "$1.200 ARS"),
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

# ---------------- WHATSAPP ----------------
def enviar(telefono, texto):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "text",
        "text": {"body": texto}
    }
    requests.post(url, json=payload, headers=headers)

def enviar_boton_menu(telefono):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "¿Querés volver al menú?"},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "VOLVER_MENU",
                            "title": "🔙 Volver al menú"
                        }
                    }
                ]
            }
        }
    }
    requests.post(url, json=payload, headers=headers)

def enviar_imagen(telefono, media_id):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "image",
        "image": {"id": media_id}
    }
    requests.post(url, json=payload, headers=headers)

def obtener_url_media(media_id):
    url = f"https://graph.facebook.com/v18.0/{media_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.get(url, headers=headers)
    return r.json().get("url")

# ---------------- PANEL HUMANO ----------------
PANEL_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Panel Humano</title>
<style>
body { font-family: Arial; background:#f0f2f5; padding:20px; }
.cliente { background:#fff; padding:15px; margin-bottom:20px; border-radius:12px; }
.mensajes { max-height:200px; overflow:auto; background:#fafafa; padding:10px; border-radius:8px; }
button { margin-top:5px; }
</style>
</head>
<body>
<h2>MENSAJES DE CLIENTES</h2>

{% for tel, data in usuarios.items() %}
{% if data.estado in ['HUMANO','TOMADO'] %}
<div class="cliente">
<h3>{{ tel }} - {{ data.estado }}</h3>

<div class="mensajes">
{% for m in data.get('mensajes_humanos', []) %}
<div>{{ m }}</div>
{% endfor %}
</div>

{% if data.get('comprobante') %}
<p><strong>Comprobante:</strong></p>
<img src="/media/{{ data.comprobante.media_id }}" width="200">
{% endif %}

{% if data.estado == 'HUMANO' %}
<form action="/tomar" method="post">
<input type="hidden" name="telefono" value="{{ tel }}">
<button>🧑‍💼 Tomar conversación</button>
</form>
{% endif %}

{% if data.estado == 'TOMADO' %}
<form action="/responder" method="post">
<input type="hidden" name="telefono" value="{{ tel }}">
<input name="mensaje" placeholder="Responder">
<button>Enviar</button>
</form>
{% endif %}
</div>
{% endif %}
{% endfor %}
</body>
</html>
"""

# ---------------- MEDIA ----------------
@app.route("/media/<media_id>")
def media(media_id):
    url = obtener_url_media(media_id)
    r = requests.get(url, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    return send_file(BytesIO(r.content), mimetype=r.headers.get("Content-Type"))

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

        texto = msg.get("text", {}).get("body", "").strip()
        boton_id = None

        if msg["type"] == "interactive":
            boton_id = msg["interactive"]["button_reply"]["id"]

        usuarios.setdefault(telefono, {"estado": "INICIO"})
        estado = usuarios[telefono]["estado"]

        # 🔙 BOTÓN GLOBAL
        if boton_id == "VOLVER_MENU":
            usuarios[telefono]["estado"] = "MENU"
            enviar(
                telefono,
                "💎 Diamantes Free Fire\n\n"
                "1️⃣ 100  – $1.200\n"
                "2️⃣ 310  – $3.200\n"
                "3️⃣ 520  – $5.000\n"
                "4️⃣ 1060 – $9.800"
            )
            guardar_usuarios()
            return "EVENT_RECEIVED", 200

        # -------- FLUJO ORIGINAL --------
        if estado == "INICIO":
            enviar(
                telefono,
                "💎 Diamantes Free Fire\n\n"
                "1️⃣ 100  – $1.200\n"
                "2️⃣ 310  – $3.200\n"
                "3️⃣ 520  – $5.000\n"
                "4️⃣ 1060 – $9.800"
            )
            usuarios[telefono]["estado"] = "MENU"

        elif estado == "MENU" and texto in PAQUETES:
            p, pr = PAQUETES[texto]
            usuarios[telefono].update({"estado": "CONFIRMAR_PAQUETE", "paquete": p, "precio": pr})
            enviar(
                telefono,
                f"💎 Paquete elegido:\n{p}\n💰 Precio: {pr}\n\n"
                "1️⃣ Confirmar paquete\n"
                "2️⃣ Volver al menú"
            )
            enviar_boton_menu(telefono)

        elif estado == "CONFIRMAR_PAQUETE":
            if texto == "1":
                usuarios[telefono]["estado"] = "ID"
                enviar(telefono, "📲 Enviá tu ID del juego")
                enviar_boton_menu(telefono)

            elif texto == "2":
                usuarios[telefono]["estado"] = "MENU"

        elif estado == "ID" and texto:
            usuarios[telefono]["id_juego"] = texto
            usuarios[telefono]["estado"] = "CONFIRMAR_ID"
            enviar(
                telefono,
                f"🎮 Tu ID es:\n{text}\n\n"
                "1️⃣ Confirmar ID\n"
                "2️⃣ Volver al menú"
            )
            enviar_boton_menu(telefono)

        guardar_usuarios()

    except Exception as e:
        print("ERROR:", e)

    return "EVENT_RECEIVED", 200

# ---------------- PANEL ----------------
@app.route("/panel")
def panel():
    return render_template_string(PANEL_HTML, usuarios=usuarios)

@app.route("/tomar", methods=["POST"])
def tomar():
    tel = request.form["telefono"]
    usuarios[tel]["estado"] = "TOMADO"
    guardar_usuarios()
    return redirect("/panel")

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
