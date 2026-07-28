def build_C1G2ReadSpec(op_spec_id=1, memory_bank=3, word_pointer=0, word_count=16):
    return {
        'opSpecID': op_spec_id,
        'memoryBank': memory_bank,
        'wordPointer': word_pointer,
        'wordCount': word_count,
        'accessPassword': 0
    }

def build_ACCESS_SPEC(access_spec_id, antenna_id, protocol_id, op_specs):
    return {
        'AccessSpecID': access_spec_id,
        'AntennaID': antenna_id,
        'ProtocolID': protocol_id,
        'CurrentState': False,
        'ROSpecID': 0,
        'AccessSpecStopTrigger': {
            'AccessSpecStopTrigger': 'Null',
            'OperationCountValue': 0
        },
        'AccessCommand': {
            'C1G2TagSpec': None,
            'OpSpec': op_specs
        }
    }
