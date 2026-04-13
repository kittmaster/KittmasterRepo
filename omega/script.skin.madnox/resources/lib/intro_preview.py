import xbmc
import xbmcgui
import xbmcvfs

# --- CONSTANTS ---
PROP_RUNNING = "Madnox.IntroPreview.Running"
PROP_SHOW_PLAYER = "ShowIntroPreview"
CONTROL_ID = 541

class IntroPlayer:
    def __init__(self):
        self.player = xbmc.Player()
        self.playback_started = False
        self.video_path = None

    def run_player(self):
        # --- STABILITY CHECK & DELAY ---
        # Wait for 1.5 seconds. If focus is lost during this time, abort.
        # video_path is intentionally resolved AFTER this delay so Kodi's
        # infolabel engine has time to warm up on first hover — reading it in
        # __init__ can return empty/stale on the very first call in a session.
        for _ in range(15):
            if not xbmc.getCondVisibility(f'Control.HasFocus({CONTROL_ID})') or xbmc.Monitor().abortRequested():
                return
            xbmc.sleep(200)

        # Resolve path here, after the stability window has passed.
        self.video_path = xbmc.getInfoLabel('Skin.String(IntroVideoSelectStartupValue)')

        # If no path is set or it's 'none', do nothing.
        if not self.video_path or self.video_path.lower() == 'none':
            return

        # If focus was held, proceed. Check if file exists.
        if not xbmcvfs.exists(self.video_path):
            xbmc.log(f"IntroPreview: Video file not found at path: {self.video_path}", xbmc.LOGWARNING)
            xbmc.executebuiltin(f'Notification({xbmc.getLocalizedString(31474)}, File not found, 3000, error)')
            return

        # Show the video player window and set our flag.
        self.playback_started = True
        xbmcgui.Window(10000).setProperty(PROP_SHOW_PLAYER, "true")
        xbmc.sleep(500) # Wait for skin animation.

        # --- CORRECTED PLAYBACK COMMAND ---
        # Use PlayMedia with the background flag '1' to target the <videowindow> control.
        xbmc.executebuiltin(f'PlayMedia("{self.video_path}",1,noresume)')
        xbmc.sleep(300) # Give player time to initialize.

        if self.player.isPlayingVideo():
            xbmc.executebuiltin('PlayerControl(Mute)')
        else:
            xbmc.log(f"IntroPreview: Player failed to start for {self.video_path}", xbmc.LOGERROR)
            self.playback_started = False
            return

        # Loop to keep script alive while video plays in the preview window.
        while self.player.isPlayingVideo() and xbmc.getCondVisibility(f'Control.HasFocus({CONTROL_ID})') and not xbmc.Monitor().abortRequested():
            xbmc.sleep(100)

    def cleanup(self):
        # Only perform cleanup if playback was actually initiated.
        if self.playback_started:
            xbmcgui.Window(10000).clearProperty(PROP_SHOW_PLAYER)
            if self.player.isPlayingVideo():
                self.player.stop()
                xbmc.sleep(500) # Delay to prevent addon conflicts.
        
        # Always clear the master running flag on exit.
        xbmcgui.Window(10000).clearProperty(PROP_RUNNING)

def run(params=None):
    # --- SINGLETON CHECK ---
    if xbmcgui.Window(10000).getProperty(PROP_RUNNING) == "true":
        return
    xbmcgui.Window(10000).setProperty(PROP_RUNNING, "true")

    player_instance = IntroPlayer()
    try:
        player_instance.run_player()
    except Exception as e:
        xbmc.log(f"IntroPreview Script Unhandled Exception: {str(e)}", xbmc.LOGERROR)
    finally:
        # Ensures cleanup is always called to prevent leftover processes.
        player_instance.cleanup()