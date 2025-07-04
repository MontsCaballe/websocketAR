import tornado.websocket
import logging
from server.rfid_manager import rfid_manager

class RFIDWebSocket(tornado.websocket.WebSocketHandler):
    clients = set()

    def open(self):
        logging.info("🌐 Cliente WebSocket conectado")
        self.clients.add(self)
        try:
            arcos_data = rfid_manager.arcos
            self.write_message({
                "type": "update_arcos",
                "arcos": arcos_data
            })
            logging.info(f"✅ Enviando {len(arcos_data)} arcos al cliente")
        except Exception as e:
            logging.error(f"❌ Error enviando arcos iniciales: {e}")

    def on_message(self, message):
        logging.info(f"📨 Mensaje recibido del cliente: {message}")

    def on_close(self):
        logging.info("❌ Cliente WebSocket desconectado")
        self.clients.discard(self)  # Evita KeyError si ya no está

    def check_origin(self, origin):
        return True

    @staticmethod
    def broadcast_message(mensaje):
        logging.info("📢 Enviando mensaje a todos los clientes WebSocket")
        for client in RFIDWebSocket.clients.copy():
            try:
                client.write_message(mensaje)
            except Exception as e:
                logging.error(f"❌ Error enviando mensaje a cliente: {e}")
