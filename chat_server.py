from time import sleep
from async import Async
from websocketremotefunctioncaller import WebSocketRemoteFunctionCaller

class MyWebSocketRemoteFunctionCaller(WebSocketRemoteFunctionCaller):
    def onopen(self, client):
        print "%s joined the chat." % client[1]
        for dest_client in ws.clients():
            if dest_client != client:
                Async(joined_chat, str(client[1]), dest_client)

if __name__ == "__main__":
    ws = MyWebSocketRemoteFunctionCaller()
    
    ws.start('127.0.0.1', '8080');

        
    # Functions on client
    @ws.client_function()
    def from_others(agent, message): pass
    
    @ws.client_function()
    def joined_chat(agent): pass
        
    # Functions client can access
    @ws.server_function()
    def end():
        ws.stop()
        ws.server.shutdown()
        
    @ws.server_function()
    def message(client, message):
        for dest_client in ws.clients():
            if dest_client != client:
                Async(from_others, str(client[1]), message, dest_client)
    
    while True:
        sleep(5)
        if not ws.running:
            break
