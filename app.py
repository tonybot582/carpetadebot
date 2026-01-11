from flask import Flask, request, render_template_string, redirect, send_file
import requests, json, os, re
from io import BytesIO

app = Flask(__name__)

# ---------------- CONFIG ----------------
VERIFY_TOKEN = "159412d596d0d2d06050a502883b08ca"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = "919152181286061"
NUMERO_PERSONAL = "543886046052"

USUARIOS_FILE = "usuarios.json"
PEDIDOS_FILE = "pedidos.json"

PAQUETES = {
    "100 diamantes": ("100 diamantes", "$1.200 ARS"),
    "310 diamantes": ("310 diamantes", "$3.200 ARS"),
    "520 diamantes": ("520 diamantes", "$5.000 ARS"),
    "1060 diamantes": ("1060 diamantes", "$9.800 ARS")
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

# ---------------- WHATSAPP SEND ----------------
def enviar_texto(tel, texto):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": tel,
        "type": "text",
        "text": {"body": texto}
    }
    requests.post(url, json=payload, headers=headers)

def enviar_botones(tel, texto, botones):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": tel,
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

def enviar_imagen(tel, media_id):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": tel,
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
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" not in value:
            return "EVENT_RECEIVED", 200

        msg = value["messages"][0]
        tel = msg["from"]

        texto = ""

        if msg["type"] == "text":
            texto = msg["text"]["body"].strip()

        elif msg["type"] == "interactive":
            if msg["interactive"]["type"] == "button_reply":
                texto = msg["interactive"]["button_reply"]["title"]

        usuarios.setdefault(tel, {"estado": "INICIO"})
        estado = usuarios[tel]["estado"]

        # -------- VOLVER AL MENU GLOBAL --------
        if texto.lower() in ["menu", "volver al menú", "volver al menu"]:
            usuarios[tel] = {"estado": "MENU"}
            enviar_botones(
                tel,
                "💎 Elegí un paquete:",
                list(PAQUETES.keys())
            )
            guardar_usuarios()
            return "EVENT_RECEIVED", 200

        # -------- INICIO --------
        if estado == "INICIO":
            usuarios[tel]["estado"] = "MENU"
            enviar_botones(
                tel,
                "💎 Elegí un paquete:",
                list(PAQUETES.keys())
            )

        # -------- MENU --------
        elif estado == "MENU" and texto in PAQUETES:
            p, pr = PAQUETES[texto]
            usuarios[tel].update({
                "estado": "ID",
                "paquete": p,
                "precio": pr
            })
            enviar_texto(tel, "📲 Enviá tu ID del juego (solo números)")

        # -------- ID --------
        elif estado == "ID":
            if not re.fullmatch(r"\d{6,15}", texto):
                enviar_texto(tel, "❌ El ID debe ser SOLO números.\nReenviá tu ID.")
                return "EVENT_RECEIVED", 200

            usuarios[tel]["id_juego"] = texto
            usuarios[tel]["estado"] = "CONFIRMAR_ID"

            enviar_botones(
                tel,
                f"🎮 ID ingresado:\n{text}",
                ["Confirmar ID", "Volver al menú"]
            )

        # -------- CONFIRMAR ID --------
        elif estado == "CONFIRMAR_ID":
            if texto == "Confirmar ID":
                usuarios[tel]["estado"] = "RESUMEN"
                enviar_botones(
                    tel,
                    f"📋 RESUMEN\n\n"
                    f"💎 {usuarios[tel]['paquete']}\n"
                    f"💰 {usuarios[tel]['precio']}\n"
                    f"🎮 ID: {usuarios[tel]['id_juego']}",
                    ["Confirmar y pagar", "Volver al menú"]
                )

        # -------- RESUMEN --------
        elif estado == "RESUMEN":
            if texto == "Confirmar y pagar":
                usuarios[tel]["estado"] = "COMPROBANTE"
                enviar_texto(tel, "💳 Realizá el pago y enviá el comprobante 📎")

        guardar_usuarios()

    except Exception as e:
        print("ERROR:", e)

    return "EVENT_RECEIVED", 200

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
