import os
import shutil
import xbmc
import xbmcgui
import xbmcvfs

LOG_PREFIX = "deploy_default_widgets"

_SRC  = "special://home/addons/script.skin.madnox/resources/lib/skin.madnox.userdata.json"
_DST  = "special://profile/addon_data/script.skinshortcuts/skin.madnox.userdata.json"


def run(params=None):
    dialog = xbmcgui.Dialog()

    confirmed = dialog.yesno(
        "Restore Default Widgets",
        "This will replace your current widget configuration with the Madnox defaults.[CR][CR]"
        "Your existing file will be backed up first.[CR][CR]Continue?"
    )
    if not confirmed:
        return

    src_path = xbmcvfs.translatePath(_SRC)
    dst_path = xbmcvfs.translatePath(_DST)

    if not os.path.isfile(src_path):
        xbmc.log("{}: Default widget file not found at '{}'.".format(LOG_PREFIX, src_path), xbmc.LOGERROR)
        dialog.ok("Restore Default Widgets", "Default widget file not found. Please reinstall the skin.")
        return

    # Back up existing file if present
    if os.path.isfile(dst_path):
        bak_path = dst_path + ".bak"
        try:
            shutil.copy2(dst_path, bak_path)
            xbmc.log("{}: Backed up existing file to '{}'.".format(LOG_PREFIX, bak_path), xbmc.LOGINFO)
        except (IOError, OSError) as e:
            xbmc.log("{}: Could not back up existing file: {}".format(LOG_PREFIX, e), xbmc.LOGWARNING)

    # Ensure destination directory exists
    dst_dir = os.path.dirname(dst_path)
    if not os.path.isdir(dst_dir):
        try:
            os.makedirs(dst_dir)
        except (IOError, OSError) as e:
            xbmc.log("{}: Could not create destination directory: {}".format(LOG_PREFIX, e), xbmc.LOGERROR)
            dialog.ok("Restore Default Widgets", "Could not create target directory. Check Kodi logs.")
            return

    # Copy default file into place
    try:
        shutil.copy2(src_path, dst_path)
        xbmc.log("{}: Default widgets deployed to '{}'.".format(LOG_PREFIX, dst_path), xbmc.LOGINFO)
    except (IOError, OSError) as e:
        xbmc.log("{}: Could not copy default file: {}".format(LOG_PREFIX, e), xbmc.LOGERROR)
        dialog.ok("Restore Default Widgets", "Failed to write widget file. Check Kodi logs.")
        return

    # Trigger skinshortcuts rebuild
    xbmc.executebuiltin(
        'RunScript(script.skinshortcuts,type=buildxml&mainmenuID=9000&group=mainmenu|shortcuts)'
    )

    xbmc.sleep(2000)
    xbmc.executebuiltin('Notification("Madnox", "Default widgets restored", 7000, "info")')
