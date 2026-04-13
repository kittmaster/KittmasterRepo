import xbmc
import xbmcgui
import json
import time
import threading

window = xbmcgui.Window(10000)

DEFAULT_COLORS = {
    'subtitles.colorpick': 'FFFFFFFF', 'subtitles.bordercolorpick': 'FF000000',
    'subtitles.shadowcolor': 'FF000000', 'subtitles.bgcolorpick': 'FF000000'
}
color_keys = {
    'Applied_Color_GUISettings.Text': 'subtitles.colorpick',
    'Applied_Color_GUISettings.Border': 'subtitles.bordercolorpick',
    'Applied_Color_GUISettings.Shadow': 'subtitles.shadowcolor',
    'Applied_Color_GUISettings.Background': 'subtitles.bgcolorpick'
}

def get_focused_color_hex():
    return xbmc.getInfoLabel('Container(6).ListItem.Label2').upper()

def set_dialog_title_from_context():
    focused_hex = get_focused_color_hex()
    active_prop_name = 'Applied_Color_GUISettings.Text'
    active_setting_id = 'subtitles.colorpick'
    if not focused_hex:
        window.setProperty("MyPickerTitle", "Color Settings")
    else:
        prefix_map = {'Applied_Color_GUISettings.Text': 'Subtitle', 'Applied_Color_GUISettings.Border': 'Border',
                      'Applied_Color_GUISettings.Shadow': 'Shadow', 'Applied_Color_GUISettings.Background': 'Background'}
        prefix = "System"
        for prop, friendly_name in prefix_map.items():
            if window.getProperty(prop).upper() == focused_hex:
                prefix, active_prop_name, active_setting_id = friendly_name, prop, color_keys[prop]
                break
        window.setProperty("MyPickerTitle", f"{prefix}: Color")
    window.setProperty("ActiveAppliedColor", window.getProperty(active_prop_name))
    window.setProperty("ActiveSettingID", active_setting_id)

def run_title_logic_in_background():
    time.sleep(0.2)
    set_dialog_title_from_context()

def get_and_store_colors():
    for prop, setting in color_keys.items():
        req = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.GetSettingValue', 'params': {'setting': setting}}
        resp = json.loads(xbmc.executeJSONRPC(json.dumps(req)))
        window.setProperty(prop, str(resp.get('result', {}).get('value', '')))

def reset_to_default():
    setting_id = window.getProperty("ActiveSettingID")
    if setting_id and setting_id in DEFAULT_COLORS:
        req = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.SetSettingValue',
               'params': {'setting': setting_id, 'value': DEFAULT_COLORS[setting_id]}}
        xbmc.executeJSONRPC(json.dumps(req))

def apply_stored_colors():
    for prop, setting in color_keys.items():
        value = window.getProperty(prop)
        if value:
            req = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.SetSettingValue',
                   'params': {'setting': setting, 'value': value}}
            xbmc.executeJSONRPC(json.dumps(req))

# --- MODULE ENTRY POINT ---
def run(params=None):
    if params is None: params = {}
    
    # Use .get and default to empty string to prevent crashes
    action = params.get('mode', '').lower()
    
    if action == 'set':
        apply_stored_colors()
    elif action == 'reset':
        reset_to_default()
        get_and_store_colors()
        set_dialog_title_from_context()
        xbmc.executebuiltin('Container.Refresh')
    else: 
        # Initial load logic
        window.setProperty("DialogTitle", " ")
        get_and_store_colors()
        threading.Thread(target=run_title_logic_in_background).start()