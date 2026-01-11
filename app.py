from flask import Flask, request, render_template_string, redirect, send_file
import requests
import json
import os
from io import BytesIO

app = Flask(__name__)

# ---------------- CONFIG ----------------
VERIFY_TOKEN = "159412d596d0d2d06050a502883b08ca"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = "919152181286061"
NUMERO_PERSONAL = "543886046052"

PEDIDOS_FILE = "pedidos.json"
USUARIOS_FILE = "usuarios.json"

PAQUETES = {
    "p1": ("100 diamantes", "$1.200 ARS"),
    "p2": ("310 diamantes", "$3.200 ARS"),
    "p3": ("520 diamantes", "$5.000 ARS"),
    "p4": ("1060 diamantes", "$9.800 ARS")
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

# ---------------- WHATSAPP HELPERS ----------------
def enviar_texto(telefono, texto):
    requests.post(
        f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "messaging_product": "whatsapp",
            "to": telefono,
            "type": "text",
            "text": {"body": texto}
        }
    )

def enviar_botones(telefono, texto, botones):
    requests.post(
        f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
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
                            "reply": {"id": b["id"], "title": b["title"]}
                        } for b in botones
                    ]
                }
            }
        }
    )

def enviar_imagen(telefono, media_id):
    requests.post(
        f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "messaging_product": "whatsapp",
            "to": telefono,
            "type": "image",
            "image": {"id": media_id}
        }
    )

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
        tipo = msg["type"]

        texto = ""
        boton_id = None

        if tipo == "text":
            texto = msg["text"]["body"].strip()
        elif tipo == "interactive":
            boton_id = msg["interactive"]["button_reply"]["id"]

        usuarios.setdefault(telefono, {"estado": "INICIO"})
        estado = usuarios[telefono]["estado"]

        # ---------------- INICIO ----------------
        if estado == "INICIO":
            enviar_botones(
                telefono,
                "💎 Elegí un paquete de diamantes",
                [
                    {"id": "p1", "title": "100 💎"},
                    {"id": "p2", "title": "310 💎"},
                    {"id": "p3", "title": "520 💎"},
                ]
            )
            usuarios[telefono]["estado"] = "MENU"

        # ---------------- MENU ----------------
        elif estado == "MENU" and boton_id in PAQUETES:
            p, pr = PAQUETES[boton_id]
            usuarios[telefono].update({
                "paquete": p,
                "precio": pr,
                "estado": "CONFIRMAR_PAQUETE"
            })

            enviar_botones(
                telefono,
                f"💎 {p}\n💰 {pr}\n\n¿Confirmás el paquete?",
                [
                    {"id": "confirmar_paquete", "title": "✅ Confirmar"},
                    {"id": "volver_menu", "title": "🔁 Volver"}
                ]
            )

        # ---------------- CONFIRMAR PAQUETE ----------------
        elif estado == "CONFIRMAR_PAQUETE":
            if boton_id == "confirmar_paquete":
                usuarios[telefono]["estado"] = "ID"
                enviar_texto(telefono, "📲 Enviá tu ID del juego")
            elif boton_id == "volver_menu":
                usuarios[telefono]["estado"] = "INICIO"
                return webhook()

        # ---------------- ID ----------------
        elif estado == "ID" and texto:
            usuarios[telefono]["id_juego"] = texto
            usuarios[telefono]["estado"] = "CONFIRMAR_ID"

            enviar_botones(
                telefono,
                f"🎮 ID ingresado:\n{text}\n\n¿Es correcto?",
                [
                    {"id": "confirmar_id", "title": "✅ Confirmar"},
                    {"id": "volver_menu", "title": "🔁 Volver"}
                ]
            )

        # ---------------- CONFIRMAR ID ----------------
        elif estado == "CONFIRMAR_ID":
            if boton_id == "confirmar_id":
                usuarios[telefono]["estado"] = "RESUMEN"
                enviar_botones(
                    telefono,
                    f"📋 RESUMEN FINAL\n\n"
                    f"💎 {usuarios[telefono]['paquete']}\n"
                    f"💰 {usuarios[telefono]['precio']}\n"
                    f"🎮 {usuarios[telefono]['id_juego']}",
                    [
                        {"id": "pagar", "title": "💳 Pagar"},
                        {"id": "volver_menu", "title": "🔁 Cancelar"}
                    ]
                )

        # ---------------- RESUMEN ----------------
        elif estado == "RESUMEN" and boton_id == "pagar":
            usuarios[telefono]["estado"] = "COMPROBANTE"
            enviar_texto(telefono, "📎 Enviá el comprobante de pago")

        # ---------------- COMPROBANTE ----------------
        elif estado == "COMPROBANTE" and tipo in ["image", "document"]:
            media_id = msg[tipo]["id"]

            enviar_texto(telefono, "✅ Comprobante recibido, un asesor continuará tu pedido 💎")
            enviar_imagen(NUMERO_PERSONAL, media_id)

            usuarios[telefono]["estado"] = "HUMANO"

        guardar_usuarios()

    except Exception as e:
        print("ERROR:", e)

    return "EVENT_RECEIVED", 200

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))





