import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime

# Paths
SKIN_SETTINGS_PATH = xbmcvfs.translatePath('special://profile/addon_data/skin.madnox/settings.xml')
PRESETS_DIR = xbmcvfs.translatePath('special://profile/addon_data/script.skin.madnox/presets/')

def is_valid_skin_settings(filepath):
    """Reads an external file to ensure it is valid XML and formatted for Kodi settings."""
    try:
        f = xbmcvfs.File(filepath)
        content = f.read()
        f.close()
        
        root = ET.fromstring(content)
        if root.tag != 'settings':
            return False
        return True
    except Exception as e:
        xbmc.log(f"Madnox Import Validation Failed: {e}", xbmc.LOGERROR)
        return False

class PresetManagerUI(xbmcgui.WindowXMLDialog):
    def onInit(self):
        """Called automatically when the window is loaded."""
        if not os.path.exists(PRESETS_DIR):
            os.makedirs(PRESETS_DIR)
            
        self.preset_list_control = self.getControl(900)
        self.populate_list()

    def populate_list(self):
        """Reads the presets directory and populates the UI list."""
        self.preset_list_control.reset()
        
        if not os.path.exists(PRESETS_DIR):
            return

        files = [f for f in os.listdir(PRESETS_DIR) if f.endswith('.xml')]
        files.sort(reverse=True) # Newest first based on 24h timestamp
        
        use_12_hour = xbmc.getCondVisibility('Skin.HasSetting(Madnox.Presets.Use12Hour)')

        for file in files:
            display_name = file.replace('.xml', '')
            
            # Use Regex to cleanly extract Name, Date, and Time from our specific format
            # Format: AnyName_YYYY-MM-DD_HH-MM
            match = re.search(r'^(.*)_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2})$', display_name)
            
            if match:
                name_part = match.group(1)
                date_part = match.group(2)
                time_part = match.group(3)
                
                # Format the time nicely for the UI
                if use_12_hour:
                    time_obj = datetime.strptime(time_part, "%H-%M")
                    # Convert to AM/PM and remove leading zero from hours
                    display_time = time_obj.strftime("%I:%M %p").lstrip('0') 
                else:
                    display_time = time_part.replace('-', ':')
                    
                label2_part = f"{date_part} • {display_time}"
            else:
                name_part = display_name
                label2_part = "Imported / Unknown Date"
            
            list_item = xbmcgui.ListItem(name_part)
            list_item.setLabel2(label2_part)
            list_item.setProperty('full_filename', file)
            
            self.preset_list_control.addItem(list_item)

    def get_selected_filename(self):
        """Helper to get the actual file name of the currently focused list item."""
        item = self.preset_list_control.getSelectedItem()
        if item:
            return item.getProperty('full_filename')
        return None

    def onClick(self, controlId):
        """Handles all button clicks in the XML layout."""
        
        # --- LEFT MENU GLOBALS ---
        if controlId == 9001:
            self.close()
            
        elif controlId == 9002:
            self.create_preset()
            
        elif controlId == 9003:
            self.import_preset()
            
        elif controlId == 9004:
            self.export_preset()
            
        elif controlId == 9005:
            self.delete_all_presets()
            
        elif controlId == 9006: # AM/PM TOGGLE
            xbmc.executebuiltin('Skin.ToggleSetting(Madnox.Presets.Use12Hour)')
            xbmc.sleep(100) # Give Kodi 100ms to register the skin setting change
            self.populate_list() # Repopulate the list with new time formats immediately

        # --- RIGHT MENU CONTEXT ACTIONS ---
        elif controlId == 9104:
            self.load_selected()
            
        elif controlId == 9105:
            self.rename_selected()
            
        elif controlId == 9106:
            self.delete_selected()

    def onAction(self, action):
        """Catches backspace/escape keys to close the dialog natively."""
        if action.getId() in [9, 10, 92, 216]: # ESC, BACK, etc.
            self.close()

    # ==========================================
    # ACTION LOGIC
    # ==========================================

    def create_preset(self):
        keyboard = xbmc.Keyboard('', 'Enter preset name (Leave blank for auto-name)')
        keyboard.doModal()
        
        if keyboard.isConfirmed():
            preset_name = keyboard.getText().strip()
            safe_name = "Madnox" if not preset_name else "".join(c for c in preset_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            
            final_filename = f"{safe_name}_{timestamp}.xml"
            preset_file = os.path.join(PRESETS_DIR, final_filename)

            if os.path.exists(preset_file):
                if not xbmcgui.Dialog().yesno("Madnox Presets", f"Preset '{final_filename}' already exists.\nOverwrite?"):
                    return

            if xbmcvfs.copy(SKIN_SETTINGS_PATH, preset_file):
                xbmcgui.Dialog().notification("Madnox Presets", "New preset saved!", xbmcgui.NOTIFICATION_INFO)
                self.populate_list()
            else:
                xbmcgui.Dialog().notification("Madnox Presets", "Failed to save preset.", xbmcgui.NOTIFICATION_ERROR)

    def import_preset(self):
        import_file = xbmcgui.Dialog().browse(1, 'Select Madnox Settings File', 'files', '.xml')
        
        if import_file:
            if not is_valid_skin_settings(import_file):
                xbmcgui.Dialog().ok("Madnox Import", "Import Failed!", "The selected file is not a valid Kodi settings file.", "Please select a valid XML file.")
                return

            filename = os.path.basename(import_file) if not import_file.endswith('/') else "Imported_Preset.xml"
            dest = os.path.join(PRESETS_DIR, filename)

            if xbmcvfs.copy(import_file, dest):
                xbmcgui.Dialog().notification("Madnox Import", "Preset added to library!", xbmcgui.NOTIFICATION_INFO)
                self.populate_list()
            else:
                xbmcgui.Dialog().notification("Madnox Import", "Failed to import file.", xbmcgui.NOTIFICATION_ERROR)

    def export_preset(self):
        export_folder = xbmcgui.Dialog().browse(3, 'Select Export Destination', 'files')
        
        if export_folder:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            final_filename = f"Madnox_Export_{timestamp}.xml"
            
            export_path = f"{export_folder}{final_filename}" if export_folder.endswith('/') or export_folder.endswith('\\') else f"{export_folder}/{final_filename}"

            if xbmcvfs.copy(SKIN_SETTINGS_PATH, export_path):
                xbmcgui.Dialog().notification("Madnox Export", "Current setup exported successfully!", xbmcgui.NOTIFICATION_INFO)
            else:
                xbmcgui.Dialog().notification("Madnox Export", "Export Failed. Check permissions.", xbmcgui.NOTIFICATION_ERROR)

    def delete_all_presets(self):
        if self.preset_list_control.size() == 0:
            return
            
        confirm = xbmcgui.Dialog().yesno("WARNING", "Are you absolutely sure you want to delete ALL saved presets?", autoclose=5000)
        if confirm:
            files = [f for f in os.listdir(PRESETS_DIR) if f.endswith('.xml')]
            for f in files:
                xbmcvfs.delete(os.path.join(PRESETS_DIR, f))
            self.populate_list()
            xbmcgui.Dialog().notification("Madnox Presets", "All presets deleted.", xbmcgui.NOTIFICATION_INFO)

    def load_selected(self):
        filename = self.get_selected_filename()
        if not filename: return
        
        source_path = os.path.join(PRESETS_DIR, filename)

        if xbmcgui.Dialog().yesno("Madnox Presets", f"Load {filename}?\nThis will overwrite your current settings.", autoclose=5000):
            if xbmcvfs.copy(source_path, SKIN_SETTINGS_PATH):
                xbmcgui.Dialog().notification("Madnox Presets", "Preset Loaded! Reloading...", xbmcgui.NOTIFICATION_INFO)
                self.close()
                xbmc.sleep(500)
                xbmc.executebuiltin("ReloadSkin()")
            else:
                xbmcgui.Dialog().notification("Madnox Presets", "Failed to load preset.", xbmcgui.NOTIFICATION_ERROR)

    def rename_selected(self):
        filename = self.get_selected_filename()
        if not filename: return
        
        current_path = os.path.join(PRESETS_DIR, filename)
        
        # Strip the .xml extension for the user to edit
        keyboard = xbmc.Keyboard(filename.replace('.xml', ''), 'Enter new name')
        keyboard.doModal()
        
        if keyboard.isConfirmed() and keyboard.getText():
            new_name = keyboard.getText().strip()
            # Clean it to make sure they didn't put weird characters in it
            safe_name = "".join(c for c in new_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            if safe_name:
                new_filename = f"{safe_name}.xml"
                new_path = os.path.join(PRESETS_DIR, new_filename)
                
                xbmcvfs.rename(current_path, new_path)
                self.populate_list()

    def delete_selected(self):
        filename = self.get_selected_filename()
        if not filename: return
        
        if xbmcgui.Dialog().yesno("Madnox Presets", f"Are you sure you want to delete:\n{filename}?"):
            xbmcvfs.delete(os.path.join(PRESETS_DIR, filename))
            self.populate_list()

# ==========================================
# ENTRY POINT
# ==========================================
def run():
    try:
        skin_path = xbmcaddon.Addon('skin.madnox').getAddonInfo('path')
        ui = PresetManagerUI('Custom_1132_PresetManager.xml', skin_path, 'default', '1080i')
        ui.doModal()
        del ui
    except Exception as e:
        xbmc.log(f"Madnox PresetManager Error: Failed to load WindowXML - {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Madnox Error", "Could not load Preset Manager UI.", xbmcgui.NOTIFICATION_ERROR)