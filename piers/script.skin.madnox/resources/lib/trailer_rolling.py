import xbmc
import xbmcgui
import time

# --- CONFIGURATION ---
SUPPORTED_VIEWS = {
    50:  "View50VideoPreviewWindow",   51:  "View51VideoPreviewWindow",   52:  "View52VideoPreviewWindow",
    53:  "View53VideoPreviewWindow",   54:  "View54VideoPreviewWindow",   55:  "View55VideoPreviewWindow",
    56:  "View56VideoPreviewWindow",   57:  "View57VideoPreviewWindow",   58:  "View58VideoPreviewWindow",
    59:  "View59VideoPreviewWindow",   60:  "View60VideoPreviewWindow",   61:  "View61VideoPreviewWindow",
    62:  "View62VideoPreviewWindow",   63:  "View63VideoPreviewWindow",   500: "View500VideoPreviewWindow",
    502: "View502VideoPreviewWindow",  503: "View503VideoPreviewWindow",  504: "View504VideoPreviewWindow",
    505: "View505VideoPreviewWindow",  506: "View506VideoPreviewWindow",  507: "View507VideoPreviewWindow",
    508: "View508VideoPreviewWindow",  510: "View510VideoPreviewWindow",  511: "View511VideoPreviewWindow",
    512: "View512VideoPreviewWindow",  520: "View520VideoPreviewWindow",  522: "View522VideoPreviewWindow",
    523: "View523VideoPreviewWindow",  530: "View530VideoPreviewWindow",  532: "View532VideoPreviewWindow",
    533: "View533VideoPreviewWindow",  540: "View540VideoPreviewWindow",  542: "View542VideoPreviewWindow",
    543: "View543VideoPreviewWindow",
}

# --- CONSTANTS ---
PROP_RUNNING = "Madnox.TrailerRolling.Running"
PROP_IS_TRAILER = "IsPlayingTrailer"
SKIN_SETTING_DEBUG = "trailer_rolling_debug"

# CORRECTED WINDOW IDS
VIDEOS_WINDOW_ID = 10025        # MyVideoNav.xml
VIDEO_INFO_DIALOG_ID = 12003    # DialogVideoInfo.xml (movieinformation)

# --- HELPER FUNCTIONS ---
def log_debug(msg):
    """Logs messages only if the skin debug setting is enabled."""
    if xbmc.getCondVisibility(f'Skin.HasSetting({SKIN_SETTING_DEBUG})'):
        xbmc.log(f"[TrailerRolling DEBUG] {msg}", xbmc.LOGINFO)

def log_error(msg):
    """Always logs errors."""
    xbmc.log(f"[TrailerRolling ERROR] {msg}", xbmc.LOGERROR)

