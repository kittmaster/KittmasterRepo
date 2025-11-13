import xbmc
import xbmcgui
import json
import sys
import time
import threading

# Constants
window = xbmcgui.Window(10000)

# ===================================================================
# <<< START: NEW DATA FOR DEFAULTS >>>
# ===================================================================

# A dictionary holding the out-of-the-box default color values.
DEFAULT_COLORS = {
    'subtitles.colorpick': 'FFFFFFFF',
    'subtitles.bordercolorpick': 'FF000000',
    'subtitles.shadowcolor': 'FF000000',
    'subtitles.bgcolorpick': 'FF000000'
}

# ===================================================================
# <<< END: NEW DATA FOR DEFAULTS >>>
# ===================================================================


def get_focused_color_hex():
    """ Gets the hex value using the robust xbmc.getInfoLabel method. """
    try:
        hex_value = xbmc.getInfoLabel('Container(6).ListItem.Label2')
        if hex_value:
            return hex_value.upper()
        return ""
    except Exception:
        return ""

def set_dialog_title_from_context():
    """
    Deduces the context and sets properties for the title and active color.
    *** NOW ALSO STORES THE ACTIVE SETTING ID FOR THE RESET FUNCTION. ***
    """
    focused_hex = get_focused_color_hex()
    
    active_prop_name = 'Applied_Color_GUISettings.Text' # Default property
    active_setting_id = 'subtitles.colorpick' # Default setting ID

    if not focused_hex:
        window.setProperty("MyPickerTitle", "Color Settings")
    else:
        prefix_map = {
            'Applied_Color_GUISettings.Text': 'Subtitle',
            'Applied_Color_GUISettings.Border': 'Border',
            'Applied_Color_GUISettings.Shadow': 'Shadow',
            'Applied_Color_GUISettings.Background': 'Background'
        }
        prefix = "System"

        for prop_name, friendly_name in prefix_map.items():
            setting_color = window.getProperty(prop_name).upper()
            if setting_color and setting_color == focused_hex:
                prefix = friendly_name
                active_prop_name = prop_name
                # Use the active property name to find the corresponding setting ID
                active_setting_id = color_keys[prop_name]
                break
        
        new_title = f"{prefix}: Color"
        window.setProperty("MyPickerTitle", new_title)

    active_color_value = window.getProperty(active_prop_name)
    window.setProperty("ActiveAppliedColor", active_color_value)
    
    # *** NEW: Store the active setting ID so the reset button knows what to do. ***
    window.setProperty("ActiveSettingID", active_setting_id)
    xbmc.log(f"[ColorSync] Helper: Context set. Active Setting ID is '{active_setting_id}'", level=xbmc.LOGINFO)

def run_title_logic_in_background():
    """ This function runs in a separate thread. """
    time.sleep(0.2)
    set_dialog_title_from_context()

# --- Your existing code ---
color_keys = {
    'Applied_Color_GUISettings.Text': 'subtitles.colorpick',
    'Applied_Color_GUISettings.Border': 'subtitles.bordercolorpick',
    'Applied_Color_GUISettings.Shadow': 'subtitles.shadowcolor',
    'Applied_Color_GUISettings.Background': 'subtitles.bgcolorpick'
}
def get_and_store_colors():
    for prop, setting in color_keys.items():
        # ... (function is unchanged) ...
        request = { 'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.GetSettingValue', 'params': {'setting': setting} }
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
        value = response.get('result', {}).get('value', '')
        window.setProperty(prop, str(value))

# ===================================================================
# <<< START: NEW FUNCTION FOR RESETTING >>>
# ===================================================================
def reset_to_default():
    """ Resets the currently active color setting to its default value. """
    setting_id = window.getProperty("ActiveSettingID")
    if not setting_id:
        xbmc.log("[ColorSync] Reset Error: No ActiveSettingID found.", level=xbmc.LOGERROR)
        return

    default_value = DEFAULT_COLORS.get(setting_id)
    if default_value is None:
        xbmc.log(f"[ColorSync] Reset Error: No default value found for '{setting_id}'.", level=xbmc.LOGERROR)
        return

    # Apply the default value using JSON-RPC
    request = { 'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.SetSettingValue', 'params': {'setting': setting_id, 'value': default_value} }
    xbmc.executeJSONRPC(json.dumps(request))
    xbmc.log(f"[ColorSync] Reset: Set '{setting_id}' to default value '{default_value}'.", level=xbmc.LOGINFO)

# ===================================================================
# <<< END: NEW FUNCTION FOR RESETTING >>>
# ===================================================================

def apply_stored_colors():
    for prop, setting in color_keys.items():
        # ... (function is unchanged) ...
        value = window.getProperty(prop)
        if value:
            request = { 'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.SetSettingValue', 'params': {'setting': setting, 'value': value} }
            xbmc.executeJSONRPC(json.dumps(request))

# --- FINAL Main Logic ---
action = sys.argv[1] if len(sys.argv) > 1 else ''

if action.lower() == 'set':
    apply_stored_colors()

elif action.lower() == 'reset':
    # Handle the reset action from the button click
    reset_to_default()
    # After resetting, we must update all our properties and refresh the UI
    get_and_store_colors()
    set_dialog_title_from_context()
    xbmc.executebuiltin('Container.Refresh') # Refresh the color grid

else:
    # This is the initial setup when the dialog loads
    window.setProperty("DialogTitle", " ")
    get_and_store_colors()
    thread = threading.Thread(target=run_title_logic_in_background)
    thread.start()