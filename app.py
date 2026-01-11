from flask import Flask, request, render_template_string, redirect, send_file
import requests
import json
import os
from io import BytesIO
import re

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
def enviar_texto(telefono, texto):
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

def enviar_botones(telefono, texto, botones):
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
            "body": {"text": texto},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b, "title": b}}
                    for b in botones
                ]
            }
        }
    }
    requests.post(url, json=payload, headers=headers)

def enviar_imagen(telefono, media_id):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "image",
        "image": {"id": media_id}
    }
    requests.post(url, json=payload, headers=headers)

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

        texto = ""
        if msg["type"] == "text":
            texto = msg["text"]["body"].strip()
        elif msg["type"] == "button":
            texto = msg["button"]["text"]

        usuarios.setdefault(telefono, {"estado": "INICIO"})
        estado = usuarios[telefono]["estado"]

        # ---- VOLVER AL MENU GLOBAL ----
        if texto.lower() in ["menu", "volver al menú", "volver al menu", "🏠 Volver al menú"]:
            usuarios[telefono] = {"estado": "MENU"}
            enviar_botones(
                telefono,
                "💎 Elegí un paquete:",
                ["1️⃣ 100", "2️⃣ 310", "3️⃣ 520", "4️⃣ 1060"]
            )
            guardar_usuarios()
            return "EVENT_RECEIVED", 200

        # ---- INICIO ----
        if estado == "INICIO":
            usuarios[telefono]["estado"] = "MENU"
            enviar_botones(
                telefono,
                "💎 Elegí un paquete:",
                ["1️⃣ 100", "2️⃣ 310", "3️⃣ 520", "4️⃣ 1060"]
            )

        # ---- MENU ----
        elif estado == "MENU" and texto[0] in PAQUETES:
            p, pr = PAQUETES[texto[0]]
            usuarios[telefono].update({
                "estado": "ID",
                "paquete": p,
                "precio": pr
            })
            enviar_texto(
                telefono,
                "📲 Enviá tu ID del juego (solo números)"
            )

        # ---- ID ----
        elif estado == "ID":
            if not re.fullmatch(r"\d{6,15}", texto):
                enviar_texto(
                    telefono,
                    "❌ El ID debe ser SOLO NÚMEROS.\nVolvé a enviarlo correctamente."
                )
                return "EVENT_RECEIVED", 200

            usuarios[telefono]["id_juego"] = texto
            usuarios[telefono]["estado"] = "CONFIRMAR_ID"

            enviar_botones(
                telefono,
                f"🎮 ID ingresado:\n👉 {texto}",
                ["✅ Confirmar ID", "🏠 Volver al menú"]
            )

        # ---- CONFIRMAR ID ----
        elif estado == "CONFIRMAR_ID":
            if "Confirmar" in texto:
                usuarios[telefono]["estado"] = "RESUMEN"
                enviar_botones(
                    telefono,
                    f"📋 RESUMEN\n\n"
                    f"💎 {usuarios[telefono]['paquete']}\n"
                    f"💰 {usuarios[telefono]['precio']}\n"
                    f"🎮 ID: {usuarios[telefono]['id_juego']}",
                    ["💳 Pagar", "🏠 Volver al menú"]
                )

        # ---- RESUMEN ----
        elif estado == "RESUMEN":
            if "Pagar" in texto:
                usuarios[telefono]["estado"] = "COMPROBANTE"
                enviar_texto(
                    telefono,
                    "💳 Realizá el pago y enviá el comprobante 📎"
                )

        guardar_usuarios()

    except Exception as e:
        print("ERROR:", e)

    return "EVENT_RECEIVED", 200

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

