import xbmc
import json

def json_call(method, **params):
    query = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1})
    response = xbmc.executeJSONRPC(query)
    return json.loads(response) # Added json.loads() so it matches your other scripts

def playall():
    playlistid = 1  # Video playlist
    container_id = 1090

    # Clear the playlist
    json_call("Playlist.Clear", playlistid=playlistid)

    # SAFEGUARD: Ensure it doesn't crash if the container is empty/loading
    num_items_str = xbmc.getInfoLabel(f"Container({container_id}).NumItems")
    num_items = int(num_items_str) if num_items_str.isdigit() else 0

    if num_items == 0:
        xbmc.log("[play_all_music_videos] Container is empty or not loaded yet. Aborting.", xbmc.LOGWARNING)
        return

    for i in range(num_items):
        dbid = xbmc.getInfoLabel(f"Container({container_id}).ListItemAbsolute({i}).DBID")
        url = xbmc.getInfoLabel(f"Container({container_id}).ListItemAbsolute({i}).Filenameandpath")

        if dbid:
            json_call("Playlist.Add", playlistid=playlistid, item={"musicvideoid": int(dbid)})
        elif url:
            json_call("Playlist.Add", playlistid=playlistid, item={"file": url})

    xbmc.sleep(1000) # Changed to xbmc.sleep

    # Get first item in the playlist to play explicitly
    first_video = xbmc.getInfoLabel(f"Playlist({playlistid}).File(0)")

    if first_video:
        json_call("Player.Open", item={"playlistid": playlistid, "position": 0}, options={"shuffled": False})
        xbmc.sleep(500)
        xbmc.executebuiltin("Dialog.Close(all,true)") # Instantly kills all open dialogs without animation
        xbmc.executebuiltin("ActivateWindow(fullscreenvideo)") # Forces the video engine to the absolute top layer

# --- MODULE ENTRY POINT ---
def run(params=None):
    playall()