import sys
import xbmc
import xbmcgui
import xbmcvfs
import xml.etree.ElementTree as ET
import threading
import time
from typing import cast

class MyColorDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, xmlFilename, scriptPath, color_file=None):
        super().__init__(xmlFilename, scriptPath)
        self.color_file = color_file
        self._monitor_stop = False
        self._monitor_thread = None
        self._last_palette_path = ""
        self.active_panel_setting = ""

    def onInit(self):
        super().onInit()
        if not self.color_file:
            from_skin = xbmc.getInfoLabel("Skin.String(mycolorfile)")
            if from_skin:
                self.color_file = xbmcvfs.translatePath(from_skin)
            else:
                self.color_file = xbmcvfs.translatePath("special://home/addons/script.skin.madnox/resources/extras/colors/madnox-(24-colors).xml")
        self._last_palette_path = self.color_file
        param_name = xbmc.getInfoLabel("Window(Home).Property(ActiveControlPanelName)")
        self.active_panel_setting = param_name
        current_color = xbmc.getInfoLabel("Window(Home).Property(ActiveControlPanelNameValue)")
        if current_color:
            color_stripped = current_color.lstrip("#").upper() or "FFFFFFFF"
            self.setProperty("SelectedColorNumOnly", color_stripped)
            self.setProperty("ColorSelectedPicker", color_stripped)
        else:
            self.setProperty("ColorSelectedPicker", "Default")
        xbmc.sleep(300)
        try:
            slider_3015 = cast(xbmcgui.ControlSlider, self.getControl(3015))
            slider_3200 = cast(xbmcgui.ControlSlider, self.getControl(3200))
            slider_3201 = cast(xbmcgui.ControlSlider, self.getControl(3201))
            slider_3202 = cast(xbmcgui.ControlSlider, self.getControl(3202))
            slider_3015.setPercent(100)
            slider_3200.setPercent(0)
            slider_3201.setPercent(0)
            slider_3202.setPercent(0)
        except Exception as e:
            xbmc.log(f"[MyColorDialog] Failed to set slider percent: {e}", xbmc.LOGERROR)
        self.populate_colors()
        self._monitor_stop = False
        self._monitor_thread = threading.Thread(target=self.monitor_mycolorfile)
        self._monitor_thread.start()

    def populate_colors(self):
        if not self.color_file: return
        try:
            panel = cast(xbmcgui.ControlList, self.getControl(6))
            panel.reset()
            tree = ET.parse(self.color_file)
            root = tree.getroot()
            for color_el in root.findall('color'):
                color_name = color_el.get("name", "Unknown")
                color_hex = (color_el.text or "#FFFFFF").strip()
                list_item = xbmcgui.ListItem(label=color_name)
                list_item.setLabel2(color_hex)
                list_item.setProperty("SelectedColor", color_hex)
                list_item.setProperty("SelectedColorNumOnly", color_hex)
                panel.addItem(list_item)
        except Exception as e:
            xbmc.log(f"[MyColorDialog] Error populating panel from '{self.color_file}': {e}", xbmc.LOGERROR)

    def onClick(self, controlId):
        if controlId == 6:
            panel = cast(xbmcgui.ControlList, self.getControl(6))
            item = panel.getSelectedItem()
            if item:
                color_hex = item.getProperty("SelectedColor") or "#FFFFFF"
                if not color_hex.startswith("#"): color_hex = "#" + color_hex
                self.setProperty("SelectedColor", color_hex)
                color_hex_num = (color_hex.lstrip("#") or "FFFFFF").upper()
                self.setProperty("SelectedColorNumOnly", color_hex_num)
                self.setProperty("ColorSelectedPicker", color_hex_num)
                if self.active_panel_setting:
                    xbmc.executebuiltin(f"Skin.SetString({self.active_panel_setting},{color_hex_num})")
                    self.setProperty("ActiveControlPanelNameValue", color_hex_num)
        elif controlId == 3203:
            new_color = (xbmc.getInfoLabel("$VAR[Def_Percent_To_Hex_Color]").lstrip("#") or "FFFFFFFF").upper()
            self.setProperty("SelectedColorNumOnly", new_color)
            self.setProperty("ActiveControlPanelNameValue", new_color)
            self.setProperty("ColorSelectedPicker", new_color)
        elif controlId == 3011:
            try:
                cast(xbmcgui.ControlSlider, self.getControl(3015)).setPercent(100)
                cast(xbmcgui.ControlSlider, self.getControl(3200)).setPercent(0)
                cast(xbmcgui.ControlSlider, self.getControl(3201)).setPercent(0)
                cast(xbmcgui.ControlSlider, self.getControl(3202)).setPercent(0)
            except Exception as e:
                xbmc.log(f"[MyColorDialog] Failed to reset sliders: {e}", xbmc.LOGERROR)

    def onAction(self, action):
        if action in (9, 10): self.close()
        else: super().onAction(action)

    def close(self):
        self._monitor_stop = True
        if self._monitor_thread: self._monitor_thread.join(2.0)
        super().close()

    def monitor_mycolorfile(self):
        while not self._monitor_stop:
            time.sleep(1.2)
            current_path = xbmc.getInfoLabel("Skin.String(mycolorfile)")
            current_path = xbmcvfs.translatePath(current_path) if current_path else xbmcvfs.translatePath("special://home/addons/script.skin.madnox/resources/extras/colors/madnox-(24-colors).xml")
            if current_path != self._last_palette_path:
                self._last_palette_path = current_path
                self.color_file = current_path
                self.populate_colors()
            if self.active_panel_setting:
                current_setting = (xbmc.getInfoLabel(f"Skin.String({self.active_panel_setting})").lstrip("#").upper() or "Default")
                if self.getProperty("ColorSelectedPicker") != current_setting:
                    self.setProperty("ColorSelectedPicker", current_setting)

# --- MODULE ENTRY POINT ---
def run(params):
    xml_file = "Custom_1104_DialogOverlayColorPicker.xml"
    addon_path = xbmcvfs.translatePath("special://home/addons/skin.madnox/16x9/")
    color_file_arg = params.get('colorfile')
    if color_file_arg:
        color_file_arg = xbmcvfs.translatePath(color_file_arg)
    dialog = MyColorDialog(xml_file, addon_path, color_file=color_file_arg)
    dialog.doModal()
    del dialog