import sys
import xbmc
import xbmcgui
import xbmcvfs
import xml.etree.ElementTree as ET
import threading
import time

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
        self.active_panel_setting = ""  # to store the active setting name (e.g., "PanelStyle.color")

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

        # 2) Grab the active panel parameter and current color from Home window.
        #    For example, ActiveControlPanelName might be "PanelStyle.color"
        param_name = xbmc.getInfoLabel("Window(Home).Property(ActiveControlPanelName)")
        self.active_panel_setting = param_name
        current_color = xbmc.getInfoLabel("Window(Home).Property(ActiveControlPanelNameValue)")

        # 3) If current_color is non-empty, update our properties (convert to uppercase)
        if current_color:
            color_stripped = current_color.lstrip("#")
            if not color_stripped:
                color_stripped = "FFFFFFFF"
            else:
                color_stripped = color_stripped.upper()
            self.setProperty("SelectedColorNumOnly", color_stripped)
            self.setProperty("ColorSelectedPicker", color_stripped)
            xbmc.log(f"[MyColorDialog] Pre-populating color from {param_name} = {color_stripped}", xbmc.LOGINFO)
        else:
            # If current_color is empty, set preview to "Default"
            self.setProperty("ColorSelectedPicker", "Default")
            xbmc.log("[MyColorDialog] No applied color; setting preview to 'Default'", xbmc.LOGINFO)

        # 4) Sleep ~300ms so Kodi finishes internal slider setup
        xbmc.sleep(300)

        # 5) Forcibly set the sliders
        try:
            self.getControl(3015).setPercent(100)
            self.getControl(3200).setPercent(50)
            self.getControl(3201).setPercent(50)
            self.getControl(3202).setPercent(50)
            xbmc.log("[MyColorDialog] Successfully set sliders", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[MyColorDialog] Failed to set slider percent: {e}", xbmc.LOGERROR)

        # 6) Populate the panel with colors
        self.populate_colors()

        # 7) Start a background thread to monitor palette changes and active setting updates
        self._monitor_stop = False
        self._monitor_thread = threading.Thread(target=self.monitor_mycolorfile)
        self._monitor_thread.start()

    def populate_colors(self):
        """
        Reads self.color_file and adds each color to <panel id="6">.
        """
        try:
            panel = self.getControl(6)
            panel.reset()

            tree = ET.parse(self.color_file)
            root = tree.getroot()

            count = 0
            for color_el in root.findall('color'):
                color_name = color_el.get("name") or "Unknown"
                color_hex = (color_el.text or "#FFFFFF").strip()
                color_hex_2 = (color_el.text or "#FFFFFF").strip()

                list_item = xbmcgui.ListItem(label=color_name)
                list_item.setLabel2(color_hex)
                list_item.setProperty("SelectedColor", color_hex)
                list_item.setProperty("SelectedColorNumOnly", color_hex_2)
                panel.addItem(list_item)
                count += 1

            xbmc.log("[MyColorDialog] Loaded {} colors from '{}'".format(count, self.color_file), xbmc.LOGINFO)
        except Exception as e:
            xbmc.log("[MyColorDialog] Error populating panel from '{}': {}".format(self.color_file, e), xbmc.LOGERROR)

    def onClick(self, controlId):
        if controlId == 6:
            # The user clicked on a color in the panel.
            panel = self.getControl(6)
            item = panel.getSelectedItem()
            if item:
                # Get full hex color (with '#' if needed)
                color_hex = item.getProperty("SelectedColor") or ""
                if not color_hex:
                    color_hex = "#FFFFFF"
                elif not color_hex.startswith("#"):
                    color_hex = "#" + color_hex
                self.setProperty("SelectedColor", color_hex)

                # Get numeric-only version (strip '#' if present), then convert to uppercase.
                color_hex_num = item.getProperty("SelectedColorNumOnly") or ""
                if not color_hex_num:
                    color_hex_num = "FFFFFF"
                elif color_hex_num.startswith("#"):
                    color_hex_num = color_hex_num.lstrip("#")
                color_hex_num = color_hex_num.upper()
                self.setProperty("SelectedColorNumOnly", color_hex_num)
                # Update the preview label property.
                self.setProperty("ColorSelectedPicker", color_hex_num)

                # Immediately write the new color to the settings file.
                if self.active_panel_setting:
                    cmd = "Skin.SetString({},{})".format(self.active_panel_setting, color_hex_num)
                    xbmc.executebuiltin(cmd)
                    self.setProperty("ActiveControlPanelNameValue", color_hex_num)
                    xbmc.log("[MyColorDialog] Palette click updated {} to {}".format(self.active_panel_setting, color_hex_num), xbmc.LOGINFO)

        elif controlId == 3203:
            # The user pressed the "Apply" button.
            new_color = xbmc.getInfoLabel("$VAR[Def_Percent_To_Hex_Color]")
            if not new_color:
                new_color = "FFFFFFFF"
            new_color = new_color.lstrip("#")
            if not new_color:
                new_color = "FFFFFFFF"
            new_color = new_color.upper()
            self.setProperty("SelectedColorNumOnly", new_color)
            self.setProperty("ActiveControlPanelNameValue", new_color)
            self.setProperty("ColorSelectedPicker", new_color)
            xbmc.log("[MyColorDialog] Apply button sets color to {}".format(new_color), xbmc.LOGINFO)

        elif controlId == 3011:
            try:
                self.getControl(3015).setPercent(100)
                self.getControl(3200).setPercent(50)
                self.getControl(3201).setPercent(50)
                self.getControl(3202).setPercent(50)
                xbmc.log("[MyColorDialog] Reset sliders to 100,50,50,50", xbmc.LOGINFO)
            except Exception as e:
                xbmc.log("[MyColorDialog] Failed to reset sliders: {}".format(e), xbmc.LOGERROR)


    def onAction(self, action):
        if action in (9, 10):  # ACTION_BACK, ACTION_CLOSE_DIALOG
            self.close()
        else:
            super().onAction(action)

    def close(self):
        self._monitor_stop = True
        if self._monitor_thread:
            self._monitor_thread.join(2.0)
        super().close()

    def monitor_mycolorfile(self):
        """
        Polls Skin.String(mycolorfile) every 1.2s.
        Also checks the active panel setting's current value and updates the applied color preview.
        """
        while not self._monitor_stop:
            time.sleep(1.2)
            # Check for palette file changes.
            current_path = xbmc.getInfoLabel("Skin.String(mycolorfile)")
            if current_path:
                current_path = xbmcvfs.translatePath(current_path)
            else:
                current_path = xbmcvfs.translatePath("special://skin/extras/colors/madnox-(24-colors).xml")
            if current_path != self._last_palette_path:
                xbmc.log("[MyColorDialog] mycolorfile changed. Reloading from: {}".format(current_path), xbmc.LOGINFO)
                self._last_palette_path = current_path
                self.color_file = current_path
                self.populate_colors()

            # Also check the active panel setting value.
            if self.active_panel_setting:
                current_setting = xbmc.getInfoLabel("Skin.String({})".format(self.active_panel_setting))
                if current_setting:
                    current_setting = current_setting.lstrip("#").upper()
                else:
                    current_setting = ""
                if not current_setting:
                    current_setting = "Default"
                if self.getProperty("ColorSelectedPicker") != current_setting:
                    self.setProperty("ColorSelectedPicker", current_setting)
                    xbmc.log("[MyColorDialog] Monitor updated applied color preview to {}".format(current_setting), xbmc.LOGINFO)

def show_color_dialog():
    xml_file = "Custom_1104_DialogOverlayColorPicker.xml"
    addon_path = xbmcvfs.translatePath("special://home/addons/skin.madnox/16x9/")
    color_file_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if color_file_arg:
        color_file_arg = xbmcvfs.translatePath(color_file_arg)
    dialog = MyColorDialog(xml_file, addon_path, color_file=color_file_arg)
    dialog.doModal()
    del dialog

if __name__ == "__main__":
    show_color_dialog()
