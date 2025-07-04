import logging
import tornado.ioloop
import tornado.web
import tornado.websocket
from server.websocket_handler import RFIDWebSocket
from server.dashboard_handler import DashboardHandler
from server.rfid_service import fake_rfid_reader

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("log.txt", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def make_app():
    return tornado.web.Application([
        (r"/", DashboardHandler),
        (r"/ws", RFIDWebSocket),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": "static"}),
    ],
    template_path="templates",
    static_path="static",
    debug=True)

if __name__ == "__main__":
    app = make_app()
    app.listen(8888)
    logging.info("✅ Servidor Tornado y WebSocket iniciado en http://localhost:8888")

    # Iniciar el lector fake en un hilo asíncrono
    tornado.ioloop.IOLoop.current().spawn_callback(fake_rfid_reader)

    tornado.ioloop.IOLoop.current().start()
