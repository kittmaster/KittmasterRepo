import xbmc
import xbmcgui
import os

def run(params):
    try:
        home_window = xbmcgui.Window(10000)
        
        # 1. Try to get path from params
        file_path = params.get('path', '')

        # 2. FALLBACK: If path is empty, try to get it from the skin setting directly
        if not file_path:
            file_path = xbmc.getInfoLabel('Skin.String(IntroVideoSelectStartupValue)')

        if file_path == 'special://home/addons/script.skin.madnox/resources/extras/intro-omega.mp4':
            home_window.setProperty('IntroVideo.Label', 'Intro-omega.mp4 - Skin built-in')
            
        elif file_path and file_path.lower() != 'none':
            filename = os.path.basename(file_path)
            home_window.setProperty('IntroVideo.Label', '%s - Custom' % filename)
            
        else:
            home_window.clearProperty('IntroVideo.Label')

    except Exception as e:
        xbmc.log("Madnox Skin Script Error (set_intro_label.py): %s" % str(e), level=xbmc.LOGERROR)
        try:
            xbmcgui.Window(10000).clearProperty('IntroVideo.Label')
        except Exception:
            pass