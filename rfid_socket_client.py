import struct
import socket
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("rfid_socket_log.txt", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Dirección IP y puerto LLRP del lector
READER_IP = '192.168.1.20'
READER_PORT = 5084

# Mensaje LLRP: GET_READER_CAPABILITIES (Message Type: 0x0101, Length: 10 bytes, Message ID: 1)
# Esto solo es para confirmar que el lector responde.
GET_CAPABILITIES_MESSAGE = struct.pack('>HHQ', 0x0101, 10, 1)

def main():
    try:
        with socket.create_connection((READER_IP, READER_PORT), timeout=5) as sock:
            logging.info(f"✅ Conectado a {READER_IP}:{READER_PORT}")

            # Enviar el mensaje GET_READER_CAPABILITIES
            sock.sendall(GET_CAPABILITIES_MESSAGE)
            logging.info("✅ Mensaje GET_READER_CAPABILITIES enviado.")

            # Esperar respuesta
            response = sock.recv(4096)
            logging.info(f"✅ Respuesta recibida (hex): {response.hex()}")

    except Exception as e:
        logging.error(f"❌ Error de conexión o comunicación: {e}")

if __name__ == "__main__":
    main()
