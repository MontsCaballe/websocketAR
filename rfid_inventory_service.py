# from twisted.internet import reactor
# from sllurp.llrp import LLRPClientFactory
# import logging

# logging.basicConfig(level=logging.INFO)

# def my_tag_callback(llrp_msg, reader_addr):
#     try:
#         tags = llrp_msg.msgdict.get('TagReportData', [])
#         for tag in tags:
#             epc_bytes = tag.get('EPC-96') or tag.get('EPC')
#             if epc_bytes:
#                 epc_str = epc_bytes.decode(errors='ignore')
#                 print(f"📡 Tag leído desde {reader_addr}: EPC={epc_str}")
#     except Exception as e:
#         print(f"❌ Error al procesar tag: {e}")

# # ✅ SIN antenna_list
# factory = LLRPClientFactory(start_inventory=True)

# factory.addTagReportCallback(my_tag_callback)

# # Conectar al lector
# reactor.connectTCP('192.168.1.20', 5084, factory)
# reactor.run()
import logging
from twisted.internet import reactor
from sllurp.llrp import LLRPClientFactory

logging.basicConfig(level=logging.INFO)

def tag_report_callback(llrp_msg):
    for tag in llrp_msg.msgdict.get('TagReportData', []):
        epc_bytes = tag.get('EPC-96') or tag.get('EPC')
        epc_hex = epc_bytes.hex() if epc_bytes else 'N/A'
        print(f'📡 EPC leído: {epc_hex}')

        # Si ya tienes activado leer el banco USER, aquí buscaría ese campo
        if 'UserData' in tag:
            user_data = tag['UserData'].hex()
            print(f'🔎 USER Memory: {user_data}')

factory = LLRPClientFactory(start_inventory=True)
factory.addTagReportCallback(tag_report_callback)

print('🚀 Iniciando inventario... Presiona Ctrl+C para detener.')
reactor.connectTCP('192.168.1.20', 5084, factory)
reactor.run()