class TrailerMonitor(xbmc.Monitor):
    def run(self):
        last_path = ""
        try:
            # Main loop: Continue as long as the main videos window is visible
            while not self.abortRequested() and xbmc.getCondVisibility(f'Window.IsVisible({VIDEOS_WINDOW_ID})'):
                
                current_window_id = xbmcgui.getCurrentWindowId()
                
                # CRITICAL CHECK: Is the Info Dialog (12003) open?
                is_info_active = xbmc.getCondVisibility(f'Window.IsActive({VIDEO_INFO_DIALOG_ID})')
                is_info_visible = xbmc.getCondVisibility(f'Window.IsVisible({VIDEO_INFO_DIALOG_ID})')

                if is_info_active or is_info_visible:
                    # If Info Dialog is open, kill the trailer immediately.
                    if xbmcgui.Window(10000).getProperty(PROP_IS_TRAILER):
                        log_debug(f"Info Dialog ({VIDEO_INFO_DIALOG_ID}) detected (Active: {is_info_active}, Visible: {is_info_visible}). Stopping trailer.")
                        self.cleanup()
                        last_path = "" # Force re-eval when we return
                    
                    xbmc.sleep(500) # Wait loop while Info Dialog is up
                    continue

                # If we aren't in the Info Dialog, but we also aren't in MyVideoNav (e.g. Settings), pause.
                if current_window_id != VIDEOS_WINDOW_ID:
                    # Only log this transition once to avoid spamming the log while in Settings
                    if xbmcgui.Window(10000).getProperty(PROP_IS_TRAILER):
                        log_debug(f"Not in MyVideoNav. Current ID: {current_window_id}. Cleaning up.")
                        self.cleanup()
                        last_path = ""
                    xbmc.sleep(500)
                    continue

                active_view = self.get_active_view()

                # If no supported view is enabled/visible
                if not active_view:
                    if xbmcgui.Window(10000).getProperty(PROP_IS_TRAILER):
                        log_debug("No supported view found/visible. Cleaning up.")
                        self.cleanup()
                        last_path = ""
                    xbmc.sleep(500) 
                    continue

                # If the active view container does not have focus
                if not xbmc.getCondVisibility(f'Container({active_view}).HasFocus'):
                    if xbmcgui.Window(10000).getProperty(PROP_IS_TRAILER):
                        log_debug(f"Active view {active_view} lost focus. Cleaning up.")
                        self.cleanup()
                        last_path = ""
                    xbmc.sleep(200)
                    continue

                # Check for list item movement
                current_path = xbmc.getInfoLabel('ListItem.Path')
                
                if current_path != last_path:
                    log_debug(f"Path changed from '{last_path}' to '{current_path}'. Starting stabilization.")
                    last_path = current_path
                    self.cleanup() 
                    
                    # Stabilization Loop
                    stable = True
                    for i in range(16): 
                        # RE-CHECK: If Info Dialog pops up during wait, abort immediately
                        if self.abortRequested() or \
                           xbmc.getCondVisibility(f'Window.IsActive({VIDEO_INFO_DIALOG_ID})') or \
                           xbmc.getCondVisibility(f'Window.IsVisible({VIDEO_INFO_DIALOG_ID})') or \
                           xbmcgui.getCurrentWindowId() != VIDEOS_WINDOW_ID or \
                           not self.get_active_view() or \
                           not xbmc.getCondVisibility(f'Control.HasFocus({active_view})') or \
                           xbmc.getInfoLabel('ListItem.Path') != current_path:
                            log_debug(f"Stability check failed at iteration {i}. Aborting.")
                            stable = False
                            break
                        xbmc.sleep(100)
                    
                    if stable:
                        trailer_url = xbmc.getInfoLabel('ListItem.Trailer')
                        log_debug(f"UI Stable. Trailer detected: {trailer_url}")
                        if trailer_url:
                            trailer_url = trailer_url.strip('"')
                            log_debug(f"Attempting to play: {trailer_url}")
                            # Store the exact URL so we only kill this trailer, not a full movie
                            xbmcgui.Window(10000).setProperty(PROP_IS_TRAILER, trailer_url)
                            xbmc.executebuiltin(f'PlayMedia("{trailer_url}",1,noresume)')
                            xbmc.sleep(1000)
                    else:
                        last_path = "" # Retry next loop

                xbmc.sleep(100)
                
        except Exception as e:
            log_error(f"Run Loop Error: {str(e)}")
        finally:
            self.cleanup()
            xbmcgui.Window(10000).clearProperty(PROP_RUNNING)
            log_debug("Script finished/exited.")

    def get_active_view(self):
        if xbmcgui.getCurrentWindowId() != VIDEOS_WINDOW_ID:
            return None
            
        for view_id, setting_name in SUPPORTED_VIEWS.items():
            if xbmc.getCondVisibility(f'Control.IsVisible({view_id})') and \
            xbmc.getCondVisibility(f'Skin.HasSetting({setting_name})') and \
            xbmc.getCondVisibility(f'Container({view_id}).HasFocus'):  # <-- FIXED
                return view_id
        return None

    def cleanup(self):
        trailer_url = xbmcgui.Window(10000).getProperty(PROP_IS_TRAILER)
        if trailer_url:
            log_debug("Cleanup triggered: Stopping player and clearing property.")
            try:
                # Prevent stopping a movie if the user clicked play!
                if xbmc.Player().isPlaying():
                    playing_file = xbmc.Player().getPlayingFile()
                    if playing_file == trailer_url:
                        xbmc.Player().stop()
            except Exception as e:
                log_debug(f"Cleanup error checking player: {e}")
                
            xbmcgui.Window(10000).clearProperty(PROP_IS_TRAILER)

# --- MODULE ENTRY POINT ---
def run(params=None):
    # Determine which action to perform
    action = params.get('action') if params else 'trailer_rolling'

    if action == 'trailer_rolling':
        # --- SINGLETON CHECK ---
        if xbmcgui.Window(10000).getProperty(PROP_RUNNING) == "true":
            log_debug("Script already running (singleton check), exiting duplicate.")
            return

        xbmcgui.Window(10000).setProperty(PROP_RUNNING, "true")
        log_debug("Script started via Router (entering main loop).")

        # Start the monitor
        monitor = TrailerMonitor()
        monitor.run()

    elif action == 'trailer_cleanup':
        # This is our new, targeted cleanup action
        log_debug("Cleanup action called directly from XML.")
        monitor = TrailerMonitor()
        monitor.cleanup()