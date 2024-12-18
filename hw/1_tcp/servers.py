import os
import struct

from protocol import MyTCPProtocol


class Base:
    def __init__(self, socket: MyTCPProtocol, iterations: int, msg_size: int):
        self.socket = socket
        self.iterations = iterations
        self.msg_size = msg_size


class EchoServer(Base):
    def run(self):
        for _ in range(self.iterations):
            msg = self.socket.recv(self.msg_size)
            self.socket.send(msg)
            
class EchoClient(Base):
    def run(self):
        for _ in range(self.iterations):
            msg = os.urandom(self.msg_size)
            n = self.socket.send(msg)
            assert n == self.msg_size
            assert msg == self.socket.recv(n)
            if self.msg_size == 10 and _ % 100 == 0:
                print(_)


class ParallelClientServer(Base):
    def run(self):
        for i in range(self.iterations):
            msg = struct.pack('!Q', i)
            n = self.socket.send(msg)
            assert n == len(msg)
        
        for i in range(self.iterations):
            msg = self.socket.recv(8)
            i_recv = struct.unpack('!Q', msg)[0]
            if i != i_recv:
                print(i, " ", i_recv, "!!!")
            else:
                print(i, " ", i_recv)
            assert i_recv == i
        
        
