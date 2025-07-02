# import logging
# import time
# from sllurp.llrp import LLRPReaderClient, LLRPReaderConfig, C1G2Read

# logging.basicConfig(level=logging.INFO)

# def tag_report_callback(reader, tag_reports):
#     print("\n📡 Nuevo lote de tags leídos:")
#     for tag in tag_reports:
#         print(tag)

# def main():
#     config = LLRPReaderConfig()
#     config.antennas = [1]
#     config.tx_power = {1: 31}
#     config.impinj_search_mode = 2
#     config.start_inventory = True
#     config.reset_on_connect = True

#     reader = LLRPReaderClient('192.168.1.20', config=config)
#     reader.add_tag_report_callback(tag_report_callback)

#     reader.connect()

#     # 👇 Esperar a que el reader termine su setup antes de enviar AccessSpec
#     time.sleep(2)

#     try:
#         read_op = C1G2Read(
#             OpSpecID=1,
#             AccessPassword=0,
#             MB=3,
#             WordPtr=0,
#             WordCount=8   # Puedes ajustar el tamaño si el VIN ocupa más
#         )
#         reader.start_access_spec(op_spec=read_op, stop_after_count=1)

#         reader.join()
#     except KeyboardInterrupt:
#         print("\n🛑 Terminando inventario por Ctrl+C")
#         reader.disconnect()

# if __name__ == '__main__':
#     main()
import logging
import time
from sllurp.llrp import LLRPReaderClient, LLRPReaderConfig, C1G2Read

logging.basicConfig(level=logging.INFO)

def parse_user_memory(raw_bytes):
    """
    Decodifica VIN y Folio basado en la posición real observada en la memoria.
    """
    try:
        if not raw_bytes or len(raw_bytes) < 25:
            return "❌ Memoria insuficiente para extraer VIN"

        # Extraer a partir del byte 8, tomar 17 caracteres (largo estándar de un VIN)
        vin_start = 8
        vin_end = vin_start + 17

        vin_bytes = raw_bytes[vin_start:vin_end]
        vin = vin_bytes.decode('ascii', errors='ignore').strip()

        return f"✅ VIN: {vin}"

    except Exception as e:
        return f"❌ Error parseando memoria: {e}"


def tag_report_callback(reader, tag_reports):
    print("\n📡 Nuevo lote de tags leídos:")
    for tag in tag_reports:
        print(tag)

        # Revisa si viene User Memory leída
        result = tag.get('C1G2ReadOpSpecResult')
        if result and result.get('Result') == 0 and result.get('ReadData'):
            user_memory = result['ReadData']
            print(f"📝 Datos crudos User Memory: {user_memory}")
            parsed = parse_user_memory(user_memory)
            print(parsed)
        else:
            print("⚠️ No se obtuvo User Memory o hubo error en lectura")

def main():
    config = LLRPReaderConfig()
    config.antennas = [1]
    config.tx_power = {1: 31}
    config.impinj_search_mode = 2
    config.start_inventory = True
    config.reset_on_connect = True

    reader = LLRPReaderClient('192.168.1.20', config=config)
    reader.add_tag_report_callback(tag_report_callback)

    reader.connect()

    # 👇 Espera pequeña antes de mandar el AccessSpec
    time.sleep(2)

    try:
        read_op = C1G2Read(
            OpSpecID=1,
            AccessPassword=0,
            MB=3,          # User Memory Bank
            WordPtr=0,     # Desde la posición 0
            WordCount=16    # Leer 8 Words = 16 bytes
        )
        reader.start_access_spec(op_spec=read_op, stop_after_count=1)

        reader.join()
    except KeyboardInterrupt:
        print("\n🛑 Terminando inventario por Ctrl+C")
        reader.disconnect()

if __name__ == '__main__':
    main()
