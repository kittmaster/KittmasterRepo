import xbmc
import json
import time

def json_call(method, **params):
    query = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1})
    response = xbmc.executeJSONRPC(query)
    return response

def playall():
    playlistid = 1  # Video playlist
    container_id = 1090

    # Clear the playlist
    json_call("Playlist.Clear", playlistid=playlistid)

    # Get the number of items in the container
    num_items = int(xbmc.getInfoLabel(f"Container({container_id}).NumItems"))

    for i in range(num_items):
        dbid = xbmc.getInfoLabel(f"Container({container_id}).ListItemAbsolute({i}).DBID")
        url = xbmc.getInfoLabel(f"Container({container_id}).ListItemAbsolute({i}).Filenameandpath")

        if dbid:
            json_call("Playlist.Add", playlistid=playlistid, item={"musicvideoid": int(dbid)})
        elif url:
            json_call("Playlist.Add", playlistid=playlistid, item={"file": url})

    # Short delay to allow playlist population
    # This delay is still useful to ensure playlist is fully built before Player.Open
    time.sleep(1.0) 

    # Get first item in the playlist to play explicitly
    first_video = xbmc.getInfoLabel(f"Playlist({playlistid}).File(0)")

    if first_video: # Keep this check, it's good practice
        json_call("Player.Open", item={"playlistid": playlistid, "position": 0}, options={"shuffled": False})

        # All previous attempts to explicitly bring the player to foreground
        # (e.g., ActivateWindow, setFullScreen, FullScreen builtin)
        # are no longer needed here due to the <onclick>Close</onclick> in the XML.
        # Ensure any such lines are removed from this section of your script.

# This line calls the playall() function to run the script
playall()