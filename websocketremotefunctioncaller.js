function WebSocketRemoteFunctionCaller(connection_string){
    ws = new WebSocket(connection_string);
    ws.onmessage = function (evt) {
        console.log(evt.data);
        if(evt.data[0] == "$"){
            // server is returning a value
            data = JSON.parse(evt.data.substr(1));
            var key = data[0];
            var value = data[1];
            if(this[key]){
                this[key](key, value);
            }
        }else{
            // server is attempting to call
            data = JSON.parse(evt.data);
            var key = data[0];
            var fn = data[1];
            var args = data.slice(2);
            var code = fn + "(" + args.join(", ") + ");";
            if(this["__"+fn]){
                return_value = this["__"+fn].apply(this, args);
                this.send(JSON.stringify( [key, return_value] ));
            }
        }
    };
    
    ws.server_function = function (func, callback){
        websocket = this;
        return function(){
            var key = "$" + Math.random();
            data = new Array(key, func.name);
            for(i = 0; i < arguments.length; i++){
                data.push(arguments[i]);
            }
            data = "$" + JSON.stringify(data);
            websocket[key] = callback;
            websocket.send(data);
            return key;
        }
    };
    
    ws.client_function = function(func){
        ws["__" + func.name] = func;
    }
    
    return ws;
}