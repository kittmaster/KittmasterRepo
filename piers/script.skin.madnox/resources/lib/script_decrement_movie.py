# --- START OF FILE script_decrement_movie.py ---
import xbmc

# --- MODULE ENTRY POINT ---
def run(params=None):
    # 1. Self-Clean Ghost Alarms if the dialogs are closed
    if not xbmc.getCondVisibility("Window.IsVisible(movieinformation) | Window.IsVisible(1190)"):
        xbmc.executebuiltin("CancelAlarm(MetaData_Slide_Movie,true)")
        return

    # 2. Check Admin Setting to see if feature is disabled completely
    if xbmc.getCondVisibility("Skin.HasSetting(disableautoscrollmoviemetadata)"):
        return

    # 3. Verify context & explicit focus
    # Must mirror XML Router exactly to prevent overlap with Person/Music views
    is_video_context = xbmc.getCondVisibility("!String.IsEqual(ListItem.DBTYPE,musicvideo) + !String.IsEqual(ListItem.DBTYPE,person) + !String.IsEqual(ListItem.DBTYPE,actor) + !String.IsEqual(ListItem.DBTYPE,video)")
    
    # Panels 9004/9010 are only truly active if the user is focused on their specific toggle buttons in 9000, 
    # OR if the user has navigated directly into the panels themselves.
    active_conditions = (
        "Container(9000).HasFocus(110) | "
        "Container(9000).HasFocus(112) | "
        "Container(9000).HasFocus(107) | "
        "Control.HasFocus(9004) | "
        "Control.HasFocus(9010)"
    )
    is_panel_active = is_video_context and xbmc.getCondVisibility(active_conditions)

    # Fetch the "seed" (in seconds) from a Kodi skin string for movies
    seed_str = xbmc.getInfoLabel("Skin.String(moviemetascrollingdelayvaluevarb)")
    try:
        seed_val = int(seed_str)
    except (ValueError, TypeError):
        seed_val = 7  # fallback if user typed something invalid

    # If the user is on a different tab, pause the counter by holding it at the seed value and exiting.
    if not is_panel_active:
        xbmc.executebuiltin(f"SetProperty(ItemListCountDownTimerMovie,{seed_val},Home)")
        return

    # Check if logging is disabled
    logging_enabled = xbmc.getCondVisibility("Skin.HasSetting(disablecounterscriptloggingall)")

    # Read the current countdown value for movies
    current_str = xbmc.getInfoLabel("Window(Home).Property(ItemListCountDownTimerMovie)")
    try:
        current_val = int(current_str)
    except (ValueError, TypeError):
        current_val = seed_val

    # --- Detect Manual Scroll ---
    item_9004 = xbmc.getInfoLabel("Container(9004).CurrentItem")
    item_9010 = xbmc.getInfoLabel("Container(9010).CurrentItem")
    saved_9004 = xbmc.getInfoLabel("Window(Home).Property(AutoScroll_Saved_Movie_9004)")
    saved_9010 = xbmc.getInfoLabel("Window(Home).Property(AutoScroll_Saved_Movie_9010)")
    script_triggered = xbmc.getInfoLabel("Window(Home).Property(AutoScroll_Script_Triggered_Movie)") == "true"
    manual_scroll_detected = False

    if (saved_9004 and item_9004 != saved_9004) or (saved_9010 and item_9010 != saved_9010):
        if not script_triggered:
            manual_scroll_detected = True

    if script_triggered:
        xbmc.executebuiltin("ClearProperty(AutoScroll_Script_Triggered_Movie,Home)")

    xbmc.executebuiltin(f"SetProperty(AutoScroll_Saved_Movie_9004,{item_9004},Home)")
    xbmc.executebuiltin(f"SetProperty(AutoScroll_Saved_Movie_9010,{item_9010},Home)")
    # ---------------------------

    # If a manual scroll was detected, ONLY reset the timer.
    # Otherwise, perform the normal countdown logic.
    if manual_scroll_detected:
        current_val = seed_val
    else:
        # Decrement or reset the countdown for movies:
        if current_val > 0:
            current_val -= 1
        else:
            # We hit 0, so do the Move() animation for movies:
            xbmc.executebuiltin("Control.Move(9004,1)")
            xbmc.executebuiltin("Control.Move(9010,1)")
            xbmc.executebuiltin("SetProperty(AutoScroll_Script_Triggered_Movie,true,Home)")
            # Reset countdown for movies:
            current_val = seed_val

    # Save the updated countdown value for movies:
    xbmc.executebuiltin(f"SetProperty(ItemListCountDownTimerMovie,{current_val},Home)")

    # Conditionally log debugging messages for movies if logging is enabled:
    if logging_enabled:
        xbmc.log(f"Movie Timer - Seed: {seed_val}, Current: {current_val}", level=xbmc.LOGINFO)