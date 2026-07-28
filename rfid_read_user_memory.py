import logging
from twisted.internet import reactor
from sllurp.llrp import LLRPClient
from sllurp.llrp_proto import (
    READ_OP,
    OpSpec,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Callback para los reportes de tag
def tag_report_callback(llrp_msg):
    tag_reports = llrp_msg.msgdict.get('TagReportData', [])
    for tag in tag_reports:
        epc = tag.get('EPC-96') or tag.get('EPC')
        if epc:
            print(f'✅ EPC: {epc.hex()}')

        # Mostrar User Memory leída (AccessResult)
        access_results = tag.get('AccessCommandOpSpecResult', [])
        for result in access_results:
            if result.get('OpSpecID') and result.get('Result') == 'Success':
                if 'ReadData' in result:
                    print(f'📥 User Memory: {result["ReadData"].hex()}')
                else:
                    print('⚠️ No User Memory data')
            else:
                print(f'❌ Error o sin resultado en AccessSpec: {result}')

# Función para lanzar AccessSpec después de conexión
def setup_access_spec(proto):
    logger.info('📡 Programando AccessSpec para leer User Memory...')
    opspec = OpSpec(
        op_type=READ_OP,
        memory_bank=3,      # Bank 3: User Memory
        word_pointer=0,     # Offset 0
        word_count=4        # Leer 4 palabras (puedes ajustar si necesitas más)
    )
    proto.addAccessSpecForAllTags(
        opspec,
        access_spec_id=99,
        currentState='Disabled',
        triggerImmediately=True
    )
    logger.info('✅ AccessSpec listo, iniciando inventario...')
    proto.startInventory()

# Crear la fábrica
factory = LLRPClient(start_inventory=True)
factory.addTagReportCallback(tag_report_callback)
factory.addOnConnectCallback(setup_access_spec)

# Conexión al reader
reader_ip = '192.168.1.20'
reader_port = 5084
logger.info('🚀 Conectando al reader...')
reactor.connectTCP(reader_ip, reader_port, factory)
reactor.run()
