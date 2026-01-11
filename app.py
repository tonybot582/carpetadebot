from flask import Flask, request
import requests
import json

app = Flask(__name__)

# ================== CONFIG ==================
ACCESS_TOKEN = "TU_ACCESS_TOKEN"
PHONE_NUMBER_ID = "TU_PHONE_NUMBER_ID"
VERIFY_TOKEN = "TU_VERIFY_TOKEN"

URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

usuarios = {}

# ================== HELPERS ==================
def enviar_texto(telefono, texto):
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "text",
        "text": {"body": texto}
    }
    requests.post(URL, headers=HEADERS, json=payload)

def enviar_botones(telefono, texto, botones):
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
    requests.post(URL, headers=HEADERS, json=payload)

# ================== WEBHOOK ==================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token inválido", 403

    data = request.json
    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        telefono = msg["from"]
        tipo = msg["type"]

        texto = ""
        boton_id = None

        if tipo == "text":
            texto = msg["text"]["body"].strip()

        if tipo == "interactive":
            boton_id = msg["interactive"]["button_reply"]["id"]

        if telefono not in usuarios:
            usuarios[telefono] = {"estado": "INICIO"}

        estado = usuarios[telefono]["estado"]

        # ================== INICIO ==================
        if estado == "INICIO":
            usuarios[telefono]["estado"] = "PAQUETE"
            enviar_botones(
                telefono,
                "💎 Elegí un paquete de diamantes",
                [
                    {"id": "p1", "title": "100 💎 - $1200"},
                    {"id": "p2", "title": "310 💎 - $3200"},
                    {"id": "p3", "title": "520 💎 - $5000"},
                    {"id": "p4", "title": "1060 💎 - $9800"},
                ]
            )

        # ================== PAQUETE ==================
        elif estado == "PAQUETE" and boton_id:
            paquetes = {
                "p1": ("100 Diamantes", "$1200"),
                "p2": ("310 Diamantes", "$3200"),
                "p3": ("520 Diamantes", "$5000"),
                "p4": ("1060 Diamantes", "$9800"),
            }

            if boton_id in paquetes:
                usuarios[telefono]["paquete"], usuarios[telefono]["precio"] = paquetes[boton_id]
                usuarios[telefono]["estado"] = "CONFIRMAR_PAQUETE"

                enviar_botones(
                    telefono,
                    f"💎 Elegiste:\n{usuarios[telefono]['paquete']} - {usuarios[telefono]['precio']}\n\n¿Confirmás?",
                    [
                        {"id": "confirmar_paquete", "title": "✅ Confirmar"},
                        {"id": "volver_menu", "title": "🔁 Cambiar"}
                    ]
                )

        # ================== CONFIRMAR PAQUETE ==================
        elif estado == "CONFIRMAR_PAQUETE":
            if boton_id == "confirmar_paquete":
                usuarios[telefono]["estado"] = "ID"
                enviar_texto(telefono, "🎮 Enviá tu ID del juego")

            elif boton_id == "volver_menu":
                usuarios[telefono]["estado"] = "INICIO"
                return webhook()

        # ================== ID ==================
        elif estado == "ID" and texto:
            usuarios[telefono]["id_juego"] = texto
            usuarios[telefono]["estado"] = "CONFIRMAR_ID"

            enviar_botones(
                telefono,
                f"🎮 ID ingresado:\n{text}\n\n¿Es correcto?",
                [
                    {"id": "confirmar_id", "title": "✅ Confirmar"},
                    {"id": "volver_menu", "title": "🔁 Cancelar"}
                ]
            )

        # ================== CONFIRMAR ID ==================
        elif estado == "CONFIRMAR_ID":
            if boton_id == "confirmar_id":
                usuarios[telefono]["estado"] = "RESUMEN"

                enviar_botones(
                    telefono,
                    f"📋 RESUMEN FINAL\n\n"
                    f"💎 {usuarios[telefono]['paquete']}\n"
                    f"💰 {usuarios[telefono]['precio']}\n"
                    f"🎮 ID: {usuarios[telefono]['id_juego']}",
                    [
                        {"id": "pagar", "title": "💳 Pagar"},
                        {"id": "volver_menu", "title": "❌ Cancelar"}
                    ]
                )

            else:
                enviar_texto(telefono, "⬆️ Usá los botones para continuar")

        # ================== RESUMEN ==================
        elif estado == "RESUMEN":
            if boton_id == "pagar":
                usuarios[telefono]["estado"] = "PAGO"
                enviar_texto(
                    telefono,
                    "💳 Realizá el pago y enviá el comprobante.\n"
                    "CBU / Mercado Pago / Alias"
                )

        return "EVENT_RECEIVED", 200

    except Exception as e:
        print("ERROR:", e)
        return "EVENT_RECEIVED", 200


if __name__ == "__main__":
    app.run(port=10000)
