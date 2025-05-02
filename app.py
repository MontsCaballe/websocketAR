import asyncio
import threading
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import httpx
import logging
from sllurp.reader import Reader

# ============================
# Configuraciones generales
# ============================

URL_DEVICES = "https://apirepuve.minayarit.gob.mx/recaudacion/arcos-repuve/"
URL_ANTENNAS = "https://apirepuve.minayarit.gob.mx/recaudacion/antenas-repuve/"
API_URL = "https://apirepuve.minayarit.gob.mx/tramites/lecturas-arcos/"

logging.basicConfig(level=logging.INFO)

# ============================
# Variables globales
# ============================

devices_with_data = []
antennas_with_data = []
readers = []
reported_tags = set()

# ============================
# WebSocket y Página Web
# ============================

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_status(200)
        devices_html = "<ul>" + "".join(
            f"<li>ID: {device['id']}, IP: {device.get('ip')}, MAC: {device.get('mac_address')}</li>"
            for device in devices_with_data
        ) + "</ul>"

        html_content = f"""
        <html>
            <head>
                <title>Bienvenido al WebSocket RFID</title>
                <style>
                    body {{ background-color: #f5f0e6; font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                    h1 {{ color: #800000; }}
                    h2 {{ color: #555; }}
                    ul {{ text-align: left; display: inline-block; }}
                </style>
            </head>
            <body>
                <h1>Bienvenido al WebSocket RFID</h1>
                <p>Conéctate a: <code>ws://localhost:8888/wsArcos</code></p>
                <h2>Dispositivos conectados:</h2>
                {devices_html}
            </body>
        </html>
        """
        self.write(html_content)

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    clients = set()

    def open(self):
        WebSocketHandler.clients.add(self)
        logging.info("Nuevo cliente WebSocket conectado.")

    def on_message(self, message):
        logging.info(f"Mensaje recibido del cliente: {message}")

    def on_close(self):
        WebSocketHandler.clients.remove(self)
        logging.info("Cliente WebSocket desconectado.")

    @classmethod
    def notify_clients(cls, message):
        for client in cls.clients:
            client.write_message(message)

# ============================
# Lector RFID
# ============================

class DeviceReader:
    def __init__(self, device, report_callback):
        self.device = device
        self.ip = device.get('ip')
        self.report_callback = report_callback
        self.reader = None

    def start(self):
        logging.info(f"Conectando a dispositivo {self.ip}")
        try:
            self.reader = Reader(self.ip)

            readSpecParam = {
                'OpSpecID': 0,
                'MB': 3,
                'WordPtr': 0,
                'AccessPassword': 0,
                'WordCount': 13
            }
            self.reader.startAccess(readWords=readSpecParam)

            self.reader.startLiveReports(
                reportCallback=self.report_callback,
                powerDBm=31.5,
                freqMHz=866.9,
                mode=1002
            )
            logging.info(f"Inventario continuo iniciado en {self.ip}")
        except Exception as e:
            logging.error(f"Error conectando a {self.ip}: {e}")
            threading.Timer(10, self.start).start()

    def stop(self):
        if self.reader:
            self.reader.stopLiveReports()
            self.reader.stopPolitely()

# ============================
# Funciones utilitarias
# ============================

def buscar_ids_arco_antena(ip_dispositivo, puerto_antena):
    arco = next((d for d in devices_with_data if d.get('ip') == ip_dispositivo), None)
    antena = next((a for a in antennas_with_data if a.get('arcos') == arco['id'] and a.get('puerto') == puerto_antena), None) if arco else None
    id_arco = arco.get('id') if arco else None
    id_antena = antena.get('id') if antena else None
    return id_arco, id_antena

def convertir_hex_ascii(hex_string):
    try:
        return bytes.fromhex(hex_string).decode('ascii').replace('\x00', '').strip()
    except:
        return ""

def construir_payload(vin, folio, id_arco, id_antena):
    return {
        "vin": vin,
        "folio": folio,
        "arco": id_arco,
        "antena": id_antena
    }

async def enviar_a_api(payload):
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(API_URL, json=payload)
        logging.info(f"API respondio: {response.status_code} - {response.text}")

# ============================
# Callback de Lectura
# ============================

def tag_seen_callback(tags):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    for tag in tags:
        try:
            user_data = tag.get('OpSpecResult', {}).get('ReadData')
            if user_data and len(user_data) >= 13:
                folio = str(int(user_data[:4].hex(), 16))
                vin = convertir_hex_ascii(user_data[4:34].hex())

                logging.info(f"\U0001f4cb Folio leído: {folio}")
                logging.info(f"\U0001f4cb VIN leído: {vin}")

                tag_uid = f"{folio}-{vin}"
                if tag_uid not in reported_tags:
                    reported_tags.add(tag_uid)

                    id_arco, id_antena = buscar_ids_arco_antena('169.254.1.1', tag.get('AntennaID'))
                    payload = construir_payload(vin, folio, id_arco, id_antena)
                    asyncio.run_coroutine_threadsafe(enviar_a_api(payload), loop)

                    WebSocketHandler.notify_clients(f"Nuevo VIN leído: {vin}")
            else:
                logging.warning("\u26a0\ufe0f Tag no tiene OpSpecResult/ReadData.")
        except Exception as e:
            logging.error(f"\u274c Error procesando tag: {e}")

# ============================
# Conexion de dispositivos
# ============================

async def fetch_device_data():
    async with httpx.AsyncClient(verify=False) as client:
        response_antennas = await client.get(URL_ANTENNAS)
        response_antennas.raise_for_status()
        antennas = response_antennas.json()

        devices = [
            # {"id": 1, "ip": "169.254.1.1", "mac_address": "00:00:00:00:00:00", "nombre": "SpeedwayR420"}
             {"id": 1, "ip": "172.17.10.102", "mac_address": "00:00:00:00:00:00", "nombre": "Speedway R420 Test 1"},
             {"id": 2, "ip": "172.17.10.101", "mac_address": "00:00:00:00:00:00", "nombre": "Speedway R420 Test 2"}
        ]

        return devices, antennas

def connect_devices_thread():
    for device in devices_with_data:
        ip = device.get('ip')
        if ip:
            reader = DeviceReader(device, tag_seen_callback)
            readers.append(reader)
            reader.start()

# ============================
# Shutdown
# ============================

async def shutdown():
    logging.info("\U0001f534 Cerrando todas las conexiones a dispositivos...")
    for reader in readers:
        reader.stop()

# ============================
# Main
# ============================

async def main():
    global devices_with_data, antennas_with_data

    devices_with_data, antennas_with_data = await fetch_device_data()

    threading.Thread(target=connect_devices_thread, daemon=True).start()

    app = tornado.web.Application([
        (r"/", MainHandler),
        (r"/wsArcos", WebSocketHandler),
    ])
    server = tornado.httpserver.HTTPServer(app)
    server.listen(8888)
    logging.info("Servidor Tornado iniciado en el puerto 8888.")

    try:
        await asyncio.Event().wait()
    finally:
        await shutdown()

if __name__ == "__main__":
    asyncio.run(main())
