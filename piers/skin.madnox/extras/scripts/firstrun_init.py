# skin.madnox/extras/scripts/firstrun_init.py
import xbmc
import time # Import the time module for sleep functionality

# Helper function to get skin string setting using executebuiltin
def get_skin_string_setting(setting_id):
    """
    Retrieves a skin string setting using Kodi's built-in Skin.GetString.
    Returns an empty string or 'None' (as string) if the setting doesn't exist or is empty.
    """
    return xbmc.executebuiltin(f"Skin.GetString({setting_id})")

# Helper function to set skin setting (string or bool) using executebuiltin
def set_skin_setting(setting_id, value):
    """
    Sets a skin setting using Kodi's built-in Skin.SetString/SetBool.
    Handles conversion of Python bools to 'true'/'false' strings.
    """
    if isinstance(value, bool):
        # Convert Python boolean to 'true' or 'false' string for Skin.SetBool
        str_value = 'true' if value else 'false'
        xbmc.executebuiltin(f"Skin.SetBool({setting_id},{str_value})")
    else:
        # Assume it's a string or convertible to string for Skin.SetString
        xbmc.executebuiltin(f"Skin.SetString({setting_id},{value})")

# Helper function to check if a boolean skin setting is true using Skin.HasSetting
def has_skin_setting(setting_id):
    """
    Checks if a skin setting exists AND its value evaluates to true.
    Uses Skin.HasSetting(id) built-in, which returns 'true' or 'false' string.
    """
    result = xbmc.executebuiltin(f"Skin.HasSetting({setting_id})")
    # Compare to the string 'true' returned by the built-in
    return result == 'true'

# --- Main logic ---

# ADD A SMALL DELAY HERE TO ALLOW KODI TO FULLY LOAD SETTINGS
time.sleep(2.0) # Sleep for 50 milliseconds (start small, can increase if needed)

xbmc.log(f"[skin.madnox] firstrun_init.py script started (with delay, using Skin.HasSetting for check).", level=xbmc.LOGINFO)

first_run_done = has_skin_setting('madnox_firstrun_done')
xbmc.log(f"[skin.madnox] Current 'madnox_firstrun_done' status (via Skin.HasSetting): '{first_run_done}'", level=xbmc.LOGINFO)

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

    xbmc.log(f"[skin.madnox] First-run initialization block complete.", level=xbmc.LOGINFO)
else:
    xbmc.log(f"[skin.madnox] First-run initialization already done. Status: '{first_run_done}'. Skipping.", level=xbmc.LOGINFO)

xbmc.log(f"[skin.madnox] firstrun_init.py script finished.", level=xbmc.LOGINFO)