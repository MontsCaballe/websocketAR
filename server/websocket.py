import tornado.websocket
import logging
import json
import tornado.ioloop
import tornado.queues

tag_queue = tornado.queues.Queue()


class RFIDWebSocket(tornado.websocket.WebSocketHandler):
    clients = set()
    
    
    def open(self):
        logging.info(f"🌐 Cliente WebSocket conectado: {self.request.remote_ip}")
        self.__class__.clients.add(self)
        from server.rfid_manager import rfid_manager
        arcos_data = rfid_manager.get_arcos_data()
        self.write_message({"type": "update_arcos", "arcos": arcos_data})

    def on_message(self, message):
        """Se llama cuando un cliente WebSocket envía un mensaje"""
        logging.info(f"📩 Mensaje recibido de cliente: {message}")
        # Aquí puedes manejar comandos desde el cliente si quieres

    def on_close(self):
        """Se llama cuando un cliente WebSocket se desconecta"""
        # RFIDWebSocket.clients.discard(self)
        self.__class__.clients.discard(self)
        logging.info(f"🔌 Cliente WebSocket desconectado: {self.request.remote_ip}")

    @classmethod
    def broadcast_tag(cls, tag_data):
        """Envía un tag leído a todos los clientes conectados"""
        message = {
            "type": "new_tag",
            "tag": tag_data
        }
        dead_clients = []
        for client in cls.clients:
            try:
                client.write_message(message)
            except Exception as e:
                logging.error(f"❌ Error enviando tag a cliente WebSocket: {e}")
                dead_clients.append(client)
        # Limpiar clientes desconectados
        for dead in dead_clients:
            cls.clients.discard(dead)
        logging.info(f"📡 Enviado new_tag a los clientes: {message}")


    @classmethod
    def broadcast_message(cls, message):
        dead_clients = []
        for client in cls.clients:
            try:
                tornado.ioloop.IOLoop.current().add_callback(
                    client.write_message, message
                )
            except Exception as e:
                logging.error(f"❌ Error enviando mensaje a cliente WebSocket: {e}")
                dead_clients.append(client)
        # Limpiar los clientes desconectados
        for client in dead_clients:
            cls.clients.discard(client)


    @classmethod
    def send_tag_to_clients(cls, tag_data):
        """Envía datos de tag en tiempo real a todos los clientes WebSocket"""
        message = json.dumps({
            "type": "new_tag",
            "tag": tag_data
        })
        for client in cls.clients:
            tornado.ioloop.IOLoop.current().add_callback(
                client.write_message, message
            )
        logging.info(f"📡 Enviado new_tag a los clientes: {message}")

    @classmethod
    def send_tag_to_all(cls, tag_data):
        for client in cls.clients:
            try:
                client.send_tag(tag_data)
            except Exception as e:
                logging.error(f"❌ Error enviando tag a cliente WebSocket: {e}")


    @classmethod
    def send_tag(cls, tag_data):
        try:
            message = {
                "type": "new_tag",
                "tag": tag_data
            }
            

            """Envía un mensaje a todos los clientes WebSocket conectados"""
            dead_clients = []
            for client in cls.clients:
                try:
                    client.write_message(message)
                except Exception as e:
                    logging.error(f"❌ Error enviando mensaje a cliente WebSocket: {e}")
                    dead_clients.append(client)
            # Limpiar clientes desconectados
            for client in dead_clients:
                cls.clients.discard(client)


            logging.info(f"📡 Enviado new_tag a los clientes: {message}")
        except Exception as e:
            logging.error(f"❌ Error enviando tag a cliente WebSocket: {e}")
    @classmethod
    def _broadcast_safe(cls, message):
        """Se ejecuta en el hilo principal (IOLoop)"""
        dead_clients = []
        for client in cls.clients:
            try:
                client.write_message(json.dumps(message))
            except Exception as e:
                logging.error(f"❌ Error enviando mensaje a cliente WebSocket: {e}")
                dead_clients.append(client)
        for client in dead_clients:
            cls.clients.discard(client)

    
    
    # Exporta la función
    __all__ = ["RFIDWebSocket", "process_tag_queue"]
async def process_tag_queue():
        while True:
            tag_data = await tag_queue.get()
            yield f"data: {json.dumps(tag_data)}\n\n"
            message = {
                "type": "tag_read",
                "tag": tag_data
            }
            dead_clients = []
            for client in RFIDWebSocket.clients:
                try:
                    client.write_message(json.dumps(message))
                    logging.info(f"📡 Enviado tag_read a clientes: {message}")
                except Exception as e:
                    logging.error(f"❌ Error enviando mensaje a cliente WebSocket: {e}")
                    dead_clients.append(client)
            for client in dead_clients:
                RFIDWebSocket.clients.discard(client)