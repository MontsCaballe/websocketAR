import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import asyncio
import httpx
import logging
from sllurp.reader import Reader

# Configurar logging
logging.basicConfig(level=logging.INFO)

# URLs
URL_DEVICES = "https://apirepuve.minayarit.gob.mx/recaudacion/arcos-repuve/"
URL_ANTENNAS = "https://apirepuve.minayarit.gob.mx/recaudacion/antenas-repuve/"

# Variables globales
devices_with_data = []
readers = []

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_status(200)
        devices_html = "<ul>" + "".join(
            f"<li>ID: {device['id']}, IP: {device.get('ip')}, MAC: {device.get('mac_address')}</li>"
            for device in devices_with_data
        ) + "</ul>"

        html_content = f"""
        <html>
            <head><title>Bienvenido al WebSocket RFID</title></head>
            <body>
                <h1>Bienvenido al WebSocket RFID</h1>
                <p>Conéctate a: <code>ws://[TU-IP-SERVIDOR]:8888/wsArcos</code></p>
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

class DeviceReader:
    def __init__(self, ip, report_callback):
        self.ip = ip
        self.report_callback = report_callback
        self.reader = None

    def start(self):
        logging.info(f"Conectando a dispositivo {self.ip}")
        try:
            self.reader = Reader(self.ip)
            self.reader.on_tag_report = self.report_callback
            self.reader.connect()
            self.reader.start_inventory()
        except Exception as e:
            logging.error(f"Error conectando a {self.ip}: {e}")
            asyncio.get_event_loop().call_later(10, self.start)  # Reintentar en 10 segundos

def tag_seen_callback(reader, tags):
    for tag in tags:
        epc = tag.get('epc')
        if epc:
            epc_hex = epc.hex()
            logging.info(f"Tag leído: {epc_hex}")
            WebSocketHandler.notify_clients(f"Tag leído: {epc_hex}")

async def fetch_device_data():
    async with httpx.AsyncClient(verify=False) as client:
        response_devices = await client.get(URL_DEVICES)
        response_devices.raise_for_status()
        devices = response_devices.json()
        if isinstance(devices, list):
            return devices
        else:
            return []

async def connect_to_devices():
    for device in devices_with_data:
        ip = device.get('ip')
        if ip:
            reader = DeviceReader(ip, tag_seen_callback)
            readers.append(reader)
            reader.start()

async def main():
    global devices_with_data

    # Obtener dispositivos al iniciar
    devices_with_data = await fetch_device_data()

    # Conectar a todos los dispositivos
    await connect_to_devices()

    # Iniciar servidor Tornado
    app = tornado.web.Application([
        (r"/", MainHandler),
        (r"/wsArcos", WebSocketHandler),
    ])
    server = tornado.httpserver.HTTPServer(app)
    server.listen(8888)
    logging.info("Servidor Tornado iniciado en el puerto 8888.")

if __name__ == "__main__":
    asyncio.run(main())
    tornado.ioloop.IOLoop.current().start()
