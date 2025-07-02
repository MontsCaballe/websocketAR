import asyncio
import logging
import threading
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
from sllurp.llrp import LLRPReaderClient, LLRPReaderConfig, LLRP_DEFAULT_PORT
from sllurp.helpers import build_ACCESS_SPEC, build_C1G2ReadSpec
from sllurp.llrp import LLRPMessage


# ========================
# Configuración de logging
# ========================
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("rfid_logs.txt", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ========================
# Variables globales
# ========================
lecturas_array = []
main_event_loop = None
reader_client = None

# ========================
# WebSocket
# ========================
class WebSocketHandler(tornado.websocket.WebSocketHandler):
    clients = set()

    def open(self):
        WebSocketHandler.clients.add(self)
        logging.info("Cliente WebSocket conectado.")

    def on_close(self):
        WebSocketHandler.clients.remove(self)
        logging.info("Cliente WebSocket desconectado.")

    @classmethod
    def notify_clients(cls, message):
        for client in cls.clients:
            client.write_message(message)

# ========================
# Tornado Handlers
# ========================
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("<h1>Servidor WebSocket RFID activo ✅</h1><p>Conéctate a ws://localhost:8888/wsArcos</p>")

class LecturasHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        self.write({"total": len(lecturas_array), "lecturas": lecturas_array})

# ========================
# Callback de Tags
# ========================
def tag_report_cb(reader, tag_reports):
    for tag in tag_reports:
        epc = tag.get('epc-pure', 'N/A')
        antenna = tag.get('antenna', 'N/A')
        user_memory = tag.get('user', b'').hex() if tag.get('user') else 'No User Memory'

        lectura = {
            "epc": epc,
            "antena": antenna,
            "user_memory": user_memory
        }
        lecturas_array.append(lectura)

        logging.info(f"✅ Tag leído - EPC: {epc}, Antena: {antenna}, User Memory: {user_memory}")
        WebSocketHandler.notify_clients(f"NUEVO TAG: EPC={epc} - USER={user_memory}")

# ========================
# AccessSpec para leer Banco 3
# ========================
def agregar_access_spec_user_memory(reader):
    access_spec = {
        'AccessSpecID': 1001,
        'AntennaID': 0,
        'ProtocolID': 1,
        'CurrentState': False,
        'ROSpecID': 0,
        'AccessSpecStopTrigger': {
            'AccessSpecStopTrigger': 0,
            'OperationCountValue': 0
        },
        'AccessCommand': {
            'C1G2TagSpec': None,
            'OpSpec': [{
                'OpSpecID': 123,
                'AccessPassword': 0,
                'MemoryBank': 3,
                'WordPointer': 0,
                'WordCount': 16
            }]
        }
    }

    try:
        # Construimos el mensaje como diccionario
        msg = {
            'MessageID': 1234,
            'AccessSpec': access_spec
        }
        # Enviamos como un ADD_ACCESS_SPEC
        reader.send('ADD_ACCESS_SPEC', msg)
        logging.info("✅ AccessSpec enviado manualmente como ADD_ACCESS_SPEC.")
    except Exception as e:
        logging.error(f"❌ Error al enviar AccessSpec manual: {e}")


# ========================
# Inicializar lector
# ========================
def iniciar_lector(ip):
    global reader_client

    config = LLRPReaderConfig({
        'antennas': [1],
        'tx_power': {1: 31},
        'mode_identifier': 0,
        'tag_content_selector': {
            'EnableAntennaID': True,
            'EnablePeakRSSI': True,
            'EnableFirstSeenTimestamp': True,
            'EnableLastSeenTimestamp': True,
            'EnableTagSeenCount': True,
            'EnableAccessSpecID': True,
            'EnableROSpecID': True,
            'EnableSpecIndex': True,
            'EnableInventoryParameterSpecID': True,
            'EnableChannelIndex': True,
            'EnableUserMemory': True
        }
    })

    reader_client = LLRPReaderClient(ip, LLRP_DEFAULT_PORT, config)
    reader_client.add_tag_report_callback(tag_report_cb)

    def run_reader():
        try:
            reader_client.connect()
            agregar_access_spec_user_memory(reader_client)
            reader_client.join(None)
        except Exception as e:
            logging.error(f"❌ Error conectando al lector: {e}")

    threading.Thread(target=run_reader, daemon=True).start()

# ========================
# Shutdown
# ========================
async def shutdown():
    if reader_client:
        reader_client.disconnect()
    logging.info("✅ Lector desconectado.")

# ========================
# Main
# ========================
async def main():
    global main_event_loop
    main_event_loop = asyncio.get_running_loop()

    iniciar_lector('192.168.1.20')  # Cambia aquí la IP si hace falta

    app = tornado.web.Application([
        (r"/", MainHandler),
        (r"/wsArcos", WebSocketHandler),
        (r"/lecturas", LecturasHandler),
    ])
    server = tornado.httpserver.HTTPServer(app)
    server.listen(8888)
    logging.info("✅ Servidor Tornado iniciado en el puerto 8888.")

    try:
        await asyncio.Event().wait()
    finally:
        await shutdown()

if __name__ == "__main__":
    asyncio.run(main())
