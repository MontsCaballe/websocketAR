import asyncio
import threading
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import httpx
import logging
import time
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
tag_timestamps = {}
main_event_loop = None

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
            self.reader.stopPolitely()

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
                mode=1002,
                tagInterval=0,
                timeInterval=0.2
            )

            logging.info(f"Inventario continuo iniciado en {self.ip}")
        except Exception as e:
            logging.error(f"Error conectando a {self.ip}: {e}")
            threading.Timer(30, self.start).start()

    def stop(self):
        if self.reader:
            try:
                self.reader.stopLiveReports()
                self.reader.stopPolitely()
            except Exception as e:
                logging.warning(f"Error al detener lector {self.ip}: {e}")

# ============================
# Funciones utilitarias
# ============================

def buscar_ids_arco_antena(ip_dispositivo, puerto_antena):
    arco = next((d for d in devices_with_data if d.get('ip') == ip_dispositivo), None)
    antena = next((a for a in antennas_with_data if a.get('arcos') == arco['id'] and a.get('puerto') == puerto_antena), None) if arco else None
    id_arco = arco.get('id') if arco else None
    id_antena = antena.get('id') if antena else None
    if not arco:
        logging.warning(f"⚠️ No se encontró el arco con IP {ip_dispositivo}")
    if not antena:
        logging.warning(f"⚠️ No se encontró la antena con arco_id={arco['id'] if arco else 'N/A'} y puerto={puerto_antena}")
    return id_arco, id_antena

def convertir_hex_ascii(hex_string):
    try:
        return bytes.fromhex(hex_string).decode('ascii').replace('\x00', '').strip()
    except Exception as e:
        logging.error(f"Error al convertir hex a ASCII: {e}")
        return ""

def construir_payload(vin, folio, id_arco, id_antena):
    return {
        "vin": vin,
        "folio": folio,
        "arco": id_arco,
        "antena": id_antena
    }

async def enviar_a_api(payload):
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(API_URL, json=payload)
            logging.info(f"API respondio: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Error al enviar datos a la API: {e}")

# ============================
# Callback de Lectura
# ============================

def tag_seen_callback(tags):
    global main_event_loop
    for tag in tags:
        try:
            logging.debug(f"🔍 Tag detectado (completo): {tag}")
            user_data = tag.get('OpSpecResult', {}).get('ReadData')
            reader_ip = tag.get('ReaderIP') or tag.get('reader_ip') or 'UNKNOWN'
            antenna_port = tag.get('AntennaID')

            if not user_data:
                logging.warning(f"⚠️ Tag sin datos. IP={reader_ip}, Antena={antenna_port}, Tag={tag}")
                continue

            if len(user_data) < 13:
                logging.warning(f"⚠️ Tag con datos incompletos. Datos leídos: {user_data.hex()} | Longitud: {len(user_data)}")
                continue

            folio = str(int(user_data[:4].hex(), 16))
            vin = convertir_hex_ascii(user_data[4:34].hex())

            logging.info(f"📋 Folio leído: {folio}")
            logging.info(f"📋 VIN leído: {vin}")

            tag_uid = f"{folio}-{vin}"
            now = time.time()
            if tag_uid in reported_tags and now - tag_timestamps.get(tag_uid, 0) < 10:
                logging.debug(f"⏱️ Tag repetido recientemente: {tag_uid}")
                continue

            reported_tags.add(tag_uid)
            tag_timestamps[tag_uid] = now

            if reader_ip == 'UNKNOWN':
                logging.warning(f"⚠️ IP del lector no disponible en el tag: {tag}")

            logging.debug(f"Buscando id_arco e id_antena para IP={reader_ip}, Puerto={antenna_port}")
            id_arco, id_antena = buscar_ids_arco_antena(reader_ip, antenna_port)

            if id_arco and id_antena:
                payload = construir_payload(vin, folio, id_arco, id_antena)
                if main_event_loop:
                    future = asyncio.run_coroutine_threadsafe(enviar_a_api(payload), main_event_loop)
                    future.add_done_callback(lambda f: logging.debug("✅ API enviada correctamente."))
                WebSocketHandler.notify_clients(f"Nuevo VIN leído: {vin}")
            else:
                logging.warning(f"⚠️ No se pudo mapear el tag a un arco o antena. Datos: IP={reader_ip}, Puerto={antenna_port}")
        except Exception as e:
            logging.error(f"❌ Error procesando tag: {e}")

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
    logging.info("🔴 Cerrando todas las conexiones a dispositivos...")
    for reader in readers:
        reader.stop()

# ============================
# Main
# ============================

async def main():
    global devices_with_data, antennas_with_data, main_event_loop

    devices_with_data, antennas_with_data = await fetch_device_data()
    main_event_loop = asyncio.get_running_loop()

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
