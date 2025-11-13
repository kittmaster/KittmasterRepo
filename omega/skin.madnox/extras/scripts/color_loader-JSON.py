import sys
import xbmc
import xbmcgui
import xbmcvfs
import xml.etree.ElementTree as ET
import threading
import time
import json # Added import for JSON-RPC

class MyColorDialog(xbmcgui.WindowXMLDialog):
    """
    A custom dialog that references your Custom_1104_DialogOverlayColorPicker.xml (id=1104)
    and populates the <panel> with color swatches. It updates "SelectedColor" on click,
    auto-refreshes if 'mycolorfile' changes, and monitors the active panel setting so that
    if its value is NULL, the applied color preview shows "Default". All hex values are
    converted to uppercase.
    """
    def __init__(self, xmlFilename, scriptPath, color_file=None):
        super().__init__()
        self.color_file = color_file
        self._monitor_stop = False
        self._monitor_thread = None
        self._last_palette_path = ""  # track last known path from Skin.String(mycolorfile)
        self.active_panel_setting = ""  # to store the active setting name (e.g., "PanelStyle.color" or "subtitles.font.color")

    def onInit(self):
        """
        Called after the XML is loaded. Populates the panel, sets slider values, and reads the current
        applied color from the Home window so the preview label is populated. Also stores the active
        panel setting for later use.
        """
        super().onInit()

        # 1) Decide which color file to load on first run
        if not self.color_file:
            from_skin = xbmc.getInfoLabel("Skin.String(mycolorfile)")
            if from_skin:
                self.color_file = xbmcvfs.translatePath(from_skin)
            else:
                self.color_file = xbmcvfs.translatePath("special://skin/extras/colors/madnox-(24-colors).xml")
        self._last_palette_path = self.color_file

        # 2) Grab the active panel parameter (which is now either JSON-RPC setting ID or Skin.String name)
        param_name = xbmc.getInfoLabel("Window(Home).Property(ActiveControlPanelName)")
        self.active_panel_setting = param_name
        current_color = "" # Initialize empty
        
        # Determine if it's a JSON-RPC setting (e.g., "subtitles.xyz") or a Skin.String setting
        # This uses the specific prefix for subtitle settings as a discriminator.
        is_jsonrpc_setting = param_name and param_name.startswith("subtitles.")

        if param_name:
            if is_jsonrpc_setting:
                try:
                    # Use JSON-RPC to get the global setting value for core settings
                    json_string = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.GetSettingValue', 'params': {'setting': param_name}}
                    json_call = json.dumps(json_string)
                    result = xbmc.executeJSONRPC(json_call)
                    parsed_result = json.loads(result)
                    
                    # Retrieve the value directly. It should already be a hex string like "FF000000"
                    retrieved_value = parsed_result.get('result', {}).get('value')

                    if retrieved_value is not None:
                        current_color = str(retrieved_value).lstrip("#").upper() # Ensure clean uppercase hex string
                        xbmc.log(f"[MyColorDialog] JSONRPC GetSettingValue for {param_name} returned: {current_color}", xbmc.LOGINFO)
                    else:
                        xbmc.log(f"[MyColorDialog] JSONRPC GetSettingValue for {param_name} returned no value.", xbmc.LOGINFO)

                except Exception as e:
                    xbmc.log(f"[MyColorDialog] Error getting setting via JSON-RPC for {param_name}: {e}", xbmc.LOGERROR)
            else:
                # Use Skin.String for skin-specific settings
                # Also consider ActiveControlPanelNameValue for initial population, if set by XML
                current_color_from_prop = xbmc.getInfoLabel("Window(Home).Property(ActiveControlPanelNameValue)")
                if current_color_from_prop:
                    current_color = current_color_from_prop.lstrip("#").upper()
                    xbmc.log(f"[MyColorDialog] Retrieved initial color from ActiveControlPanelNameValue: {current_color}", xbmc.LOGINFO)
                else:
                    current_color = xbmc.getInfoLabel(f"Skin.String({param_name})")
                    if current_color:
                        current_color = current_color.lstrip("#").upper()
                    xbmc.log(f"[MyColorDialog] Skin.String GetInfoLabel for {param_name} returned: {current_color}", xbmc.LOGINFO)

        # 3) If current_color is non-empty, update our properties
        if current_color and current_color != "NONE": # "NONE" can be a string default in some settings
            # Ensure it's 8 characters (AARRGGBB), pad with FF if only 6 (RGB)
            if len(current_color) == 6:
                current_color = "FF" + current_color
            elif len(current_color) != 8:
                xbmc.log(f"[MyColorDialog] Warning: Retrieved color string has unexpected length: {current_color}. Defaulting to FFFFFFFF.", xbmc.LOGWARNING)
                current_color = "FFFFFFFF" # Fallback to opaque white

            self.setProperty("SelectedColorNumOnly", current_color)
            self.setProperty("ColorSelectedPicker", current_color)
            xbmc.log(f"[MyColorDialog] Pre-populating color from {param_name} = {current_color}", xbmc.LOGINFO)
        else:
            # If current_color is empty or "NONE", set preview to "Default"
            self.setProperty("ColorSelectedPicker", "Default")
            self.setProperty("SelectedColorNumOnly", "FFFFFFFF") # Default to opaque white for internal use
            xbmc.log("[MyColorDialog] No applied color; setting preview to 'Default'", xbmc.LOGINFO)

        self.getControl(14).setEnabled(True) # Ensure sliders are enabled for the first time
        self._slider_a_val = int(xbmc.getInfoLabel("$VAR[Def_Hex_To_Percent_A]"))
        self._slider_r_val = int(xbmc.getInfoLabel("$VAR[Def_Hex_To_Percent_R]"))
        self._slider_g_val = int(xbmc.getInfoLabel("$VAR[Def_Hex_To_Percent_G]"))
        self._slider_b_val = int(xbmc.getInfoLabel("$VAR[Def_Hex_To_Percent_B]"))
        self.getControl(101).setPercent(self._slider_a_val)
        self.getControl(102).setPercent(self._slider_r_val)
        self.getControl(103).setPercent(self._slider_g_val)
        self.getControl(104).setPercent(self._slider_b_val)
        
        self.populate_colors()

        # Start monitoring in a separate thread
        self._monitor_thread = threading.Thread(target=self.monitor_mycolorfile)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()

    def onClick(self, controlId):
        """
        Handles clicks on controls.
        """
        new_color_hex_str = None

        if controlId == 6:  # Click on a color swatch in the palette panel
            panel = self.getControl(6)
            item = panel.getSelectedItem()
            if item:
                new_color_hex_str = (item.getProperty("SelectedColorNumOnly") or "FFFFFFFF").upper()
                xbmc.log(f"[MyColorDialog] Palette color selected: {new_color_hex_str}", xbmc.LOGINFO)

        elif controlId == 3203: # Apply button click
            # Get the current color from the sliders, which is already in AARRGGBB hex format
            new_color_hex_str = (xbmc.getInfoLabel("$VAR[Def_Percent_To_Hex_Color]") or "FFFFFFFF").lstrip("#").upper()
            xbmc.log(f"[MyColorDialog] Apply button clicked. New color from sliders: {new_color_hex_str}", xbmc.LOGINFO)
            
        elif controlId in [101, 102, 103, 104]: # Slider clicks (update immediately)
            # This handles slider value changes. The main 'Apply' button (3203) will commit.
            # No need to set new_color_hex_str for direct setting here.
            return
        
        elif controlId == 3200: # Cancel button
            self.close()
            return
            
        elif controlId == 3201: # Reset button
            if self.active_panel_setting:
                is_jsonrpc_setting = self.active_panel_setting.startswith("subtitles.")
                
                if is_jsonrpc_setting:
                    try:
                        # For JSON-RPC settings, attempt to reset to default.
                        # This might require knowing the default, or setting a common default (e.g., black)
                        # or using a ResetSettingValue if available (not directly in the provided snippets).
                        # For now, setting to a common default like FF000000 (black) as per your settings.xml
                        default_color_for_jsonrpc = "FF000000" # As seen in your settings.xml defaults
                        json_string = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.SetSettingValue', 'params': {'setting': self.active_panel_setting, 'value': default_color_for_jsonrpc}}
                        json_call = json.dumps(json_string)
                        result = xbmc.executeJSONRPC(json_call)
                        xbmc.log(f"[MyColorDialog] JSONRPC Reset for {self.active_panel_setting} to {default_color_for_jsonrpc} result: {result}", xbmc.LOGINFO)
                        new_color_hex_str = default_color_for_jsonrpc
                    except Exception as e:
                        xbmc.log(f"[MyColorDialog] Error resetting JSON-RPC setting {self.active_panel_setting}: {e}", xbmc.LOGERROR)
                else:
                    # For Skin.String settings, use the Reset.Color property if available
                    reset_prop = xbmc.getInfoLabel("Window(Home).Property(Reset.Color)")
                    if reset_prop and reset_prop == self.active_panel_setting:
                        xbmc.executebuiltin(f"Skin.Reset({self.active_panel_setting})")
                        xbmc.log(f"[MyColorDialog] Skin.Reset for {self.active_panel_setting}", xbmc.LOGINFO)
                        # After reset, fetch the new default to update the dialog
                        new_color_hex_str = xbmc.getInfoLabel(f"Skin.String({self.active_panel_setting})")
                        if new_color_hex_str:
                            new_color_hex_str = new_color_hex_str.lstrip("#").upper()
                        else:
                            new_color_hex_str = "FFFFFFFF" # Default to opaque white if reset gives nothing
                    else:
                        xbmc.log("[MyColorDialog] Reset.Color property not set or does not match active setting.", xbmc.LOGWARNING)
            else:
                xbmc.log("[MyColorDialog] No active panel setting to reset.", xbmc.LOGWARNING)
            
            # Update the dialog's preview and sliders immediately after reset
            if new_color_hex_str:
                self.setProperty("SelectedColorNumOnly", new_color_hex_str)
                self.setProperty("ColorSelectedPicker", new_color_hex_str)
                # Recalculate slider values based on the new hex string
                self._slider_a_val = int(xbmc.getInfoLabel("$VAR[Def_Hex_To_Percent_A]"))
                self._slider_r_val = int(xbmc.getInfoLabel("$VAR[Def_Hex_To_Percent_R]"))
                self._slider_g_val = int(xbmc.getInfoLabel("$VAR[Def_Hex_To_Percent_G]"))
                self._slider_b_val = int(xbmc.getInfoLabel("$VAR[Def_Hex_To_Percent_B]"))
                self.getControl(101).setPercent(self._slider_a_val)
                self.getControl(102).setPercent(self._slider_r_val)
                self.getControl(103).setPercent(self._slider_g_val)
                self.getControl(104).setPercent(self._slider_b_val)
            return


        if new_color_hex_str:
            # Ensure it's 8 characters (AARRGGBB), pad with FF if only 6 (RGB)
            if len(new_color_hex_str) == 6:
                new_color_hex_str = "FF" + new_color_hex_str
            elif len(new_color_hex_str) != 8:
                 xbmc.log(f"[MyColorDialog] Warning: New color hex string has unexpected length: {new_color_hex_str}. Defaulting to FFFFFFFF.", xbmc.LOGWARNING)
                 new_color_hex_str = "FFFFFFFF" # Fallback

            self.setProperty("SelectedColorNumOnly", new_color_hex_str)
            self.setProperty("ColorSelectedPicker", new_color_hex_str) # Still display hex string

            if self.active_panel_setting:
                is_jsonrpc_setting = self.active_panel_setting.startswith("subtitles.") # Re-evaluate flag

                if is_jsonrpc_setting:
                    try:
                        # Use JSON-RPC to set the global setting value as a string
                        json_string = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.SetSettingValue', 'params': {'setting': self.active_panel_setting, 'value': new_color_hex_str}}
                        json_call = json.dumps(json_string)
                        result = xbmc.executeJSONRPC(json_call)
                        xbmc.log(f"[MyColorDialog] JSONRPC SetSettingValue for {self.active_panel_setting} to {new_color_hex_str} result: {result}", xbmc.LOGINFO)
                    except Exception as e:
                        xbmc.log(f"[MyColorDialog] Error setting setting via JSON-RPC for {self.active_panel_setting}: {e}", xbmc.LOGERROR)
                else:
                    # Use Skin.SetString for skin-specific settings
                    xbmc.executebuiltin(f"Skin.SetString({self.active_panel_setting},{new_color_hex_str})")
                    xbmc.log(f"[MyColorDialog] Skin.SetString for {self.active_panel_setting} to {new_color_hex_str}", xbmc.LOGINFO)
            
            # Close dialog after apply
            self.close()

    def onAction(self, action):
        """
        Handles actions like closing the dialog with Escape/Back.
        """
        if action == xbmcgui.ACTION_PARENT_DIR or action == xbmcgui.ACTION_PREVIOUS_MENU:
            self.close()

    def onClose(self):
        """
        Called when the dialog is closed. Stop the monitor thread.
        """
        self._monitor_stop = True
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.5) # Give it a little time to finish
        xbmc.log("[MyColorDialog] Dialog closed. Monitor thread stopped.", xbmc.LOGINFO)
        super().onClose()

    def populate_colors(self):
        """
        Populates the color swatches from the specified XML file.
        """
        panel = self.getControl(6)
        panel.reset()
        xbmc.log("[MyColorDialog] Populating colors from: {}".format(self.color_file), xbmc.LOGINFO)
        try:
            tree = ET.parse(self.color_file)
            root = tree.getroot()
            for color_element in root.findall('color'):
                color_value = color_element.text.strip().lstrip('#').upper()
                if len(color_value) == 6: # If only RGB, prepend FF for opaque
                    color_value = "FF" + color_value
                elif len(color_value) != 8:
                    xbmc.log(f"[MyColorDialog] Skipping invalid color format: {color_value}", xbmc.LOGWARNING)
                    continue

                list_item = xbmcgui.ListItem()
                list_item.setProperty("SelectedColorNumOnly", color_value)
                list_item.setProperty("HexColor", color_value)
                list_item.setProperty("ColorSample", f"0x{color_value}") # For skin display (e.g., color overlays)
                panel.addItem(list_item)
            xbmc.log(f"[MyColorDialog] Loaded {len(panel.getItems())} colors.", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[MyColorDialog] Error loading colors from {self.color_file}: {e}", xbmc.LOGERROR)

    def monitor_mycolorfile(self):
        """
        Monitors changes to 'mycolorfile' and the active panel setting.
        """
        while not self._monitor_stop:
            time.sleep(1.2)
            
            # Check for palette file changes (existing logic)
            current_path = xbmc.getInfoLabel("Skin.String(mycolorfile)")
            if current_path:
                current_path = xbmcvfs.translatePath(current_path)
            else:
                current_path = xbmcvfs.translatePath("special://skin/extras/colors/madnox-(24-colors).xml") # Fallback to default if Skin.String is empty
                
            if current_path != self._last_palette_path:
                xbmc.log("[MyColorDialog] mycolorfile changed. Reloading from: {}".format(current_path), xbmc.LOGINFO)
                self._last_palette_path = current_path
                self.color_file = current_path
                self.populate_colors()

            # Also check the active panel setting value
            if self.active_panel_setting:
                is_jsonrpc_setting = self.active_panel_setting.startswith("subtitles.")
                current_setting_hex_str = "Default"

                if is_jsonrpc_setting:
                    try:
                        json_string = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.GetSettingValue', 'params': {'setting': self.active_panel_setting}}
                        json_call = json.dumps(json_string)
                        result = xbmc.executeJSONRPC(json_call)
                        parsed_result = json.loads(result)
                        retrieved_value = parsed_result.get('result', {}).get('value')
                        
                        if retrieved_value is not None:
                            current_setting_hex_str = str(retrieved_value).lstrip("#").upper()
                            # Ensure AARRGGBB format
                            if len(current_setting_hex_str) == 6:
                                current_setting_hex_str = "FF" + current_setting_hex_str
                            elif len(current_setting_hex_str) != 8:
                                current_setting_hex_str = "FFFFFFFF" # Fallback
                        else:
                             current_setting_hex_str = "FFFFFFFF" # Default if no value retrieved
                            

                    except Exception as e:
                        xbmc.log(f"[MyColorDialog] Error in monitor thread getting setting via JSON-RPC for {self.active_panel_setting}: {e}", xbmc.LOGERROR)
                else:
                    # Skin.String monitoring
                    current_setting_hex_str = xbmc.getInfoLabel(f"Skin.String({self.active_panel_setting})")
                    if current_setting_hex_str:
                        current_setting_hex_str = current_setting_hex_str.lstrip("#").upper()
                        # Ensure AARRGGBB format
                        if len(current_setting_hex_str) == 6:
                            current_setting_hex_str = "FF" + current_setting_hex_str
                        elif len(current_setting_hex_str) != 8:
                            current_setting_hex_str = "FFFFFFFF" # Fallback
                    else:
                        current_setting_hex_str = "FFFFFFFF" # Default if Skin.String is empty/None

                if self.getProperty("ColorSelectedPicker") != current_setting_hex_str:
                    self.setProperty("ColorSelectedPicker", current_setting_hex_str)
                    xbmc.log("[MyColorDialog] Monitor updated applied color preview to {}".format(current_setting_hex_str), xbmc.LOGINFO)

def show_color_dialog():
    xml_file = "Custom_1104_DialogOverlayColorPicker.xml"
    addon_path = xbmcvfs.translatePath("special://home/addons/skin.madnox/16x9/")
    color_file_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if color_file_arg:
        color_file_arg = xbmcvfs.translatePath(color_file_arg)
    dialog = MyColorDialog(xml_file, addon_path, color_file_arg)
    dialog.doModal()
    del dialog

if __name__ == '__main__':
    show_color_dialog()