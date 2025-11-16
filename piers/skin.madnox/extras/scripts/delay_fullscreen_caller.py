import xbmc
import time

# Adjust this delay as needed. 2-3 seconds is usually a good starting point.
DELAY_SECONDS = 1.0 

time.sleep(DELAY_SECONDS)
xbmc.executebuiltin("RunScript(special://home/addons/skin.madnox/extras/scripts/send_fullscreen.py)")