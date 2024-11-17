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
    msg = bytes("LOL message", "utf-8")
    print("msg = ", msg)
    print('Hopping in')
    for i in range(10):
        a.send(msg)
    print('Sent 10 times!')
    for i in range(10):
        recieved = b.recv(len(msg))
        print('Recieved ', i,  'th time')
        print(recieved.decode("utf-8"))


