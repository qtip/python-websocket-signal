from urllib2 import urlopen
from SocketServer import TCPServer, ThreadingMixIn, BaseRequestHandler
from sys import argv
from string import count, rjust
from hashlib import md5

class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    def __init__(self, *args, **kwargs):
        TCPServer.__init__(self, *args, **kwargs)
        self.connections = dict()
        
    def get_request(self):
        request, client_address = TCPServer.get_request(self)
        self.connections[client_address] = request
        return request, client_address
    def send_to_all(self, msg):
        for client_address, connection in self.connections.iteritems():
            connection.send(msg)
    
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
                print repr(request[0])
                print repr(request[-1])
                if msg == 'hi':
                    self.server.send_to_all(websocket_msg('why hello there'))
                elif msg == 'exit':
                    self.server.shutdown()
        else:
            # not a websocket request.
            print 'failure'

if __name__ == "__main__":
    try:
        port = int(argv[1])
    except IndexError:
        port = 8080
    server = ThreadingTCPServer(('127.0.0.1', port), WebSocketTCPHandler)
    try:
        server.serve_forever()
    except (KeyboardInterrupt):
        exit()
