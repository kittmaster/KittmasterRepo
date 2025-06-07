import xbmcaddon
import xbmcgui
import xbmc
import sys

ADDON_ID = 'plugin.video.themoviedb.helper' # Your critical plugin ID
SKIN_ADDON_ID = 'skin.madnox'              # Your skin's addon ID

def get_skin_addon():
    """Returns the xbmcaddon.Addon object for the current skin."""
    try:
        return xbmcaddon.Addon(SKIN_ADDON_ID)
    except RuntimeError as e:
        xbmc.log(f"[tmdb_validation] ERROR: Skin addon '{SKIN_ADDON_ID}' not found or other runtime error: {e}", xbmc.LOGERROR)
        return None
    except Exception as e:
        xbmc.log(f"[tmdb_validation] ERROR: Unexpected error getting skin addon '{SKIN_ADDON_ID}': {e}", xbmc.LOGERROR)
        return None

def is_addon_enabled(addon_id):
    """Checks if a specific Kodi addon is currently installed and enabled."""
    try:
        # Use xbmc.getCondVisibility to check the addon's enabled status.
        # This is the reliable way to evaluate System.AddonIsEnabled() in Python.
        return xbmc.getCondVisibility(f"System.AddonIsEnabled({repr(addon_id)})")
    except Exception as e:
        xbmc.log(f"[tmdb_validation] Error checking addon '{addon_id}' status with getCondVisibility: {e}", xbmc.LOGERROR)
        return False

def show_critical_plugin_dialog():
    """
    Displays a modal dialog if the critical plugin is not enabled,
    and offers to retry (reload skin) or exit Kodi.
    """
    skin_addon = get_skin_addon()
    if not skin_addon:
        xbmc.log("[tmdb_validation] Cannot proceed without skin addon settings (skin addon not found). Exiting.", xbmc.LOGWARNING)
        return

    addon_name = "The MovieDB Helper"
    dialog = xbmcgui.Dialog()

    if not is_addon_enabled(ADDON_ID):
        xbmc.log(f"[tmdb_validation] Critical plugin '{ADDON_ID}' is NOT enabled. Showing dialog.", xbmc.LOGDEBUG)

        message = (
            f"The '{addon_name}' plugin is absolutely critical for this skin to function correctly. "
            "Please ensure it is installed and enabled via the Add-on browser.\n\n"
            "Would you like to retry (reload skin) or exit Kodi?"
        )

        if dialog.yesno("Critical Plugin Missing!", message, yeslabel="Retry", nolabel="Exit Kodi"):
            xbmc.log(f"[tmdb_validation] User chose 'Retry'. Reloading skin.", xbmc.LOGDEBUG)
            xbmc.executebuiltin("ReloadSkin()")
        else:
            xbmc.log(f"[tmdb_validation] User chose 'Exit Kodi'. Quitting Kodi.", xbmc.LOGDEBUG)
            xbmc.executebuiltin("Quit()")
            sys.exit(0)
    else:
        xbmc.log(f"[tmdb_validation] Critical plugin '{ADDON_ID}' is ENABLED. No further action needed.", xbmc.LOGDEBUG)

if __name__ == '__main__':
    show_critical_plugin_dialog()