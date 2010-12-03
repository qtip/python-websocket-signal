from SocketServer import TCPServer, ThreadingMixIn, BaseRequestHandler
from string import count, rjust
from hashlib import md5
from threading import Thread, Event
import json
import datetime

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
        client_address = self.client_address
        try:
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
                # fire event
                self.server.websocketserver.onopen(client_address)
                while True:
                    request = self.request.recv(1024)
                    if not request:
                        break
                    msg = request[1:-1]
                    # fire event
                    self.server.websocketserver.onmessage(client_address, msg)
                del self.server.connections[client_address]
                # fire event
                self.server.websocketserver.onclose(client_address)
            else:
                # not a websocket request.
                # fire event
                self.server.websocketserver.onerror(client_address)
        except ValueError:
            self.server.websocketserver.onerror(client_address)

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
        self.join()
    def onopen(self, client):
        pass
    def onmessage(self, client, message):
        pass
    def onerror(self, client):
        pass
    def onclose(self, client):
        pass

class CallValue:
    def __init__(self):
        self.finished = False
        self.value = None
    def set(self, value):
        self.value = value
        self.finished = True

class WaitingCall:
    def __init__(self, clients, is_specific_client_call):
        self.lock = Event()
        self.is_specific_client_call = is_specific_client_call
        # key = client, value = CallValue instance
        self.client_values = dict()
        for client in clients:
            self.client_values[client] = CallValue()
    
    def call_complete(self):
        return not [x.finished for x in self.client_values.values()].count(False)
    
    def update(self, client, value):
        """
        Given a client and a return value from that client, remember
        the value and unblock the values method if all clients
        have returned values.
        """
        self.client_values[client].set(value)
        if self.call_complete():
            self.lock.set()
    
    def values(self):
        self.lock.clear()
        self.lock.wait(3)
        out = [x.value for x in self.client_values.values()]
        if self.is_specific_client_call:
            return out[0]
        else:
            return out
    
class ReturnValueKeeper:
    
    def __init__(self):
        # key=random key, value = WaitingCall instance
        self.waiting_calls = dict()
    
    def new_call(self, clients, is_specific_client_call):
        """
        Given a list of clients which are (ip, port) pairs,
        return a random identifying key.
        """
        key = md5(str(datetime.datetime.now()) + str(clients)).hexdigest()
        self.waiting_calls[key] = WaitingCall(clients, is_specific_client_call)
        return key
    
    def values(self, key):
        """
        Given a key that was returned from the new_call method,
        block until all the values are in.
        """
        values = self.waiting_calls[key].values()
        try:
            del self.waiting_calls[key]
        except KeyError:
            pass
        return values
    
    def update(self, key, client, value):
        """
        Given a key that was returned from the new_call method,
        a client, and a return value from that client, remember
        the value and unblock the values method if all clients
        have returned values.
        """
        try:
            self.waiting_calls[key].update(client, value)
        except KeyError:
            # there's likely been a time out
            pass


class WebSocketRemoteFunctionCaller(WebSocketServer):
    
    def __init__(self, *args, **kwargs):
        self.remote_functions = dict()
        self.callable_functions = dict()
        self.keeper = ReturnValueKeeper()
        WebSocketServer.__init__(self, *args, **kwargs)
    
    # overridden from parent class
    def onmessage(self, client, message):
        try:
            if message.startswith("$"):
                # client is attempting to call
                data = json.loads(message[1:])
                key, func_name = data[0], str(data[1])
                args = data[2:]
                func = self.callable_functions[func_name]
                params = func.func_code.co_varnames
                if "client" in params:
                    args.insert(params.index("client"), client)
                ret_val = func(*args)
                out = "$" + json.dumps([key, ret_val])
                self.send_to_client(client, out)
            else:
                # client is returning with a value
                data = json.loads(message)
                key, value = data
                self.keeper.update(key, client, value)
        except ValueError:
            pass
    
    # this is a decorator
    def client_function(self):
        def decorator(function):
            self.remote_functions[function.__name__] = function.func_code.co_varnames
            def replacer(*args):
                # check for specific client argument
                if len(args) > len(function.func_code.co_varnames):
                    clients = [args[-1]]
                    args = args[:-1]
                    is_specific_client_call = True
                else:
                    clients = self.clients()
                    is_specific_client_call = False
                # prepare arguments for remote function
                key = self.keeper.new_call(clients, is_specific_client_call)
                
                # args = tuple(json.dumps(x) for x in args)
                data = json.dumps((key, function.__name__) + args)
                
                for client in clients:
                    self.send_to_client(client, data)
                
                return self.keeper.values(key)
            return replacer
        return decorator
    
    # this is a decorator
    def server_function(self):
        def decorator(function):
            self.callable_functions[function.func_name] = function
            return function
        return decorator

