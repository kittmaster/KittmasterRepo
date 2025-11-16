import xbmc
import json
import time

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
    
    songs = json_response.get('result', {}).get('songs', [])
    for song in songs:
        if song.get('songid'):
            json_call("Playlist.Add", playlistid=playlistid, item={"songid": int(song['songid'])})
        elif song.get('file'):
            json_call("Playlist.Add", playlistid=playlistid, item={"file": song['file']})

    time.sleep(1.0)
    json_call("Player.Open", item={"playlistid": playlistid, "position": 0}, options={"shuffled": False})

    # Wait for playback to start ### Appears to be not needed for now. Add if strange behavior shows up.
    #time.sleep(1.0)

    # Attempt different fullscreen methods
    #xbmc.executebuiltin("ToggleFullscreen")  ## Does not work
    json_call("Input.ExecuteAction", action="fullscreen")   ## Works and starts "Now Playing"

    # Attempt to send Tab key
    #xbmc.executebuiltin("SendKey(61486)")  ## Does not work

play_album_songs()