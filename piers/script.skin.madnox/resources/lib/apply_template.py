import xbmc
import os
from xml.etree import ElementTree

SCRIPT_NAME = "[Madnox Template]"
TEMPLATE_FILENAME = 'settings_template.xml'

def run(params=None):
    xbmc.log(f"{SCRIPT_NAME} Apply Template Script: INITIALIZING.", level=xbmc.LOGINFO)

    # Check if this is the automatic first-run or a manual user reset
    is_first_run = not xbmc.getCondVisibility('Skin.HasSetting(Madnox.Settings.Initialized)')

    try:
        template_file_path = os.path.join(os.path.dirname(__file__), TEMPLATE_FILENAME)
        
        if not os.path.exists(template_file_path):
            xbmc.log(f"{SCRIPT_NAME} FATAL ERROR: Template file not found.", level=xbmc.LOGERROR)
            return
        
        tree = ElementTree.parse(template_file_path)
        root = tree.getroot()
        settings_list = root.findall('setting')

        for i, setting in enumerate(settings_list):
            setting_id = setting.get('id')
            setting_type = setting.get('type')
            setting_value = setting.text if setting.text is not None else ''

            if not setting_id or not setting_type:
                continue

            builtin_command = ''
            if setting_type == 'bool':
                builtin_command = f'Skin.SetBool({setting_id},{setting_value})'
            elif setting_type == 'string':
                builtin_command = f'Skin.SetString({setting_id},{setting_value})'
            elif setting_type == 'integer':
                builtin_command = f'Skin.SetInteger({setting_id},{setting_value})'
            
            if builtin_command:
                xbmc.executebuiltin(builtin_command)

    except Exception as e:
        xbmc.log(f"{SCRIPT_NAME} Error: {e}", level=xbmc.LOGERROR)
        return

    # --- FINAL ACTIONS ---
    if is_first_run:
        # First Run: Set flag and reload silently
        xbmc.executebuiltin('Skin.SetBool(Madnox.Settings.Initialized)')
        xbmc.log(f"{SCRIPT_NAME} First run detected. Reloading skin.", level=xbmc.LOGINFO)
        xbmc.executebuiltin('ReloadSkin()')
    else:
        # Manual Reset: Close user dialogs, reload, and notify success
        xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
        xbmc.executebuiltin('Dialog.Close(1107)')
        xbmc.executebuiltin('ReloadSkin()')

        monitor = xbmc.Monitor()
        if not monitor.waitForAbort(3.5):
            xbmc.executebuiltin('Notification(Settings Applied, Factory defaults restored successfully., 7000)')