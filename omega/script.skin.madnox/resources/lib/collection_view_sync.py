# collection_view_sync.py
# Part of script.skin.madnox — DEBUG BUILD

import xbmc
import xbmcgui
import threading

GLOBAL_SET_VIEW_KEY = 'GlobalSetView'
LAST_APPLIED_KEY    = 'CollectionViewSync.LastApplied'
LOCK_KEY            = 'CollectionViewSync.Applying'
SET_PATH_FRAGMENT   = 'videodb://movies/sets/'
TAG                 = '[collection_view_sync]'
HOME_WINDOW_ID      = 10000


def _home():
    return xbmcgui.Window(HOME_WINDOW_ID)


def _get_folder_path():
    return xbmc.getInfoLabel('Container.FolderPath')


def _get_global_view():
    val = _home().getProperty(GLOBAL_SET_VIEW_KEY)
    if not val:
        val = xbmc.getInfoLabel(f'Skin.String({GLOBAL_SET_VIEW_KEY})')
        if val:
            _home().setProperty(GLOBAL_SET_VIEW_KEY, val)
            xbmc.log(f'{TAG} _get_global_view() loaded from Skin.String = "{val}"', xbmc.LOGINFO)
    return val


def _do_set_view(global_view, folder_path, caller):
    """Fire SetViewMode and record LAST_APPLIED."""
    xbmc.log(f'{TAG} {caller} — FIRING Container.SetViewMode({global_view})', xbmc.LOGINFO)
    xbmc.executebuiltin(f'Container.SetViewMode({global_view})')
    _home().setProperty(LAST_APPLIED_KEY, f'{folder_path}:{global_view}')
    xbmc.log(f'{TAG} {caller} — set LAST_APPLIED="{folder_path}:{global_view}"', xbmc.LOGINFO)


def _bg_monitor():
    """
    Background thread that monitors folder path changes passively.
    """
    home = _home()
    if home.getProperty('CollectionViewSync.MonitorRunning') == 'true':
        return
        
    home.setProperty('CollectionViewSync.MonitorRunning', 'true')
    xbmc.log(f'{TAG} Background monitor STARTED', xbmc.LOGINFO)

    try:
        xbmc_monitor = xbmc.Monitor()
        last_path = _get_folder_path()
        
        while not xbmc_monitor.abortRequested():
            # TWEAK 1: Check every 100ms instead of 250ms for snappier detection.
            # This consumes virtually 0 CPU as the thread yields entirely while waiting.
            if xbmc_monitor.waitForAbort(0.1):
                break
            
            if not xbmc.getCondVisibility('Window.IsVisible(MyVideoNav.xml)'):
                xbmc.log(f'{TAG} Left MyVideoNav, stopping monitor', xbmc.LOGINFO)
                break
            
            current_path = _get_folder_path()
            if current_path != last_path:
                last_path = current_path
                
                if SET_PATH_FRAGMENT in current_path:
                    global_view = _get_global_view()
                    if global_view:
                        last_applied = home.getProperty(LAST_APPLIED_KEY)
                        expected = f'{current_path}:{global_view}'
                        
                        if last_applied != expected:
                            # TWEAK 2: Poll Container.IsUpdating faster (every 50ms)
                            # Loop 80 times to maintain a 4-second maximum timeout
                            for _ in range(80):
                                if xbmc_monitor.abortRequested() or not xbmc.getCondVisibility('Window.IsVisible(MyVideoNav.xml)'):
                                    break
                                if not xbmc.getCondVisibility('Container.IsUpdating'):
                                    break
                                xbmc.sleep(50)
                                
                            # TWEAK 3: Settle delay reduced from 400ms to 150ms.
                            # If the view fails to set occasionally on a Firestick, 
                            # bump this to 200 or 250.
                            xbmc.sleep(150)
                            
                            if _get_folder_path() == current_path:
                                _do_set_view(global_view, current_path, 'bg_monitor')

    finally:
        home.clearProperty('CollectionViewSync.MonitorRunning')
        xbmc.log(f'{TAG} Background monitor STOPPED', xbmc.LOGINFO)


def start_monitor():
    """Spins up the daemon thread if it isn't already running."""
    if _home().getProperty('CollectionViewSync.MonitorRunning') != 'true':
        t = threading.Thread(target=_bg_monitor)
        t.daemon = True
        t.start()


def save(params):
    xbmc.log(f'{TAG} save() ENTERED params={params}', xbmc.LOGINFO)
    folder_path = _get_folder_path()
    xbmc.log(f'{TAG} save() FolderPath="{folder_path}"', xbmc.LOGINFO)

    if SET_PATH_FRAGMENT not in folder_path:
        xbmc.log(f'{TAG} save() — not in collection, skipping', xbmc.LOGINFO)
        return

    view_id = params.get('viewid', '').strip()
    if not view_id:
        xbmc.log(f'{TAG} save() — no viewid param', xbmc.LOGWARNING)
        return

    home = _home()
    home.setProperty(GLOBAL_SET_VIEW_KEY, view_id)
    # Clear LAST_APPLIED so next focus/onload will re-enforce new view
    home.clearProperty(LAST_APPLIED_KEY)
    xbmc.executebuiltin(f'Skin.SetString({GLOBAL_SET_VIEW_KEY},{view_id})')
    xbmc.log(f'{TAG} save() saved view_id="{view_id}" readback="{home.getProperty(GLOBAL_SET_VIEW_KEY)}"', xbmc.LOGINFO)


def apply_view():
    """
    Called from <onload> in MyVideoNav.xml.
    """
    xbmc.log(f'{TAG} apply_view() ENTERED', xbmc.LOGINFO)

    start_monitor()

    home = _home()
    if home.getProperty(LOCK_KEY) == 'true':
        return

    global_view = _get_global_view()
    if not global_view:
        return

    folder_path = _get_folder_path()
    home.clearProperty(LAST_APPLIED_KEY)

    if SET_PATH_FRAGMENT not in folder_path:
        return

    home.setProperty(LOCK_KEY, 'true')
    try:
        # TWEAK 4: Reduced initial load delay from 600ms to 250ms
        xbmc.sleep(250)
        folder_path = _get_folder_path()
        if SET_PATH_FRAGMENT in folder_path:
            _do_set_view(global_view, folder_path, 'apply_view()')
    finally:
        home.clearProperty(LOCK_KEY)


def on_list_focus():
    """
    Called from <onfocus> on list controls 55 and 58.
    """
    xbmc.log(f'{TAG} on_list_focus() ENTERED', xbmc.LOGINFO)
    
    start_monitor()

    folder_path = _get_folder_path()
    if SET_PATH_FRAGMENT not in folder_path:
        return

    global_view = _get_global_view()
    if not global_view:
        return

    home = _home()
    last_applied = home.getProperty(LAST_APPLIED_KEY)
    expected = f'{folder_path}:{global_view}'

    if last_applied == expected:
        return

    _do_set_view(global_view, folder_path, 'on_list_focus()')


def run(params):
    mode = params.get('mode', '').strip()
    xbmc.log(f'{TAG} run() mode="{mode}"', xbmc.LOGINFO)
    if mode == 'save':
        save(params)
    elif mode == 'apply':
        apply_view()
    elif mode == 'focus':
        on_list_focus()
    else:
        xbmc.log(f'{TAG} Unknown mode "{mode}"', xbmc.LOGWARNING)