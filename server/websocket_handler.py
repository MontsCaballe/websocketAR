import tornado.websocket
import json
import logging

class RFIDWebSocket(tornado.websocket.WebSocketHandler):
    clientes = set()

    def initialize(self, arcos):
        self.arcos = arcos  # 🏷️ Ahora tiene acceso a la lista de arcos

    def open(self):
        print("🔗 Cliente WebSocket conectado")
        self.clientes.add(self)

    def on_message(self, message):
        print(f"📩 Mensaje recibido de cliente: {message}")

    def on_close(self):
        print("❌ Cliente WebSocket desconectado")
        self.clientes.remove(self)

    def check_origin(self, origin):
        return True  # Permitir conexiones desde cualquier origen

    @classmethod
    def broadcast_message(cls, data):
        """
        Envía un mensaje JSON a todos los clientes WebSocket conectados.
        """
        message = json.dumps(data)
        for cliente in list(cls.clientes):
            try:
                cliente.write_message(message)
            except Exception as e:
                logging.error(f"⚠️ Error enviando mensaje a cliente WebSocket: {e}")
