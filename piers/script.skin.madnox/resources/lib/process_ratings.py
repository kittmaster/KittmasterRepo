import xbmc
import time

def calculate_and_set_ratings(params):
    # 1. Get Output Property Names from Params
    out_tmdb = params.get("output_tmdb", "InfoDialog.TMDb.Percent")
    out_imdb = params.get("output_imdb", "InfoDialog.IMDb.Percent")
    out_user = params.get("output_user", "InfoDialog.User.Formatted")
    out_pct  = params.get("output_user_percent", "InfoDialog.User.Percent")
    out_f5   = params.get("output_file_5star", "InfoDialog.User.File5Star")
    out_f10  = params.get("output_file_10star", "InfoDialog.User.File10Star")
    out_prec = params.get("output_file_precision", "InfoDialog.User.FilePrecision")
    out_star = params.get("output_star", "InfoDialog.User.StarValue")
    out_ready = params.get("output_ready", "InfoDialog.Ratings.Ready")

    # --- NEW: Check skin setting for display preference ---
    # True  = Show as Number (e.g., 8.5)
    # False = Show as Percentage (e.g., 85)
    use_numbers = xbmc.getCondVisibility("Skin.HasSetting(RatingsAsNumbers)")

    # 2. Bio/Person Protection
    if xbmc.getCondVisibility("String.IsEqual(ListItem.DBTYPE,person) | String.IsEqual(ListItem.DBTYPE,actor) | String.IsEqual(ListItem.Property(item.type),person)"):
        return

    # CLEAR the ready flag first — this causes the grouplist to hide,
    # then we set it again below to force a full layout recalculation
    xbmc.executebuiltin(f"ClearProperty({out_ready},Home)")

    # --- 3. Process TMDb ---
    tmdb = xbmc.getInfoLabel('ListItem.Property(TMDb_Rating)') or \
           xbmc.getInfoLabel('Window(Home).Property(TMDbHelper.ListItem.TMDb_Rating)') or \
           xbmc.getInfoLabel('ListItem.Rating(themoviedb)')
    if tmdb:
        try:
            if use_numbers:
                val = f"{float(tmdb):.1f}"
            else:
                val = str(int(round(float(tmdb) * 10)))
            xbmc.executebuiltin(f"SetProperty({out_tmdb},{val},Home)")
        except: pass

    # --- 4. Process IMDb ---
    imdb = xbmc.getInfoLabel('Window(Home).Property(TMDbHelper.ListItem.IMDb_Rating)') or \
           xbmc.getInfoLabel('ListItem.Rating(imdb)')
    if imdb:
        try:
            if use_numbers:
                val = f"{float(imdb):.1f}"
            else:
                val = str(int(round(float(imdb) * 10)))
            xbmc.executebuiltin(f"SetProperty({out_imdb},{val},Home)")
        except: pass

    # --- 5. Process User/Star Ratings ---
    user = xbmc.getInfoLabel('ListItem.Property(TMDb_Rating)') or \
           xbmc.getInfoLabel('Window(Home).Property(TMDbHelper.ListItem.TMDb_Rating)') or \
           xbmc.getInfoLabel('ListItem.Rating(themoviedb)') or \
           xbmc.getInfoLabel('ListItem.Rating')
    if user:
        try:
            n = float(user)
            # Static formatted output
            xbmc.executebuiltin(f"SetProperty({out_user},{round(n, 1):.1f},Home)")
            
            # Toggled value (Percent OR Number based on setting)
            if use_numbers:
                toggled_user = f"{n:.1f}"
            else:
                toggled_user = str(int(round(n * 10)))
                
            xbmc.executebuiltin(f"SetProperty({out_pct},{toggled_user},Home)")
            
            # Other visual outputs
            xbmc.executebuiltin(f"SetProperty({out_f5},rating{int(round(n / 2.0))},Home)")
            xbmc.executebuiltin(f"SetProperty({out_f10},{int(round(n))},Home)")
            xbmc.executebuiltin(f"SetProperty({out_prec},{round(n, 1):.1f},Home)")
            xbmc.executebuiltin(f"SetProperty({out_star},{int(round(n / 2.0))},Home)")
        except: pass

    # SET the ready flag LAST — this re-shows the grouplist, forcing a fresh layout pass
    xbmc.executebuiltin(f"SetProperty({out_ready},true,Home)")


def run(params):
    mode = params.get("mode", "calculate")
    monitor = xbmc.Monitor() 
    
    if mode == 'monitor':
        # --- HUD MODE (Real-time polling) ---
        window_id = params.get("window_id", "98")
        
        # MUTEX LOCK: Ensure only one monitor loop runs at a time
        if xbmc.getInfoLabel('Window(Home).Property(RatingScriptIsRunning)') == 'true':
            return
        xbmc.executebuiltin('SetProperty(RatingScriptIsRunning,true,Home)')
        
        last_dbid = None
        invisible_count = 0
        
        try:
            while not monitor.abortRequested():
                # DEBOUNCE VISIBILITY: Kodi's window engine causes visibility to flicker to 'False' 
                # for a split second during window navigation. We wait 3 loops (~1.3s) before actually dying.
                if not xbmc.getCondVisibility(f"Window.IsVisible({window_id})"):
                    invisible_count += 1
                    if invisible_count >= 3:
                        break
                else:
                    invisible_count = 0

                curr_dbid = xbmc.getInfoLabel("ListItem.DBID")
                
                if curr_dbid and curr_dbid != last_dbid:
                    calculate_and_set_ratings(params)
                    last_dbid = curr_dbid
                
                if monitor.waitForAbort(0.45):
                    break
        finally:
            xbmc.executebuiltin('ClearProperty(RatingScriptIsRunning,Home)')
            # Backup: Force clear the scriptdialog property from Window 10000 to keep the HUD clean upon true exit
            xbmc.executebuiltin('ClearProperty(scriptdialog,10000)')
            
    else:
        # ONE-SHOT MODE
        exec_id = str(time.time())
        xbmc.executebuiltin(f"SetProperty(RatingExecID,{exec_id},Home)")

        # Use a shorter debounce on fresh open (properties are empty),
        # longer on return-from-person path (properties were previously populated)
        # so ListItem has time to restore to movie context.
        out_ready = params.get("output_ready", "InfoDialog.Ratings.Ready")
        is_return_trip = xbmc.getInfoLabel(f"Window(Home).Property({out_ready})") == 'true'
        debounce = 0.65 if is_return_trip else 0.15

        if not monitor.waitForAbort(debounce):

            current_id = xbmc.getInfoLabel("Window(Home).Property(RatingExecID)")
            if current_id != exec_id:
                return

            # Retry loop: if ListItem is still in person context,
            # wait a bit longer for Kodi to restore the movie ListItem
            max_retries = 4
            for attempt in range(max_retries):
                is_person = xbmc.getCondVisibility(
                    "String.IsEqual(ListItem.DBTYPE,person) | "
                    "String.IsEqual(ListItem.DBTYPE,actor) | "
                    "String.IsEqual(ListItem.Property(item.type),person)"
                )
                if not is_person:
                    break
                if attempt < max_retries - 1:
                    if monitor.waitForAbort(0.3):
                        return
                else:
                    return  # Genuinely in person context, do nothing

            calculate_and_set_ratings(params)