import json
import tornado.web
import logging
from server.rfid_manager import rfid_manager
import time

class DashboardHandler(tornado.web.RequestHandler):
    def initialize(self, rfid_manager):
        self.rfid_manager = rfid_manager
    def get(self):
        # Esperar hasta que haya arcos o timeout de 5s
        timeout = 5
        interval = 0.1
        waited = 0
        current_arcos = self.rfid_manager.arcos

        while not current_arcos and waited < timeout:
            logging.warning(f"⏳ Esperando arcos... {waited:.1f}s")
            time.sleep(interval)
            waited += interval

        current_arcos = current_arcos
        if not current_arcos:
            logging.error("❌ No se cargaron arcos tras esperar")
        else:
            logging.info(f"✅ Enviando {len(current_arcos)} arcos al cliente")

        self.render("index.html", arcos_json=json.dumps(current_arcos))
