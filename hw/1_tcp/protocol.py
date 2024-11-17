import socket
import select
from time import sleep
from random import randint
from threading import Thread
import queue

DATABLOCK_SIZE = 60000
MAX_PWR = 200

ports_data = {}
watching = {}

class UDPBasedProtocol:
    def __init__(self, *, local_addr, remote_addr):
        self.udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        if local_addr not in watching.keys():
            watching[local_addr] = 1
        else:
            watching[local_addr] += 1
        if(local_addr in ports_data.keys()):
            ports_data[local_addr].clear()
        else:
            ports_data[local_addr] = []
        self.rcv_read_counter = len(ports_data[local_addr])
        self.wrt_read_counter = len(ports_data[local_addr])
        self.local_addr = local_addr
        self.remote_addr = remote_addr
        self.udp_socket.bind(local_addr)
        self.packs_sent = 0

    
    def attempt_prolong(self):
        ready = select.select([self.udp_socket], [], [], 0)
        if(ready[0]):
            msg = self.udp_socket.recvmsg(70000)[0]
            ports_data[self.local_addr].append(msg)

    def sure_prolong(self):
        ready = select.select([self.udp_socket], [], [])
        if(ready[0]):
            msg = self.udp_socket.recvmsg(70000)[0]
            ports_data[self.local_addr].append(msg)



    def sendto(self, data):
        self.packs_sent += 1
        return self.udp_socket.sendto(data, self.remote_addr)

    def recvfrom(self, from_rcv: bool):
        if(from_rcv):
            if(self.rcv_read_counter == len(ports_data[self.local_addr])):
                self.attempt_prolong()
            if(self.rcv_read_counter == len(ports_data[self.local_addr])):
                return bytes(0)
            self.rcv_read_counter += 1
            return ports_data[self.local_addr][self.rcv_read_counter - 1]
        else:
            if(self.wrt_read_counter == len(ports_data[self.local_addr])):
                self.attempt_prolong()
            if(self.wrt_read_counter == len(ports_data[self.local_addr])):
                return bytes(0)
            self.wrt_read_counter += 1
            return ports_data[self.local_addr][self.wrt_read_counter - 1]


    def sure_recvfrom(self, from_rcv: bool):
        if(from_rcv):
            while(self.rcv_read_counter == len(ports_data[self.local_addr])):
                self.sure_prolong()
            self.rcv_read_counter += 1
            return ports_data[self.local_addr][self.rcv_read_counter - 1]
        else:
            while(self.wrt_read_counter == len(ports_data[self.local_addr])):
                self.sure_prolong()
            self.wrt_read_counter += 1
            return ports_data[self.local_addr][self.wrt_read_counter - 1]

    def close(self):
        print("closed thread, packs sent: ", self.packs_sent)
        watching[self.local_addr] -= 1
        if(watching[self.local_addr] == 0):
            print("closed socket")
            self.udp_socket.close()
            ports_data[self.local_addr].clear()

