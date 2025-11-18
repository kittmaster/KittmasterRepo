# skin.madnox/extras/scripts/firstrun_init.py
import xbmc
import time

# Helper function to get skin string setting using executebuiltin
def get_skin_string_setting(setting_id):
    """
    Retrieves a skin string setting using Kodi's built-in Skin.GetString.
    """
    return xbmc.executebuiltin(f"Skin.GetString({setting_id})")

# Helper function to set skin setting (string or bool) using executebuiltin
def set_skin_setting(setting_id, value):
    """
    Sets a skin setting using Kodi's built-in Skin.SetString/SetBool.
    """
    if isinstance(value, bool):
        str_value = 'true' if value else 'false'
        xbmc.executebuiltin(f"Skin.SetBool({setting_id},{str_value})")
    else:
        xbmc.executebuiltin(f"Skin.SetString({setting_id},{value})")

# --- REVISED AND MORE RELIABLE HELPER FUNCTION ---
def is_skin_setting_enabled(setting_id):
    """
    Checks if a skin's boolean setting is enabled using the reliable getCondVisibility.
    Returns True if the setting is 'true', False otherwise.
    """
    # xbmc.getCondVisibility returns 1 (true) or 0 (false) for skin settings
    return xbmc.getCondVisibility(f"Skin.HasSetting({setting_id})") == 1

# --- Main logic ---

# INCREASED DELAY to be safer on slower systems. 2 seconds might be too short.
time.sleep(3.0)

xbmc.log(f"[skin.madnox] firstrun_init.py script started.", level=xbmc.LOGINFO)

# Use the new, more reliable checking function
first_run_done = is_skin_setting_enabled('madnox_firstrun_done')
xbmc.log(f"[skin.madnox] Current 'madnox_firstrun_done' status: '{first_run_done}'", level=xbmc.LOGINFO)

if not first_run_done:
    xbmc.log(f"[skin.madnox] Running first-run initialization block...", level=xbmc.LOGINFO)

    # Log current 'mainmenulayout' before modification
    current_layout = get_skin_string_setting('mainmenulayout')
    xbmc.log(f"[skin.madnox] 'mainmenulayout' BEFORE setting: '{current_layout}'", level=xbmc.LOGINFO)

    # Set the default mainmenulayout
    set_skin_setting('mainmenulayout', 'icons')
    xbmc.log(f"[skin.madnox] Attempted to set 'mainmenulayout' to 'icons'.", level=xbmc.LOGINFO)

    # Verify 'mainmenulayout' immediately after setting
    updated_layout = get_skin_string_setting('mainmenulayout')
    xbmc.log(f"[skin.madnox] 'mainmenulayout' AFTER setting: '{updated_layout}'", level=xbmc.LOGINFO)

    # Set the lock variable to True
    set_skin_setting('madnox_firstrun_done', True)
    xbmc.log(f"[skin.madnox] Attempted to set 'madnox_firstrun_done' to 'true'.", level=xbmc.LOGINFO)

    # ADDED: Force skin to reload to help persist the setting
    xbmc.executebuiltin("Skin.Reload()")
    xbmc.log(f"[skin.madnox] Executed Skin.Reload() to help persist settings.", level=xbmc.LOGINFO)

    xbmc.log(f"[skin.madnox] First-run initialization block complete.", level=xbmc.LOGINFO)
else:
    xbmc.log(f"[skin.madnox] First-run initialization already done. Skipping.", level=xbmc.LOGINFO)

xbmc.log(f"[skin.madnox] firstrun_init.py script finished.", level=xbmc.LOGINFO)