import os
import threading
import logging
import tornado.ioloop
import tornado.web
import tornado.httpserver
from dotenv import load_dotenv
from server.rfid_manager import rfid_manager
from server.websocket import RFIDWebSocket, process_tag_queue, tag_queue
from server.dashboard_handler import DashboardHandler
from server.api_client import fetch_arcos_periodically
from server.sse_handler import SSEHandler

# 📦 Cargar variables de entorno
load_dotenv()

# 📖 Configurar logging
logging.basicConfig(level=logging.INFO)

# 📂 Paths
base_dir = os.path.dirname(__file__)
templates_path = os.path.join(base_dir, "templates")
static_path = os.path.join(base_dir, "static")


def arcos_updater():
    """Hilo que consulta periódicamente la API y actualiza los arcos"""
    for arcos in fetch_arcos_periodically():
        rfid_manager.update_arcos(arcos)
        try:
            # 🌐 Notificar a clientes WebSocket
            RFIDWebSocket.broadcast_message({
                "type": "update_arcos",
                "arcos": arcos
            })
            logging.info("📡 Enviado update_arcos a los clientes WebSocket")
            
        except Exception as e:
            logging.error(f"❌ Error enviando arcos a clientes: {e}")


if __name__ == "__main__":
    # 📡 Configurar Tornado app
    app = tornado.web.Application([
        (r"/", DashboardHandler, dict(rfid_manager=rfid_manager)),
        (r"/ws", RFIDWebSocket),
        (r"/live", SSEHandler),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": static_path}),
    ], debug=True, template_path=templates_path)

    # 🚀 Arrancar hilo para actualizar arcos periódicamente
    updater_thread = threading.Thread(target=arcos_updater, daemon=True)
    updater_thread.start()

    # 🚀 Iniciar servidor HTTP
    server = tornado.httpserver.HTTPServer(app)
    port = int(os.getenv("PORT", 8889))
    # server.listen(port, address="172.17.1.245")
    server.listen(port)
    logging.info(f"✅ Servidor iniciado en http://172.17.1.245:{port}")

    # 🚀 Ejecutar loop principal y procesar la cola de tags (SSE y WebSocket)
    ioloop = tornado.ioloop.IOLoop.current()
    ioloop.spawn_callback(process_tag_queue)
    tornado.ioloop.IOLoop.current().spawn_callback(process_tag_queue)

    ioloop.start()
