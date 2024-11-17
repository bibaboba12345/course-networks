from protocol import MyTCPProtocol
from servers import EchoClient, EchoServer, ParallelClientServer

import os
import random
from contextlib import closing

used_ports = {}


def generate_port():
    while True:
        port = random.randrange(25000, 30000)
        if port not in used_ports:
            break
    used_ports[port] = True
    return port


a_addr = ('127.0.0.1', generate_port())
b_addr = ('127.0.0.1', generate_port())

print(a_addr, '\n', b_addr)

with closing(MyTCPProtocol(local_addr=a_addr, remote_addr=b_addr)) as a, \
         closing(MyTCPProtocol(local_addr=b_addr, remote_addr=a_addr)) as b:
    msg = os.urandom(10)
    print("msg = ", msg)
    print('Hopping in')
    a.send(msg)
    print('Sent!')
    recieved = b.recv(len(msg))
    print('Recieved!')
    print(recieved)
    b.send(recieved)
    print('Sent back!')
    recieved = a.recv(len(recieved))
    print('Recieved back!')
    print(recieved)

