import socket
import select
from time import sleep, time
from random import randint
from threading import Thread
import threading
import queue

DATABLOCK_SIZE = 60000
MAX_PWR = 200
MAX_SESS = pow(256,8)

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
        self.counters = [0,0]
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

    def recvfrom(self, ind: int):
            if(self.counters[ind] == len(ports_data[self.local_addr])):
                self.attempt_prolong()
            if(self.counters[ind] == len(ports_data[self.local_addr])):
                return bytes(0)
            self.counters[ind] += 1
            return ports_data[self.local_addr][self.counters[ind] - 1]


    def sure_recvfrom(self, ind: int):
        if(self.counters[ind] == len(ports_data[self.local_addr])):
                self.sure_prolong()
        self.counters[ind] += 1
        return ports_data[self.local_addr][self.counters[ind] - 1]
    
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
        self.sess = randint(0, MAX_SESS - 1)

    def __init__(self, nmb: int, ack_tp: int, sess: int, data: bytes):
        self.nmb = nmb
        self.data = bytearray(data)
        self.ack_tp = ack_tp
        self.sess = sess


    def bytes(self):
        assert(self.nmb // 256 <= 255)
        res = bytearray(11 + len(self.data))
        res[0] = self.nmb % 256
        res[1] = self.nmb // 256
        res[2] = self.ack_tp
        n = self.sess
        for i in range(3, 3 + 8):
            res[i] = n % 256
            n //= 256
        for i in range(len(self.data)):
            res[i + 11] = self.data[i]
        return res
    
    def __str__(self):
        ans = str(self.nmb) + " " + str(self.ack_tp) + " " + str(self.sess) + " " + str(self.data)
        return ans

def make_pack(a : bytes):
    if(len(a) <= 10):
        return pack(-1, -1, -1, bytes(0))
    
    sess = 0
    for i in range(10, 2, -1):
        sess *= 256
        sess += a[i]

    return pack(a[0] + a[1] * 256, a[2], sess,  a[11:])


SLEEP_TIME = 0.0015
class MyTCPProtocol(UDPBasedProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.threads_count = 0
        self.th = None
        self.used_sessions = set()
        self.header_packs_sent = 0
        self.data_packs_sent = 0
        self.header_acks_sent = 0
        self.acks_sent = 0
        self.closed_sessions = set()

    def sender(self, data: bytes, ind: int, last_sender):
        if last_sender != None:
            last_sender.join()
        sess = randint(0, MAX_SESS - 1)
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
        
        head_packet = pack(num_packs, 3, sess, bytes(0))
        self.sendto(head_packet.bytes())
        self.sendto(packets[0].bytes())
        self.header_packs_sent+= 1
        counter = 0
        while(True):
            counter += 1
            if counter == 4:
                break
            c = make_pack(self.recvfrom(ind))
            while(c.sess != -1 and c.sess != sess):
                if(c.sess != sess or c.ack_tp != 1):
                    c = make_pack(self.recvfrom(ind))
                    continue
            if(c.sess != sess or c.ack_tp != 1):
                sleep(SLEEP_TIME)
                self.sendto(head_packet.bytes())
                self.header_packs_sent += 1
                continue
            break
        cnt_acks = 0
        ack = [False for i in range(len(packets))]
        cnt_iters = 0
        while(cnt_acks != len(packets)):
            cnt_iters += 1
            if((len(data) == 10 and cnt_iters == 4) or cnt_iters == 20):
                break
            msg = make_pack(self.recvfrom(ind))
            if msg.sess == sess and msg.ack_tp == 4:
                break
            while(msg.sess != -1):
                while(msg.ack_tp == 2 and msg.sess == sess):
                    if(not ack[msg.nmb]):
                        ack[msg.nmb] = True
                        cnt_acks += 1
                    msg = make_pack(self.recvfrom(ind))
                msg = make_pack(self.recvfrom(ind))
            for i in range(len(packets)):
                if not ack[i]:
                    self.sendto(packets[i].bytes())
                    self.data_packs_sent+= 1
        self.threads_count -= 1

    def send(self, data: bytes):
        if len(data) == 10:
            self.quicksend(data)
            return len(data)
        watching[self.local_addr] += 1
        self.counters.append(len(ports_data[self.local_addr]))
        self.th = Thread(target=self.sender, args = (data, len(self.counters) - 1, self.th, ))
        self.th.daemon = True
        self.threads_count += 1
        self.th.start() 
        self.need_closure = 0
        return len(data)
    
    def quicksend(self, data: bytes):
        sess = randint(0, MAX_SESS - 1)
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
        self.sendto(packets[0].bytes())
        self.sendto(packets[0].bytes())
        self.sendto(packets[0].bytes())
        self.sendto(packets[0].bytes())
    
    def quickrcv(self):
        header = make_pack(self.recvfrom(0))
        self.rcv_process(header)
        while(header.ack_tp != 0 or header.sess in self.used_sessions):
            header = make_pack(self.recvfrom(0))
            self.rcv_process(header)
        self.used_sessions.add(header.sess)
        return header.data
        
    def rcv_process(self, p: pack):
        if p.sess in self.closed_sessions:
            h = pack(0, 4, p.sess, bytes(0))
            self.sendto(h.bytes())

    def rcv_closer(self):
        pck = make_pack(self.recvfrom(0))
        while(pck.ack_tp != -1):
            self.rcv_process(pck)
            pck = make_pack(self.recvfrom(0))

    def reciever(self, answer):
        if hasattr(self, "th") and self.threads_count == 1:
            self.th.join()
        header = make_pack(self.recvfrom(0))
        self.rcv_process(header)
        while(header.ack_tp != 3 or header.sess in self.used_sessions):
            header = make_pack(self.recvfrom(0))
            self.rcv_process(header)
        sess = header.sess
        self.used_sessions.add(sess)
        header_ack = pack(header.nmb, 1, sess, bytes(0))
        self.sendto(header_ack.bytes())
        cnt_packs = header.nmb

        packs = [bytearray(0) for i in range(cnt_packs)]
        acks = [False for i in range(cnt_packs)]
        cnt_acks = 0

        while(cnt_acks != cnt_packs):
            r_bytes = make_pack(self.recvfrom(0))
            #self.rcv_process(r_bytes)
            if(r_bytes.ack_tp == 3 and r_bytes.sess == sess):
                self.sendto(header_ack.bytes())
            while(r_bytes.ack_tp == 0 and r_bytes.sess == sess):
                packs[r_bytes.nmb] = r_bytes.data
                if not acks[r_bytes.nmb]:
                    cnt_acks += 1
                    acks[r_bytes.nmb] = True
                ack = pack(r_bytes.nmb, 2, sess, bytes(0))
                self.sendto(ack.bytes())
                self.acks_sent+= 1
                r_bytes = make_pack(self.recvfrom(0))
                self.rcv_process(r_bytes)
        self.closed_sessions.add(sess)
        answ = bytearray(0)
        for i in range(cnt_packs):
            answ.extend(packs[i])
        answer.append(answ)
        answer.append(sess)

    def recv(self, n: int):
        if n == 10:
            return self.quickrcv()
        answ = []
        self.reciever(answ)
        return answ[0]
    
    def close(self):
        print("headers sent: ", self.header_packs_sent)
        print("packs sent: ", self.data_packs_sent)
        print("header acks sent: ", self.header_acks_sent)
        print("data acks sent: ", self.acks_sent)
        #self.rcv_closer()
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