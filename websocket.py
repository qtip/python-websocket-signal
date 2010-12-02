from urllib2 import urlopen
from SocketServer import TCPServer, ThreadingMixIn, BaseRequestHandler
from sys import argv
from string import count, rjust
from hashlib import md5
from threading import Thread
from time import sleep
import json

class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    def __init__(self, websocketserver, *args, **kwargs):
        TCPServer.__init__(self, *args, **kwargs)
        self.websocketserver = websocketserver
        self.connections = dict()
        self.daemon_threads = True
        
    def get_request(self):
        request, client_address = TCPServer.get_request(self)
        self.connections[client_address] = request
        return request, client_address
    def send_to_all(self, msg):
        for client_address, connection in self.connections.iteritems():
            connection.send(msg)
    def send_to_client(self, client_address, msg):
        self.connections[client_address].send(msg)
        
def number_to_bytes(n):
    out = ''
    while n > 0:
        r = n % 256
        n = int(n/256)
        out = chr(r) + out
    return rjust(out, 4, '\x00')

def sec_websocket_key_decode(s):
    number = int(''.join([x for x in s if x in '0123456789']))
    spaces = count(s, ' ')
    return number_to_bytes(int(number/spaces))

def websocket_msg(s):
    return '\x00' + s + '\xff'

class WebSocketTCPHandler(BaseRequestHandler):
    """
    Handle incoming server requests.
    """
    def handle(self):
        # receive data
        request = self.request.recv(1024)
        headers, data = request.split('\r\n\r\n')
        data = bytes(data)
        headers = headers.split('\r\n')
        requestline = headers[0].split()
        fields = dict([[y.strip() for y in x.split(':',1)] for x in headers[1:]])
        if fields['Connection'] == 'Upgrade' and fields['Upgrade'] == 'WebSocket':
            number1 = sec_websocket_key_decode(fields['Sec-WebSocket-Key1'])
            number2 = sec_websocket_key_decode(fields['Sec-WebSocket-Key2'])
            response = []
            response.append("HTTP/1.1 101 WebSocket Protocol Handshake")
            response.append("Upgrade: WebSocket")
            response.append("Connection: Upgrade")
            response.append("Sec-WebSocket-Origin: %s" % fields['Origin'])
            response.append("Sec-WebSocket-Location: ws://%s%s" % (fields['Host'], requestline[1]))
            response.append("")
            response.append(md5(number1 + number2 + data).digest())
            self.request.send("\r\n".join(response))
            while True:
                request = self.request.recv(1024)
                if not request:
                    break
                msg = request[1:-1]
                print repr(msg)
                # fire event
                self.server.websocketserver.onmessage(self, self.request, msg)
                
        else:
            # not a websocket request.
            print 'failure'

class WebSocketServer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.server = None
        self.running = True
    def start(self, host='127.0.0.1', port=8080, *args, **kwargs):
        self.host = host
        self.port = port
        Thread.start(self, *args, **kwargs)
    def run(self):
        self.server = ThreadingTCPServer(self, (self.host, int(self.port)), WebSocketTCPHandler)
        self.server.serve_forever()
    def clients(self):
        return self.server.connections.keys()
    def send_to_all(self, msg):
        self.server.send_to_all(websocket_msg(msg))
    def send_to_client(self, client_address, msg):
        self.server.send_to_client(client_address, websocket_msg(msg))
    def stop(self):
        self.server.shutdown()
    def onopen(self, socket):
        pass
    def onmessage(self, socket, message):
        pass
    def onerror(self):
        pass
    def onclose(self):
        pass

class WebSocketRemoteFunctionCaller(WebSocketServer):
    def __init__(self, *args, **kwargs):
        self.remote_functions = dict()
        WebSocketServer.__init__(self, *args, **kwargs)
    class RemoteFunctionCallThread(Thread):
        def __init__(self, parent_server, lock):
            Thread.__init__(self)
            self.parent_server = parent_server
            self.lock = lock
        def run(self):
            lock
            
    def remote_function(web_socket_server):
        def decorator(function):
            web_socket_server.remote_functions[function.__name__] = function.func_code.co_varnames
            def replacer(*args):
                if len(args) > len(function.func_code.co_varnames):
                    client = args[-1]
                else:
                    client = None
                data = json.dumps((function.__name__, ) + args)
                if client:
                    web_socket_server.send_to_client(client, data)
                else:
                    web_socket_server.send_to_all(data)
                return None
            return replacer
        return decorator

def myonmessage(ws, client, data):
    print "MY ON MESSAGE %s" % data
    if data == 'hi':
        self.server.send_to_all(websocket_msg('why hello there'))
    elif data == 'exit':
        self.server.shutdown()



if __name__ == "__main__":
    try:
        port = int(argv[1])
    except IndexError:
        port = 8080
    ws = WebSocketRemoteFunctionCaller()
    ws.onmessage = myonmessage
    ws.start('127.0.0.1', port)
    @WebSocketRemoteFunctionCaller.remote_function(ws)
    def shoop(x, y): pass
    sleep(2)
    shoop(1,2)
    sleep(6)
    ws.stop()
    exit()