class pack:
    nmb: int
    ack_tp: int
    sess: int
    data: bytearray

    def __init__(self):
        self.nmb = 0
        self.data = []
        self.ack_tp = 0
        self.sess = randint(255)

    def __init__(self, nmb: int, ack_tp: int, sess: int, data: bytes):
        self.nmb = nmb
        self.data = bytearray(data)
        self.ack_tp = ack_tp
        self.sess = sess


    def bytes(self):
        assert(self.nmb // 256 <= 255)
        res = bytearray(4 + len(self.data))
        res[0] = self.nmb % 256
        res[1] = self.nmb // 256
        res[2] = self.ack_tp
        res[3] = self.sess
        for i in range(len(self.data)):
            res[i + 4] = self.data[i]
        return res
    
    def __str__(self):
        ans = str(self.nmb) + " " + str(self.ack_tp) + " " + str(self.sess) + " " + str(self.data)
        return ans

def make_pack(a : bytes):
    if(len(a) <= 3):
        return pack(-1, -1, -1, bytes(0))
    return pack(a[0] + a[1] * 256, a[2], a[3],  a[4:])



class MyTCPProtocol(UDPBasedProtocol):
    q = queue.Queue()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        q = queue.Queue()

    def sender(self, data: bytes):
        sess = randint(0, 255)
        data = bytearray(data)
        packets = []
        num_packs = 0
        l = 0
        for i in range(len(data)):
            if (i != 0 and i % DATABLOCK_SIZE == 0) or (i == len(data) - 1):
                packet = pack(num_packs, 0, sess, data[l : i + 1])
                num_packs += 1
                l = i + 1
                packets.append(packet)
        
        head_packet = pack(num_packs, 3, sess, bytes(MAX_PWR))
        n = len(data)
        for i in range(MAX_PWR):
            head_packet.data[i] = n % 256
            n //= 256

        self.sendto(head_packet.bytes())
        counter = 0
        while(True):
            counter += 1
            c = make_pack(self.recvfrom(False))
            while(c.sess != -1 and c.sess != sess):
                if(c.sess != sess or c.ack_tp != 1):
                    c = make_pack(self.recvfrom(False))
                    continue
            if(c.sess != sess or c.ack_tp != 1):
                #sleep(0.001)
                self.sendto(head_packet.bytes())
                continue
            break
        cnt_acks = 0
        ack = [False for i in range(len(packets))]

        while(cnt_acks != len(packets)):
            for i in range(len(packets)):
                if not ack[i]:
                    self.sendto(packets[i].bytes())
            msg = make_pack(self.recvfrom(False))
            while(msg.ack_tp == 2 and msg.sess == sess):
                if(not ack[msg.nmb]):
                    ack[msg.nmb] = True
                    cnt_acks += 1
                msg = make_pack(self.recvfrom(False))
            #sleep(0.001)

    def send(self, data: bytes):
        watching[self.local_addr] += 1
        self.th = Thread(target=self.sender, args = (data, ))
        self.th.start() 
        self.need_closure = 0
        return len(data)
        
        
    def recv(self, n: int):
        if hasattr(self, "th"):
            self.th.join()
        header = make_pack(self.sure_recvfrom(True))
        while(header.ack_tp != 3):
            header = make_pack(self.sure_recvfrom(True))
        sess = header.sess
        header_ack = pack(header.nmb, 1, sess, bytes(0))
        self.sendto(header_ack.bytes())
        cnt_packs = header.nmb

        total_len = 0
        for i in range(MAX_PWR - 1, -1, -1):
            total_len *= 256
            total_len += header.data[i]


        packs = [bytearray(0) for i in range(cnt_packs)]
        acks = [False for i in range(cnt_packs)]
        cnt_acks = 0
        while(cnt_acks != cnt_packs):
            r_bytes = make_pack(self.recvfrom(True))
            while(r_bytes.ack_tp == 0 and r_bytes.sess == sess):
                packs[r_bytes.nmb] = r_bytes.data
                if not acks[r_bytes.nmb]:
                    cnt_acks += 1
                    acks[r_bytes.nmb] = True
                ack = pack(r_bytes.nmb, 2, sess, bytes(0))
                self.sendto(ack.bytes())
                r_bytes = make_pack(self.recvfrom(True))

        answ = bytearray(0)
        for i in range(cnt_packs):
            answ.extend(packs[i])
        return answ
    
    def close(self):
        super().close()

# import socket


# class UDPBasedProtocol:
#     def __init__(self, *, local_addr, remote_addr):
#         self.udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
#         self.remote_addr = remote_addr
#         self.udp_socket.bind(local_addr)

#     def sendto(self, data):
#         return self.udp_socket.sendto(data, self.remote_addr)

#     def recvfrom(self, n):
#         msg = self.udp_socket.recvmsg(n)[0]
#         return msg

#     def close(self):
#         self.udp_socket.close()


# class MyTCPProtocol(UDPBasedProtocol):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)

#     def send(self, data: bytes):
#         return self.sendto(data)

#     def recv(self, n: int):
#         return self.recvfrom(n)
    
#     def close(self):
#         super().close()