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
                    {
                        "type": "reply",
                        "reply": {
                            "id": b["id"],
                            "title": b["title"]
                        }
                    } for b in botones
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
        boton_id = None

        if msg["type"] == "text":
            texto = msg["text"]["body"].strip()

        if msg["type"] == "interactive":
            boton_id = msg["interactive"]["button_reply"]["id"]

        usuarios.setdefault(telefono, {"estado": "INICIO"})
        estado = usuarios[telefono]["estado"]

        # -------- INICIO --------
        if estado == "INICIO":
            enviar_botones(
                telefono,
                "💎 Elegí un paquete",
                [
                    {"id": "1", "title": "100 - $1.200"},
                    {"id": "2", "title": "310 - $3.200"},
                    {"id": "3", "title": "520 - $5.000"},
                    {"id": "4", "title": "1060 - $9.800"}
                ]
            )
            usuarios[telefono]["estado"] = "MENU"

        # -------- MENU --------
        elif estado == "MENU" and boton_id in PAQUETES:
            p, pr = PAQUETES[boton_id]
            usuarios[telefono].update({
                "estado": "CONFIRMAR_PAQUETE",
                "paquete": p,
                "precio": pr
            })

            enviar_botones(
                telefono,
                f"💎 {p}\n💰 {pr}",
                [
                    {"id": "CONFIRMAR_PAQUETE", "title": "Confirmar"},
                    {"id": "VOLVER_MENU", "title": "Volver"}
                ]
            )

        # -------- CONFIRMAR PAQUETE --------
        elif estado == "CONFIRMAR_PAQUETE":
            if boton_id == "CONFIRMAR_PAQUETE":
                usuarios[telefono]["estado"] = "ID"
                enviar(telefono, "🎮 Escribí tu ID del juego")

            elif boton_id == "VOLVER_MENU":
                usuarios[telefono]["estado"] = "INICIO"

        # -------- ID --------
        elif estado == "ID" and texto:
            usuarios[telefono]["id_juego"] = texto
            usuarios[telefono]["estado"] = "CONFIRMAR_ID"

            enviar_botones(
                telefono,
                f"🎮 ID ingresado:\n{text}",
                [
                    {"id": "CONFIRMAR_ID", "title": "Confirmar ID"},
                    {"id": "VOLVER_MENU", "title": "Volver"}
                ]
            )

        # -------- CONFIRMAR ID --------
        elif estado == "CONFIRMAR_ID":
            if boton_id == "CONFIRMAR_ID":
                usuarios[telefono]["estado"] = "RESUMEN"
                enviar_botones(
                    telefono,
                    f"📋 RESUMEN\n\n"
                    f"💎 {usuarios[telefono]['paquete']}\n"
                    f"💰 {usuarios[telefono]['precio']}\n"
                    f"🎮 {usuarios[telefono]['id_juego']}",
                    [
                        {"id": "PAGAR", "title": "Confirmar y pagar"},
                        {"id": "VOLVER_MENU", "title": "Volver"}
                    ]
                )

            elif boton_id == "VOLVER_MENU":
                usuarios[telefono]["estado"] = "INICIO"

        # -------- PAGO --------
        elif estado == "RESUMEN" and boton_id == "PAGAR":
            usuarios[telefono]["estado"] = "COMPROBANTE"
            enviar(telefono, "💳 Enviá el comprobante del pago 📎")

        guardar_usuarios()

    except Exception as e:
        print("ERROR:", e)

    return "EVENT_RECEIVED", 200

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
