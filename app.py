from flask import Flask, request, render_template_string, redirect, send_file
import requests, json, os
from io import BytesIO

app = Flask(__name__)

# ---------- CONFIG ----------
VERIFY_TOKEN = "159412d596d0d2d06050a502883b08ca"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = "919152181286061"
NUMERO_PERSONAL = "543886046052"

USUARIOS_FILE = "usuarios.json"

PAQUETES = {
    "p1": ("100 Diamantes", "$1.200"),
    "p2": ("310 Diamantes", "$3.200"),
    "p3": ("520 Diamantes", "$5.000"),
    "p4": ("1060 Diamantes", "$9.800"),
}

# ---------- PERSISTENCIA ----------
def cargar_usuarios():
    if os.path.exists(USUARIOS_FILE):
        return json.load(open(USUARIOS_FILE))
    return {}

def guardar_usuarios():
    json.dump(usuarios, open(USUARIOS_FILE, "w"), indent=4)

usuarios = cargar_usuarios()

# ---------- WHATSAPP ----------
URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}

def enviar_texto(tel, texto):
    requests.post(URL, headers=HEADERS, json={
        "messaging_product": "whatsapp",
        "to": tel,
        "type": "text",
        "text": {"body": texto}
    })

def enviar_botones(tel, texto, botones):
    requests.post(URL, headers=HEADERS, json={
        "messaging_product": "whatsapp",
        "to": tel,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto},
            "action": {"buttons": botones}
        }
    })

def enviar_imagen(tel, media_id):
    requests.post(URL, headers=HEADERS, json={
        "messaging_product": "whatsapp",
        "to": tel,
        "type": "image",
        "image": {"id": media_id}
    })

# ---------- WEBHOOK ----------
@app.route("/webhook", methods=["GET","POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Forbidden", 403

    data = request.json

    # ✅ FILTRO CRÍTICO
    if not data.get("entry"):
        return "EVENT_RECEIVED", 200

    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" not in value:
            return "EVENT_RECEIVED", 200

        msg = value["messages"][0]
        tel = msg["from"]
        tipo = msg["type"]

        texto = msg.get("text", {}).get("body", "").strip()
        boton = msg.get("interactive", {}).get("button_reply", {}).get("id")

        if tel not in usuarios:
            usuarios[tel] = {"estado": "MENU"}

        estado = usuarios[tel]["estado"]

        # ---------- MENU ----------
        if estado == "MENU":
            usuarios[tel]["estado"] = "ELEGIR_PAQUETE"
            enviar_botones(tel, "💎 Elegí un paquete", [
                {"type":"reply","reply":{"id":"p1","title":"100 💎 $1200"}},
                {"type":"reply","reply":{"id":"p2","title":"310 💎 $3200"}},
                {"type":"reply","reply":{"id":"p3","title":"520 💎 $5000"}},
                {"type":"reply","reply":{"id":"p4","title":"1060 💎 $9800"}},
            ])

        # ---------- PAQUETE ----------
        elif estado == "ELEGIR_PAQUETE" and boton in PAQUETES:
            p, pr = PAQUETES[boton]
            usuarios[tel].update({"paquete":p,"precio":pr,"estado":"PEDIR_ID"})
            enviar_texto(tel, f"💎 Elegiste {p} ({pr})\n🎮 Enviá tu ID del juego")

        # ---------- ID ----------
        elif estado == "PEDIR_ID" and texto:
            usuarios[tel]["id_juego"] = texto
            usuarios[tel]["estado"] = "CONFIRMAR_ID"
            enviar_botones(tel, f"🎮 ID ingresado:\n{text}", [
                {"type":"reply","reply":{"id":"ok_id","title":"✅ Confirmar"}},
                {"type":"reply","reply":{"id":"cambiar","title":"🔁 Cambiar"}}
            ])

        # ---------- CONFIRMAR ID ----------
        elif estado == "CONFIRMAR_ID":
            if boton == "ok_id":
                usuarios[tel]["estado"] = "COMPROBANTE"
                enviar_texto(
                    tel,
                    f"📋 RESUMEN\n"
                    f"💎 {usuarios[tel]['paquete']}\n"
                    f"💰 {usuarios[tel]['precio']}\n"
                    f"🎮 {usuarios[tel]['id_juego']}\n\n"
                    "📎 Enviá el comprobante"
                )
            elif boton == "cambiar":
                usuarios[tel]["estado"] = "PEDIR_ID"
                enviar_texto(tel, "🎮 Enviá nuevamente tu ID")

        # ---------- COMPROBANTE ----------
        elif estado == "COMPROBANTE":
            media_id = msg.get(tipo, {}).get("id")
            enviar_texto(NUMERO_PERSONAL,
                f"📦 NUEVO PEDIDO\nCliente: {tel}\n"
                f"{usuarios[tel]['paquete']} - {usuarios[tel]['precio']}\n"
                f"ID: {usuarios[tel]['id_juego']}"
            )
            if media_id:
                enviar_imagen(NUMERO_PERSONAL, media_id)

            usuarios[tel]["estado"] = "HUMANO"
            enviar_texto(tel, "✅ Pedido recibido. Un asesor te escribe.")

        guardar_usuarios()

    except Exception as e:
        print("ERROR:", e)

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

