import tornado.websocket

class RFIDWebSocket(tornado.websocket.WebSocketHandler):
    clientes = set()

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
