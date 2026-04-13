import sys
import xbmc
import json
import xbmcgui

# =============================================================================
#  TMDb_Helper_SettingsWriter.py
#  A universal framework for modifying Kodi guisettings via Skin XML.
# =============================================================================

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[TMDb_Helper_SettingsWriter] {msg}", level)

def json_rpc(method, params=None):
    """ Executes a JSON-RPC command and returns the result dictionary. """
    if params is None:
        params = {}
    
    query = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    response = xbmc.executeJSONRPC(json.dumps(query))
    return json.loads(response)

# =============================================================================
#  3. TYPE HANDLING & LOGIC
# =============================================================================

def get_current_setting(setting_id):
    """ Gets the current value and type of a setting. """
    data = json_rpc("Settings.GetSettingValue", {"setting": setting_id})
    if 'result' in data:
        return data['result'] # Returns dict like {'value': 'true', 'default': 'true'}
    return None

def cast_value(new_val_str, current_val):
    """
    Kodi passes XML args as strings. We must cast them to the 
    correct Python type (bool, int) based on what the setting expects.
    """
    # 1. Handle Booleans
    if isinstance(current_val, bool):
        if str(new_val_str).lower() in ('true', '1', 'on', 'yes'):
            return True
        return False
    
    # 2. Handle Integers
    if isinstance(current_val, int):
        try:
            return int(new_val_str)
        except ValueError:
            log(f"Error converting '{new_val_str}' to int.", xbmc.LOGERROR)
            return current_val

    # 3. Handle Floats
    if isinstance(current_val, float):
        try:
            return float(new_val_str)
        except ValueError:
            log(f"Error converting '{new_val_str}' to float.", xbmc.LOGERROR)
            return current_val
            
    # 4. Strings require no conversion
    return str(new_val_str)


# =============================================================================
#  4. ACTIONS
# =============================================================================

def action_toggle(setting_id):
    """ Reads a boolean setting and flips it. """
    result = get_current_setting(setting_id)
    
    if result is not None:
        current_val = result.get('value')
        
        # Verify it is actually a boolean
        if isinstance(current_val, bool):
            new_val = not current_val
            json_rpc("Settings.SetSettingValue", {"setting": setting_id, "value": new_val})
            log(f"Toggled {setting_id} to {new_val}")
        else:
            log(f"Cannot toggle {setting_id}: It is not a boolean (Value: {current_val})", xbmc.LOGWARNING)
    else:
        log(f"Setting {setting_id} not found.", xbmc.LOGERROR)

def action_set(setting_id, raw_value):
    """ Sets a setting to a specific value, handling type conversion automatically. """
    result = get_current_setting(setting_id)
    
    if result is not None:
        current_val = result.get('value')
        
        # Convert the string from XML to the correct type (Bool/Int/String)
        final_value = cast_value(raw_value, current_val)
        
        json_rpc("Settings.SetSettingValue", {"setting": setting_id, "value": final_value})
        log(f"Set {setting_id} to {final_value}")
    else:
        log(f"Setting {setting_id} not found.", xbmc.LOGERROR)

def action_reset(setting_id):
    """ Resets a setting to its default value (if Kodi exposes this). """
    result = get_current_setting(setting_id)
    if result is not None and 'default' in result:
        default_val = result['default']
        json_rpc("Settings.SetSettingValue", {"setting": setting_id, "value": default_val})
        log(f"Reset {setting_id} to default: {default_val}")


# =============================================================================
#  5. MAIN LOGIC
# =============================================================================

def run(params):
    mode = params.get('mode', '')
    setting = params.get('setting', '')
    value = params.get('value', '')

    if not setting:
        log("No setting ID provided.", xbmc.LOGERROR)
    else:
        if mode == 'toggle':
            action_toggle(setting)
        
        elif mode == 'set':
            if value != '':
                action_set(setting, value)
            else:
                log("Mode 'set' requires a 'value' parameter.", xbmc.LOGERROR)
                
        elif mode == 'reset':
            action_reset(setting)
            
        else:
            log(f"Unknown mode: {mode}", xbmc.LOGWARNING)