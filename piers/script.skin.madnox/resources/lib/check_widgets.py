import os
import shutil
import xbmc
import xbmcgui
import xbmcvfs

LOG_PREFIX = "check_widgets"

_USERDATA_JSON = "special://profile/addon_data/script.skinshortcuts/skin.madnox.userdata.json"
_DEFAULT_JSON  = "special://home/addons/script.skin.madnox/resources/lib/skin.madnox.userdata.json"
_V2_PROPERTIES = "special://profile/addon_data/script.skinshortcuts/skin.madnox.properties"


def run(params=None):
    json_path  = xbmcvfs.translatePath(_USERDATA_JSON)
    props_path = xbmcvfs.translatePath(_V2_PROPERTIES)
    src_path   = xbmcvfs.translatePath(_DEFAULT_JSON)

    # Already has v3 userdata — nothing to do
    if os.path.isfile(json_path):
        xbmc.executebuiltin('Skin.SetBool(Madnox_Widgets_Initialized)')
        xbmc.log("{}: userdata.json already present — skipping.".format(LOG_PREFIX), xbmc.LOGINFO)
        return

    has_v2 = os.path.isfile(props_path)

    if has_v2:
        message = (
            "Your previous Madnox widget setup was detected but needs updating "
            "for the new skin shortcuts format.[CR][CR]"
            "Select Yes to apply recommended defaults now — your previous data "
            "remains on disk and can be fully restored using the Madnox Migrator "
            "tool on Windows.[CR][CR]"
            "Select No to skip and configure manually later."
        )
    else:
        message = (
            "No widget configuration was found.[CR][CR]"
            "Select Yes to set up your home screen with recommended defaults "
            "(Movies and TV Shows: Recently Added).[CR][CR]"
            "Select No to skip and configure manually via Skin Shortcuts."
        )

    dialog = xbmcgui.Dialog()
    confirmed = dialog.yesno("Madnox — Widget Setup", message)

    # Set the bool regardless so this never auto-fires again.
    # The button in Advanced Settings > Restore Default Widgets serves as
    # the manual re-trigger path going forward.
    xbmc.executebuiltin('Skin.SetBool(Madnox_Widgets_Initialized)')

    if not confirmed:
        xbmc.log("{}: User declined widget setup.".format(LOG_PREFIX), xbmc.LOGINFO)
        return

    if not os.path.isfile(src_path):
        xbmc.log("{}: Default widget file not found at '{}'.".format(LOG_PREFIX, src_path), xbmc.LOGERROR)
        dialog.ok("Madnox — Widget Setup", "Default file not found. Please reinstall the skin.")
        return

    dst_dir = os.path.dirname(json_path)
    if not os.path.isdir(dst_dir):
        try:
            os.makedirs(dst_dir)
        except (IOError, OSError) as e:
            xbmc.log("{}: Could not create destination directory: {}".format(LOG_PREFIX, e), xbmc.LOGERROR)
            return

    try:
        shutil.copy2(src_path, json_path)
        xbmc.log("{}: Default widgets deployed to '{}'.".format(LOG_PREFIX, json_path), xbmc.LOGINFO)
    except (IOError, OSError) as e:
        xbmc.log("{}: Could not copy default file: {}".format(LOG_PREFIX, e), xbmc.LOGERROR)
        return

    xbmc.executebuiltin(
        'RunScript(script.skinshortcuts,type=buildxml&mainmenuID=9000&group=mainmenu|shortcuts)'
    )
    xbmc.sleep(2000)

    if has_v2:
        xbmc.executebuiltin(
            'Notification("Madnox", "Defaults applied. Use the Madnox Migrator to restore your previous setup.", 9000, "info")'
        )
    else:
        xbmc.executebuiltin(
            'Notification("Madnox", "Home screen defaults applied", 7000, "info")'
        )
