# --- START OF FILE script_decrement_person.py ---
import xbmc

# --- MODULE ENTRY POINT ---
def run(params=None):
    # 1. Self-Clean Ghost Alarms if the dialogs are closed
    if not xbmc.getCondVisibility("Window.IsVisible(movieinformation) | Window.IsVisible(1190)"):
        xbmc.executebuiltin("CancelAlarm(MetaData_Slide_Person,true)")
        return

    # 2. Check Admin Setting to see if feature is disabled completely
    if xbmc.getCondVisibility("Skin.HasSetting(disableautoscrollpersonmetadata)"):
        return

    # 3. Verify context & explicit focus
    # Must mirror XML Router exactly so TMDb Helper 'video' types resolve to Person
    is_person_context = xbmc.getCondVisibility("String.IsEqual(ListItem.DBTYPE,person) | String.IsEqual(ListItem.DBTYPE,actor) | String.IsEqual(ListItem.DBTYPE,video)")
    
    # 9004 (Biography) is only active if the user is focused on the Biography button (100001) OR inside 9004
    active_conditions = "Container(9000).HasFocus(100001) | Control.HasFocus(9004)"
    is_panel_active = is_person_context and xbmc.getCondVisibility(active_conditions)

    # Fetch the "seed" (in seconds) from a Kodi skin string for persons
    seed_str = xbmc.getInfoLabel("Skin.String(personmetascrollingdelayvaluevarb)")
    try:
        seed_val = int(seed_str)
    except (ValueError, TypeError):
        seed_val = 7  # fallback if user typed something invalid

    # If the user is on a different tab, pause the counter by holding it at the seed value and exiting.
    if not is_panel_active:
        xbmc.executebuiltin(f"SetProperty(ItemListCountDownTimerPerson,{seed_val},Home)")
        return

    # Check if logging is disabled
    logging_enabled = xbmc.getCondVisibility("Skin.HasSetting(disablecounterscriptloggingall)")

    # Read the current countdown value for persons
    current_str = xbmc.getInfoLabel("Window(Home).Property(ItemListCountDownTimerPerson)")
    try:
        current_val = int(current_str)
    except (ValueError, TypeError):
        current_val = seed_val

    # --- Detect Manual Scroll ---
    item_9004 = xbmc.getInfoLabel("Container(9004).CurrentItem")
    saved_9004 = xbmc.getInfoLabel("Window(Home).Property(AutoScroll_Saved_Person_9004)")
    script_triggered = xbmc.getInfoLabel("Window(Home).Property(AutoScroll_Script_Triggered_Person)") == "true"
    manual_scroll_detected = False

    if saved_9004 and item_9004 != saved_9004:
        if not script_triggered:
            manual_scroll_detected = True

    if script_triggered:
        xbmc.executebuiltin("ClearProperty(AutoScroll_Script_Triggered_Person,Home)")

    xbmc.executebuiltin(f"SetProperty(AutoScroll_Saved_Person_9004,{item_9004},Home)")
    # ---------------------------

    # If a manual scroll was detected, ONLY reset the timer.
    # Otherwise, perform the normal countdown logic.
    if manual_scroll_detected:
        current_val = seed_val
    else:
        # Decrement or reset the countdown for persons:
        if current_val > 0:
            current_val -= 1
        else:
            # We hit 0, so do the Move() animation for persons:
            xbmc.executebuiltin("Control.Move(9004,1)")
            xbmc.executebuiltin("SetProperty(AutoScroll_Script_Triggered_Person,true,Home)")
            # Reset countdown for persons:
            current_val = seed_val

    # Save the updated countdown value for persons:
    xbmc.executebuiltin(f"SetProperty(ItemListCountDownTimerPerson,{current_val},Home)")

    # Debugging logs for persons (optional):
    if logging_enabled:
        xbmc.log(f"Person Timer - Seed: {seed_val}, Current: {current_val}", level=xbmc.LOGINFO)