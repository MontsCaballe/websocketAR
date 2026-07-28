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
    Extrae el VIN desde la memoria de usuario (User Memory Bank).
    Asume que el VIN está a partir del byte 8 en adelante, con longitud de 17 caracteres.
    """
    try:
        if not raw_bytes or len(raw_bytes) < 25:
            return "❌ Memoria insuficiente para extraer VIN"

        vin_start = 8
        vin_end = vin_start + 17

        vin_bytes = raw_bytes[vin_start:vin_end]
        vin = vin_bytes.decode('ascii', errors='ignore').strip()

        return f"✅ VIN desde User Memory: {vin}"

    except Exception as e:
        return f"❌ Error parseando memoria: {e}"

def parse_epc_folio(epc_bytes):
    try:
        # EPC viene en ASCII HEX. Ejemplo: b'323835393838353420202020'
        # Convertir primero los bytes a string ASCII
        hex_string = epc_bytes.decode('ascii', errors='ignore')
        # Ahora convierte ese string hexadecimal a bytes reales
        ascii_bytes = bytes.fromhex(hex_string)
        # Finalmente decodifica como ASCII final (tu folio real en texto)
        folio = ascii_bytes.decode('ascii', errors='ignore').strip()
        return f"✅ Folio desde EPC: {folio}"
    except Exception as e:
        return f"❌ Error al parsear EPC: {e}"



def tag_report_callback(reader, tag_reports):
    print("\n📡 Nuevo lote de tags leídos:")
    for tag in tag_reports:
        print(tag)

        # Leer Folio desde el EPC
        epc = tag.get('EPC-96') or tag.get('EPC')
        if epc:
            print(parse_epc_folio(epc))

        # Leer VIN desde User Memory
        result = tag.get('C1G2ReadOpSpecResult')
        if result and result.get('Result') == 0 and result.get('ReadData'):
            user_memory = result['ReadData']
            print(f"📝 Datos crudos User Memory: {user_memory}")
            print(parse_user_memory(user_memory))
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

    # Espera pequeña antes de mandar el AccessSpec
    time.sleep(2)

    try:
        read_op = C1G2Read(
            OpSpecID=1,
            AccessPassword=0,
            MB=3,          # User Memory Bank
            WordPtr=0,     # Desde la posición 0
            WordCount=16   # Leer 16 palabras (32 bytes por si acaso)
        )
        reader.start_access_spec(op_spec=read_op, stop_after_count=0)

        reader.join()
    except KeyboardInterrupt:
        print("\n🛑 Terminando inventario por Ctrl+C")
        reader.disconnect()

if __name__ == '__main__':
    main()
