import socket
import struct
import logging
import time

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("rfid_socket_inventory_raw_log.txt", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

READER_IP = '192.168.1.20'
READER_PORT = 5084

def build_message(message_type, message_id, body_bytes):
    length = 10 + len(body_bytes)
    header = struct.pack('>HHQ', message_type, length, message_id)
    return header + body_bytes

def build_add_rospec():
    message_type = 0x0433  # ADD_ROSPEC
    message_id = 1001

    # Aquí va el body binario de ADD_ROSPEC
    # Este es un ejemplo súper básico: ROSpecID = 123, todos los triggers null
    rospec_id = 123
    body = struct.pack('>I B B', rospec_id, 0, 0)  # ROSpecID, Priority, CurrentState (Disabled)

    # Aquí no estoy incluyendo AISpec ni InventoryParams ni ROReportSpec por simplicidad
    return build_message(message_type, message_id, body)

def build_enable_rospec(rospec_id):
    message_type = 0x0434  # ENABLE_ROSPEC
    message_id = 1002
    body = struct.pack('>I', rospec_id)
    return build_message(message_type, message_id, body)

def build_start_rospec(rospec_id):
    message_type = 0x0436  # START_ROSPEC
    message_id = 1003
    body = struct.pack('>I', rospec_id)
    return build_message(message_type, message_id, body)

def main():
    try:
        with socket.create_connection((READER_IP, READER_PORT), timeout=5) as sock:
            logging.info(f"✅ Conectado a {READER_IP}:{READER_PORT}")

            # Enviar ADD_ROSPEC
            add_msg = build_add_rospec()
            sock.sendall(add_msg)
            logging.info("✅ ADD_ROSPEC enviado.")

            time.sleep(0.5)

            # Enviar ENABLE_ROSPEC
            enable_msg = build_enable_rospec(123)
            sock.sendall(enable_msg)
            logging.info("✅ ENABLE_ROSPEC enviado.")

            time.sleep(0.5)

            # Enviar START_ROSPEC
            start_msg = build_start_rospec(123)
            sock.sendall(start_msg)
            logging.info("✅ START_ROSPEC enviado.")

            # Leer respuesta
            response = sock.recv(4096)
            logging.info(f"📡 Respuesta recibida: {response.hex()}")

    except Exception as e:
        logging.error(f"❌ Error de conexión o comunicación: {e}")

if __name__ == "__main__":
    main()
