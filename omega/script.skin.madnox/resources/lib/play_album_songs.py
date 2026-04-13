import xbmc
import json

def json_call(method, **params):
    query = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1})
    response = xbmc.executeJSONRPC(query)
    return json.loads(response)

def play_album_songs():
    playlistid = 0  
    albumid = xbmc.getInfoLabel("ListItem.DBID")

    if not albumid:
        xbmc.log("play_album_songs.py: No albumid found. Ensure an album is selected.", xbmc.LOGERROR)
        return

    json_call("Playlist.Clear", playlistid=playlistid)
    json_response = json_call("AudioLibrary.GetSongs", filter={"albumid": int(albumid)}, properties=["file"])
    
    songs = json_response.get('result', {}).get('songs',[])
    for song in songs:
        if song.get('songid'):
            json_call("Playlist.Add", playlistid=playlistid, item={"songid": int(song['songid'])})
        elif song.get('file'):
            json_call("Playlist.Add", playlistid=playlistid, item={"file": song['file']})

    json_call("Player.Open", item={"playlistid": playlistid, "position": 0}, options={"shuffled": False})
    
    xbmc.sleep(500)
    # Instantly kill all open dialogs without animation
    xbmc.executebuiltin("Dialog.Close(all,true)")
    # Force the music visualization engine to the absolute top layer
    xbmc.executebuiltin("ActivateWindow(visualisation)")

# --- MODULE ENTRY POINT ---
def run(params=None):
    play_album_songs()