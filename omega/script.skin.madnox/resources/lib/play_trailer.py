import xbmc

def run(params):
    # 1. Try to get path from the parameters passed
    trailer_path = params.get('path', '').strip('"')

    # 2. FALLBACK: If path is empty, try to get it directly from Kodi
    if not trailer_path:
        trailer_path = xbmc.getInfoLabel('ListItem.Trailer')
    
    # 3. If still empty, the movie actually has no trailer assigned
    if not trailer_path:
        xbmc.log("[play_trailer] No trailer found for this item.", xbmc.LOGWARNING)
        xbmc.executebuiltin('Notification(Trailer, No trailer available for this item, 5000)')
        return

    # Proceed with playback
    xbmc.executebuiltin("Dialog.Close(MovieInformation)")
    xbmc.executebuiltin(f"PlayMedia({trailer_path})")

    monitor = xbmc.Monitor()
    xbmc.sleep(1000)

    while not monitor.abortRequested():
        if not xbmc.getCondVisibility("Player.HasVideo"):
            break
        xbmc.sleep(500)

    if not monitor.abortRequested():
        xbmc.sleep(500)
        xbmc.executebuiltin("Action(Info)")