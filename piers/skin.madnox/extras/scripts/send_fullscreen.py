import xbmc
import json

def json_call(method, **params):
    query = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1})
    response = xbmc.executeJSONRPC(query)
    return json.loads(response)

# Execute fullscreen action
json_call("Input.ExecuteAction", action="fullscreen")