import os
import signal
import time
from core.configuration import Configuration
from core.monitor import Monitor
from core.detection import Detection
from core.mitigation import Mitigation
from utils import log
from kombu import Connection, Queue, Exchange, uuid, Consumer, Producer


class GracefulKiller:
    def __init__(self):
        self.kill_now = False
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self,signum, frame):
        self.kill_now = True


def main():
    # Instatiate Modules
    modules = {}

    modules['configuration'] = Configuration()
    modules['monitor'] = Monitor()
    modules['detection'] = Detection()
    modules['mitigation'] = Mitigation()
    # modules['detection3'] = Detection()
    # modules['detection4'] = Detection()


    for name, module in modules.items():
        module.start()

    killer = GracefulKiller()
    log.info('Send SIGTERM signal to end..\n')


    with Connection('amqp://guest:guest@localhost:5672//') as conn:
        with conn.SimpleQueue('modules_control') as queue:
            while True:
                try:
                    message = queue.get(block=False, timeout=1)
                    message.ack()

                    if message.payload['module'] in modules:
                        module = modules[message.payload['module']]
                        if message.payload['action'] == 'stop':
                            if not module.is_alive():
                                log.warning('Module already stopped..')
                            else:
                                module.terminate()
                                while module.is_alive():
                                    time.sleep(1)
                        elif message.payload['action'] == 'start':
                            if module.is_alive():
                                log.warning('Module already running..')
                            else:
                                modules[message.payload['module']] = module.__class__()
                                modules[message.payload['module']].start()
                    else:
                        log.warning('Unrecognized module name {}'.format(message.payload['module']))
                except queue.Empty:
                    time.sleep(1)
                    if killer.kill_now:
                        break
    #input("\n[!] Press ENTER to exit [!]\n\n")

    # Stop all modules and web application
    for name, module in modules.items():
        module.terminate()

    for name, module in modules.items():
        module.join()
    log.info('Bye..!')


if __name__ == '__main__':
    main()
