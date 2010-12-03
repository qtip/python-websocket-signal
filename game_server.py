from time import sleep
from async import Async
from websocketremotefunctioncaller import WebSocketRemoteFunctionCaller

class MyWebSocketRemoteFunctionCaller(WebSocketRemoteFunctionCaller):
    def onopen(self, client):
        client_positions[client] = (0,0)
        for known_client in self.clients():
            if known_client != client:
                x, y = client_positions[known_client]
                Async(agent_update, str(known_client), x, y, client)
                Async(agent_update, str(client), 0, 0, known_client)
    def onclose(self, client):
        for dest_client in self.clients():
            if dest_client != client:
                Async(agent_exit, str(client), dest_client)

if __name__ == "__main__":
    ws = MyWebSocketRemoteFunctionCaller()
    
    
    ws.start('127.0.0.1', '8080');

    
    # Remote functions
    @ws.client_function()
    def agent_update(agent, x, y): pass
    
    @ws.client_function()
    def agent_exit(agent): pass
    
    # Local functions
    @ws.server_function()
    def end():
        ws.stop()
        ws.server.shutdown()
    
    client_positions = dict()
    
    @ws.server_function()
    def broadcast_position(x, y, client):
        client_positions[client] = (x,y)
        for dest_client in ws.clients():
            if dest_client != client:
                Async(agent_update, str(client), x, y, dest_client)
    
    while True:
        sleep(5)
        if not ws.running:
            break
