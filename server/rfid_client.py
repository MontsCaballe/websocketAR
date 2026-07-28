# server/rfid_client.py
import threading
import time
import logging
from rfid_user_memory_inventory import LLRPReaderClient

class RFIDClient(threading.Thread):
    def __init__(self, ip, websocket_callback):
        super().__init__()
        self.ip = ip
        self.websocket_callback = websocket_callback
        self.stop_event = threading.Event()
        self.client = None

    def run(self):
        logging.info(f"📡 Iniciando lector en {self.ip}")
        self.client = LLRPReaderClient(self.ip, self.on_tag_read)

        try:
            self.client.connect()
            while not self.stop_event.is_set():
                self.client.run_inventory_once()
                time.sleep(1)  # ⏳ Delay entre inventarios
        except Exception as e:
            logging.error(f"❌ Error en lector {self.ip}: {e}")
        finally:
            self.client.disconnect()
            logging.info(f"🔌 Lector desconectado {self.ip}")

    def stop(self):
        logging.info(f"🛑 Deteniendo lector {self.ip}")
        self.stop_event.set()

    def on_tag_read(self, tag_data):
        """
        tag_data = {
            'epc': 'E20034120123456789012345',
            'vin': '1HGCM82633A123456',
            'folio': 'F123456789'
        }
        """
        data = {
            "ip": self.ip,
            "epc": tag_data.get("epc"),
            "vin": tag_data.get("vin"),
            "folio": tag_data.get("folio"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        logging.info(f"📦 Enviando lectura de {self.ip} al WebSocket: {data}")
        self.websocket_callback(data)
