import subprocess
import threading

def run_inventory():
    command = [
        'sllurp',
        'inventory',
        '--antennas', '1',
        '--tx-power', '31',
        '--mode-identifier', '2',
        '192.168.1.20'
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    try:
        for line in process.stdout:
            if 'saw tag(s):' in line or 'EPC' in line:
                print('📡', line.strip())
    except Exception as e:
        print(f'❌ Error leyendo inventario: {e}')
    finally:
        process.terminate()
        print('🛑 Inventario detenido.')

def start_inventory_thread():
    thread = threading.Thread(target=run_inventory)
    thread.start()

if __name__ == "__main__":
    print('🚀 Iniciando inventario... Presiona Ctrl+C para detener.')
    start_inventory_thread()
