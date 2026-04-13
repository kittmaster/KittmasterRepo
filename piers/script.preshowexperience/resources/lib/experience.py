import json
import os
import re
import time
import threading
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import datetime

import requests
from bs4 import BeautifulSoup
from contextlib import contextmanager
from .kodijsonrpc import rpc

from . import kodigui
from . import kodiutil
from . import preshowutil  # noqa E402
from . import preshowexperience  # noqa E402
# from resources.lib.kodiutil import T

kodiutil.LOG('Version: {0}'.format(kodiutil.ADDON.getAddonInfo('version')))

AUDIO_FORMATS = {
    "dts": "DTS",
    "dca": "DTS",
    "dtsma": "DTS-HD Master Audio",
    "dtshd_ma": "DTS-HD Master Audio",
    "dtshd_hra": "DTS-HD Master Audio",
    "dtshr": "DTS-HD Master Audio",
    "ac3": "Dolby Digital",
    "eac3": "Dolby Digital Plus",
    "a_truehd": "Dolby TrueHD",
    "truehd": "Dolby TrueHD"
}

GENRES = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Science Fiction",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
    37: "Western"
}

def DEBUG_LOG(msg):
    kodiutil.DEBUG_LOG('Experience: {0}'.format(msg))

def isURLFile(path):
    if path and (path.endswith('.url') or path.endswith('.pseurl')):
        return True
    return False

def resolveURLFile(path):
    try:
        with xbmcvfs.File(path, 'r') as f:
            url = f.read().strip()
    except Exception as e:
        kodiutil.ERROR('Failed to read URL from file: {0}'.format(str(e)))
        return None

    # Parse the URL to extract the video ID and format it for the Kodi YouTube plugin
    if "youtu.be/" in url:
        video_id = url.split("youtu.be/")[-1]
    elif "youtube.com/watch?v=" in url:
        video_id = url.split("youtube.com/watch?v=")[-1]
    else:
        return url  # Return the original URL if it's not a YouTube link

    # Construct the URL for the Kodi YouTube plugin
    if video_id:
        return "plugin://plugin.video.youtube/play/?video_id=" + video_id
    return None


def getIMDBAspectRatio(title, imdb_number=None):
    BASE_URL = "https://www.imdb.com/"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'}
    
    if imdb_number and str(imdb_number).startswith("tt"):
        URL = "{}/title/{}/technical/".format(BASE_URL, imdb_number)
    else:
        URL = BASE_URL + "find/?q={}".format(title)
        DEBUG_LOG('URL: {0}'.format(URL))
        search_page = requests.get(URL, headers=HEADERS)

        soup = BeautifulSoup(search_page.text, 'html.parser')

        title_url_tag = soup.select_one('.ipc-metadata-list-summary-item__t')
        if title_url_tag:
            title_url = title_url_tag['href']
            imdb_number = title_url.rsplit(
                '/title/', 1)[-1].split("/")[0]

            URL = BASE_URL + title_url
            
        # URL = "{}find?q={}&s=tt".format(BASE_URL, title.replace(' ', '+'))
        # search_page = requests.get(URL, headers=HEADERS)
        # soup = BeautifulSoup(search_page.text, 'html.parser')
        # title_url_tag = soup.select_one('td.result_text a')

        # if title_url_tag and title.lower() in title_url_tag.text.lower():
            # imdb_number = title_url_tag['href'].split('/')[2]
            # URL = "{}/title/{}/technical/".format(BASE_URL, imdb_number)
        # else:
            # DEBUG_LOG('No matching title URL found or title does not match')
            # return '1.85'  # Default or fallback aspect ratio if not found

    tech_specs_page = requests.get(URL, headers=HEADERS)
    soup = BeautifulSoup(tech_specs_page.text, 'html.parser')
    aspect_ratio_li = soup.find("li", id="aspectratio")
    aspect_ratios = []

    if aspect_ratio_li:
        for li in aspect_ratio_li.find_all("span", class_="ipc-metadata-list-item__list-content-item"):
            aspect_ratio = li.get_text(strip=True).split(':')[0]
            next_span = li.find_next_sibling("span")
            description = next_span.text.strip() if next_span else "No description available"
            # Check if the description contains "theatrical" and mark it as recommended
            if "theatrical" in description.lower():
                description += " **Recommended"
            aspect_ratios.append(f"{aspect_ratio} - {description}")

        # If multiple aspect ratios, let the user choose
        if len(aspect_ratios) > 1:
            dialog = xbmcgui.Dialog()
            choice = dialog.select("Choose an Aspect Ratio", aspect_ratios)
            if choice == -1:
                return '1.85'  # Default or fallback if user cancels the dialog
            selected_aspect_ratio = aspect_ratios[choice].split(' - ')[0]
            return selected_aspect_ratio

        elif aspect_ratios:
            return aspect_ratios[0].split(' - ')[0]

    return '1.85'  # Fallback aspect ratio if not found or no aspect ratios are listed
    
class KodiVolumeControl:
    def __init__(self, abort_flag):
        self.saved = None
        self.abortFlag = abort_flag
        self._stopFlag = False
        self._fader = None
        self._restoring = False

    def current(self):
        return rpc.Application.GetProperties(properties=['volume'])['volume']

    def fading(self):
        if not self._fader:
            return False

        return self._fader.is_alive()

    def _set(self, volume):
        xbmc.executebuiltin("SetVolume({0})".format(volume))

    def store(self):
        if self.saved:
            return

        self.saved = self.current()

    def restore(self, delay=0):
        if self._restoring:
            return

        self._restoring = True
        try:
            if self.saved is None:
                return

            if delay:
                xbmc.sleep(delay)

            DEBUG_LOG('Restoring volume to: {0}'.format(self.saved))

            self._set(self.saved)
            self.saved = None
        finally:
            self._restoring = False

    def set(self, volume_or_pct, fade_time=0, relative=False):
        self.store()
        if relative:
            volume = int(self.saved * (volume_or_pct / 100.0))
            DEBUG_LOG('Setting volume to: {0} ({1}%)'.format(volume, volume_or_pct))
        else:
            volume = volume_or_pct
            DEBUG_LOG('Setting volume to: {0}'.format(volume))

        if fade_time:
            current = self.current()
            self._fade(current, volume, fade_time)
        else:
            self._set(volume)

    def stop(self):
        self._stopFlag = True

    def _stop(self):
        if self._stopFlag:
            self._stopFlag = False
            return True
        return False

    def _fade(self, start, end, fade_time_millis):
        if self.fading():
            self.stop()
            self._fader.join()
        self._fader = threading.Thread(target=self._fadeWorker, args=(start, end, fade_time_millis))
        self._fader.start()

    def _fadeWorker(self, start, end, fade_time_millis):
        volWidth = end - start

        func = end > start and min or max

        duration = fade_time_millis / 1000.0
        endTime = time.time() + duration
        vol = start
        left = duration

        DEBUG_LOG('Fade: START ({0}) - {1}ms'.format(start, fade_time_millis))
        while time.time() < endTime and not kodiutil.wait(0.1):
            while xbmc.getCondVisibility('Player.Paused') and not kodiutil.wait(0.1):
                endTime = time.time() + left

            if xbmc.Monitor().abortRequested() or not xbmc.getCondVisibility(
                    'Player.Playing') or self.abortFlag.is_set() or self._stop():
                DEBUG_LOG(
                    'Fade ended early({0}): {1}'.format(vol, not xbmc.getCondVisibility(
                        'Player.Playing') and 'NOT_PLAYING' or 'ABORT')
                )
                return
            left = endTime - time.time()
            vol = func(end, int(start + (((duration - left) / duration) * volWidth)))
            self._set(vol)

        DEBUG_LOG('Fade: END ({0})'.format(vol))

class SettingControl:
    def __init__(self, setting, log_display, disable_value=''):
        self.setting = setting
        self.logDisplay = log_display
        self.disableValue = disable_value
        self._originalMode = None
        self.store()

    def disable(self):
        rpc.Settings.SetSettingValue(setting=self.setting, value=self.disableValue)
        DEBUG_LOG('{0}: DISABLED'.format(self.logDisplay))

    def store(self):
        try:
            self._originalMode = rpc.Settings.GetSettingValue(setting=self.setting).get('value')
            DEBUG_LOG('{0}: Mode stored ({1})'.format(self.logDisplay, self._originalMode))
        except:
            kodiutil.ERROR()

    def restore(self):
        if not self._originalMode:
            return
        rpc.Settings.SetSettingValue(setting=self.setting, value=self._originalMode)
        DEBUG_LOG('{0}: RESTORED'.format(self.logDisplay))

class ExperienceWindow(kodigui.BaseWindow):
    xmlFile = 'script.preshowexperience-experience.xml'
    path = kodiutil.ADDON_PATH
    theme = 'Main'
    res = '1080i'

    def __init__(self, *args, **kwargs):
        kodigui.BaseWindow.__init__(self, *args, **kwargs)
        kodiutil.setGlobalProperty('paused', '')
        kodiutil.setGlobalProperty('number', '')
        kodiutil.setScope()
        self.player = None
        self.action = None
        self.volume = None
        self.abortFlag = None
        self.effect = None
        self.duration = 400
        self.lastImage = ''
        self.initialized = False
        self._paused = False
        self._pauseStart = 0
        self._pauseDuration = 0
        self.inShowImageFromQueue = False
        self.clear()

    def onInit(self):
        kodigui.BaseWindow.onInit(self)
        self.image = (self.getControl(100), self.getControl(101))
        self.skipNotice = self.getControl(200)
        self.initialized = True

    def join(self):
        while not kodiutil.wait(0.1) and not self.abortFlag.is_set():
            if self.initialized:
                return

    def initialize(self):
        self.clear()
        self.action = None

    def setImage(self, url):
        #kodiutil.DEBUG_LOG(f"ExperienceWindow: Setting image - {url}")
        self._paused = False
        self._pauseStart = 0
        self._pauseDuration = 0

        if not self.effect:
            return

        if self.effect == 'none':
            self.none(url)
        elif self.effect == 'fade':
            self.change(url)
        elif self.effect == 'fadesingle':
            self.change(url)
        elif self.effect.startswith('slide'):
            self.change(url)

    def none(self, url):
        self.lastImage = url
        kodiutil.setGlobalProperty('image0', url)

    def change(self, url):
        kodiutil.setGlobalProperty('image0', self.lastImage)
        kodiutil.setGlobalProperty('show1', '')
        xbmc.sleep(100)
        kodiutil.setGlobalProperty('image1', url)
        kodiutil.setGlobalProperty('show1', '1')
        self.lastImage = url

    def clear(self):
        self.currentImage = 0
        self.lastImage = ''
        kodiutil.setGlobalProperty('image0', '')
        kodiutil.setGlobalProperty('image1', '')
        kodiutil.setGlobalProperty('show1', '')

    def setTransition(self, effect=None, duration=400):
        self.duration = duration
        self.effect = effect or 'none'
        if self.effect == 'none':
            self.image[1].setAnimations([])
        elif self.effect == 'fade':
            self.image[1].setAnimations([
                ('Visible', 'effect=fade start=0 end=100 time={duration}'.format(duration=self.duration)),
                ('Hidden', 'effect=fade start=100 end=0 time=0')
            ])
        elif self.effect == 'fadesingle':
            self.image[1].setAnimations([
                ('Visible', 'effect=fade start=0 end=100 time={duration}'.format(duration=self.duration)),
                ('Hidden', 'effect=fade start=100 end=0 time={duration}'.format(duration=self.duration))
            ])
        elif self.effect == 'slideL':
            self.image[1].setAnimations([
                ('Visible', 'effect=slide start=1980,0 end=0,0 time={duration}'.format(duration=self.duration)),
                ('Hidden', 'effect=slide start=0,0 end=1980,0 time=0')
            ])
        elif self.effect == 'slideR':
            self.image[1].setAnimations([
                ('Visible', 'effect=slide start=-1980,0 end=0,0 time={duration}'.format(duration=self.duration)),
                ('Hidden', 'effect=slide start=0,0 end=-1980,0 time=0')
            ])
        elif self.effect == 'slideU':
            self.image[1].setAnimations([
                ('Visible', 'effect=slide start=0,1080 end=0,0 time={duration}'.format(duration=self.duration)),
                ('Hidden', 'effect=slide start=0,0 end=0,1080 time=0')
            ])
        elif self.effect == 'slideD':
            self.image[1].setAnimations([
                ('Visible', 'effect=slide start=0,-1080 end=0,0 time={duration}'.format(duration=self.duration)),
                ('Hidden', 'effect=slide start=0,0 end=-1080 time=0')
            ])

    def fadeOut(self):
        kodiutil.setGlobalProperty('show1', '')

    def onAction(self, action):
        scriptAddon = xbmcaddon.Addon('script.preshowexperience')
        shieldskipbutton = scriptAddon.getSetting('shieldskip.button')
        #DEBUG_LOG('Shield skip button: {0}'.format(shieldskipbutton)) 
       
        try:
            if action == xbmcgui.ACTION_PREVIOUS_MENU or action == xbmcgui.ACTION_NAV_BACK or action == xbmcgui.ACTION_STOP:
                self.volume.stop()
                self.abortFlag.set()
                self.doClose()                    
            elif action == xbmcgui.ACTION_MOVE_RIGHT:
                if self.action != 'SKIP':
                    self.action = 'NEXT'
            elif action == xbmcgui.ACTION_MOVE_LEFT:
                if self.action != 'BACK':
                    self.action = 'PREV'
            elif action == xbmcgui.ACTION_MOVE_UP:
                if self.action != 'SKIP':
                    self.action = 'BIG_NEXT'
            elif action == xbmcgui.ACTION_MOVE_DOWN:
                if self.action != 'BACK':
                    self.action = 'BIG_PREV'
            elif action == xbmcgui.ACTION_PAGE_UP or action == xbmcgui.ACTION_NEXT_ITEM:
                self.action = 'SKIP'
            elif action == xbmcgui.ACTION_PAGE_DOWN or action == xbmcgui.ACTION_PREV_ITEM:
                self.action = 'BACK'
            elif action == xbmcgui.ACTION_PAUSE:
                self.pause()
            elif action == xbmcgui.ACTION_PLAYER_FORWARD and shieldskipbutton == "Fast Forward":
                self.action = 'SKIP'
            elif action == xbmcgui.ACTION_SELECT_ITEM and shieldskipbutton == "Select":
                self.action = 'SKIP'
            elif action == xbmcgui.ACTION_CONTEXT_MENU:
                return
        except:
            kodiutil.ERROR()
            return kodigui.BaseWindow.onAction(self, action)

        kodigui.BaseWindow.onAction(self, action)
        
    def onPause(self):
        self.player.onPlayBackPaused()
        kodiutil.setGlobalProperty('paused', '1')

    def onResume(self):
        self.player.onPlayBackResumed()
        kodiutil.setGlobalProperty('paused', '')

    def hasAction(self):
        return bool(self.action)
            
    def pause(self):
        if xbmc.getCondVisibility('Player.HasAudio'):
            if xbmc.getCondVisibility('Player.Paused'):
                self._pauseStart = time.time()
                self._paused = True
            else:
                self._pauseDuration = time.time() - self._pauseStart
                self.action = 'RESUME'
        else:
            if self._paused:
                self._pauseDuration = time.time() - self._pauseStart
                self.action = 'RESUME'
                self.onResume()
            else:
                self._pauseStart = time.time()
                self._paused = True
                self.onPause()

    def pauseDuration(self):
        pd = self._pauseDuration
        self._pauseDuration = 0
        return pd

    def finishPause(self):
        self._paused = False
        self._pauseStart = 0

    def getAction(self):
        action = self.action
        self.action = None
        return action

    def skip(self):
        if self.action == 'SKIP':
            self.action = None
            return True
        return False

    def back(self):
        if self.action == 'BACK':
            self.action = None
            return True
        return False

    def next(self):
        if self.action == 'NEXT':
            self.action = None
            return True
        return False

    def prev(self):
        if self.action == 'PREV':
            self.action = None
            return True
        return False

    def bigNext(self):
        if self.action == 'BIG_NEXT':
            self.action = None
            return True
        return False

    def bigPrev(self):
        if self.action == 'BIG_PREV':
            self.action = None
            return True
        return False

    def paused(self):
        return self._paused

    def resume(self):
        if self.action == 'RESUME':
            self.action = None
            return True
        return False

    def setSkipNotice(self, msg):
        kodiutil.setGlobalProperty('number', msg)
        self.skipNotice.setAnimations(
            [('Conditional', 'effect=fade start=100 end=0 time=500 delay=1000 condition=true')])

def requiresStart(func):
    def wrapper(self, *args, **kwargs):
        if hasattr(self, 'processor'):
            return func(self, *args, **kwargs)
        else:
            return None

    return wrapper

class ExperiencePlayer(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.current_chapter = 0
        self.total_chapters = 0
        self.last_chapter_triggered = False
        self.middle_chapter_triggered = False
        self.is_tracking_chapters = False
        self.track_chapters = False
        self.is_feature_playing = False
        self.monitor = xbmc.Monitor()
        self.tracking_thread = None
        
    NOT_PLAYING = 0
    PLAYING_DUMMY_NEXT = -1
    PLAYING_DUMMY_PREV = -2
    PLAYING_MUSIC = -10
    MUSIC_STOPPED = -20

    DUMMY_FILE_PREV = 'PREV.mp4'
    DUMMY_FILE_NEXT = 'NEXT.mp4'

    def create(self, from_editor=False):
        # xbmc.Player.__init__(self)
        self.fromEditor = from_editor
        self.playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        self.fakeFilePrev = os.path.join(kodiutil.ADDON_PATH, 'resources', 'videos', self.DUMMY_FILE_PREV)
        self.fakeFileNext = os.path.join(kodiutil.ADDON_PATH, 'resources', 'videos', self.DUMMY_FILE_NEXT)
        self.featureStub = os.path.join(kodiutil.ADDON_PATH, 'resources', 'videos', 'preshow_feature.mp4')
        self.playStatus = self.NOT_PLAYING
        self.hasFullscreened = False
        self.loadActions()
        self.init()
        return self

    def setPlayStatus(self, status):
        self.playStatus = status

    def doPlay(self, item, listitem=None, windowed=None, startpos=None):
        self.setPlayStatus(self.NOT_PLAYING)
        self.play(item)

    # PLAYER EVENTS
    @requiresStart
    def onPlayBackEnded(self):
        if self.playStatus != self.PLAYING_MUSIC:
            self.volume.restore()

        if self.playStatus == self.PLAYING_MUSIC or self.playStatus == self.MUSIC_STOPPED:
            self.setPlayStatus(self.NOT_PLAYING)
            DEBUG_LOG('MUSIC ENDED')
            return
        elif self.playStatus == self.NOT_PLAYING:
            return self.onPlayBackFailed()

        self.setPlayStatus(self.NOT_PLAYING)

        if self.playlist.getposition() != -1:
            DEBUG_LOG('PLAYBACK ENDED')
            if self.playlist.size():
                return

        self.is_tracking_chapters = False
        self.next()

    @requiresStart
    def onPlayBackPaused(self):       
        DEBUG_LOG('PLAYBACK PAUSED')
        if self.pauseAction:
            DEBUG_LOG('Executing pause action: {0}'.format(self.pauseAction))
            self.pauseAction.run()
        
        if self.track_chapters:
            self.is_tracking_chapters = False
            DEBUG_LOG("Chapter tracking paused.")          
            
    @requiresStart
    def onPlayBackResumed(self):
        DEBUG_LOG("Playback Resumed.")       
        if self.resumeAction is True:
            resumeAction = self.processor.lastAction()
            if resumeAction:
                DEBUG_LOG('Executing resume action (last): {0}'.format(resumeAction))
                resumeAction.run()
        elif self.resumeAction:
            DEBUG_LOG('Executing resume action: {0}'.format(self.resumeAction))
            self.resumeAction.run()
            
        if self.track_chapters:
            self.start_chapter_tracking()
            self.is_tracking_chapters = True
            DEBUG_LOG("Resuming chapter tracking.")

    def start_chapter_tracking(self):
        if not self.lastChapterAction and not self.middleChapterAction:
            DEBUG_LOG("No chapter actions are configured.")
            return
        
        self.is_tracking_chapters = True
        if not self.tracking_thread or not self.tracking_thread.is_alive():
            self.tracking_thread = threading.Thread(target=self.track_chapters_loop)
            self.tracking_thread.start()
 
    def track_chapters_loop(self):
        middle_chapter = self.total_chapters // 2
        while not self.monitor.waitForAbort(3) and self.is_tracking_chapters:
            new_chapter = int(xbmc.getInfoLabel('Player.Chapter'))
            if new_chapter != self.current_chapter:
                DEBUG_LOG(f"Chapter changed from {self.current_chapter} to {new_chapter}")
                self.current_chapter = new_chapter
                self.handle_chapter_actions(new_chapter, middle_chapter)

    def stop_chapter_tracking(self):
        self.is_tracking_chapters = False
        if self.tracking_thread:
            self.tracking_thread.join()
        DEBUG_LOG("Chapter tracking stopped.")
                
    def handle_chapter_actions(self, new_chapter, middle_chapter):
        if new_chapter == self.total_chapters and not self.last_chapter_triggered and self.lastChapterAction:
            self.onLastChapter()
        if new_chapter == middle_chapter and not self.middle_chapter_triggered and self.middleChapterAction:
            self.onMiddleChapter()
            
    @requiresStart
    def onLastChapter(self):
        self.lastChapterAction.run()
        self.last_chapter_triggered = True
        DEBUG_LOG("Last chapter action triggered.")        

    @requiresStart
    def onMiddleChapter(self):
        self.middleChapterAction.run()
        self.middle_chapter_triggered = True
        DEBUG_LOG("Intermission action triggered.")            
    
        
    @requiresStart
    def onPlayBackStarted(self):
        DEBUG_LOG('Player Started')
        skip_setting = kodiutil.getSetting('allow.video.skip')
        DEBUG_LOG('Video skipping is {0}.'.format(kodiutil.getSetting('allow.video.skip')))
        DEBUG_LOG('Is feature playing: {0}'.format(self.is_feature_playing))
        skip_setting = bool(skip_setting)

        if self.is_feature_playing:
            DEBUG_LOG('Feature is playing')
            DEBUG_LOG('Waiting 10 seconds before checking for chapters.')
            xbmc.sleep(10000)
            self.total_chapters = int(xbmc.getInfoLabel('Player.ChapterCount'))
            self.current_chapter = int(xbmc.getInfoLabel('Player.Chapter'))
            self.last_chapter_triggered = False
            self.middle_chapter_triggered = False
            self.track_chapters = bool(self.lastChapterAction or self.middleChapterAction)  

            if self.total_chapters > 1 and self.track_chapters:
                self.is_tracking_chapters = True
                self.start_chapter_tracking()
                DEBUG_LOG('Playback started with chapter tracking of {0} chapters'.format(self.total_chapters))
            else:
                DEBUG_LOG("Playback started without chapter tracking.")
                if self.total_chapters < 2:
                    DEBUG_LOG('This movie has {0} chapters.'.format(self.total_chapters))                 
                if not self.lastChapterAction:
                    DEBUG_LOG("A last chapter action is not set.")
                if not self.middleChapterAction:
                    DEBUG_LOG("A middle chapter action is not set.")
        else:
            DEBUG_LOG("Playback not started or feature not playing.")
          

        if self.playStatus == self.PLAYING_MUSIC:
            DEBUG_LOG('MUSIC STARTED')
            return
            
        self.setPlayStatus(time.time())

        # Handle dummy files used for specific navigation purposes
        if self.DUMMY_FILE_PREV in self.getPlayingFile():
            self.setPlayStatus(self.PLAYING_DUMMY_PREV)
            DEBUG_LOG('Stopping for PREV dummy')
        elif self.DUMMY_FILE_NEXT in self.getPlayingFile():
            self.setPlayStatus(self.PLAYING_DUMMY_NEXT)
            DEBUG_LOG('Stopping for NEXT dummy')
        else:
            self.hasFullscreened = False

        # Log that playback has started
        DEBUG_LOG('PLAYBACK STARTED')

    @requiresStart
    def onPlayBackStopped(self):
        self.is_tracking_chapters = False
        self.is_feature_playing = False
        
        if self.playStatus != self.PLAYING_MUSIC:
            self.volume.restore()

        if self.playStatus == self.PLAYING_MUSIC or self.playStatus == self.MUSIC_STOPPED:
            self.setPlayStatus(self.NOT_PLAYING)
            DEBUG_LOG('MUSIC STOPPED')
            return
        elif self.playStatus == self.NOT_PLAYING:
            return self.onPlayBackFailed()
        elif self.playStatus == self.PLAYING_DUMMY_NEXT:
            self.setPlayStatus(self.NOT_PLAYING)
            DEBUG_LOG('PLAYBACK INTERRUPTED')
            self.next()
            return
        elif self.playStatus == self.PLAYING_DUMMY_PREV:
            self.setPlayStatus(self.NOT_PLAYING)
            DEBUG_LOG('SKIP BACK')
            self.next(prev=True)
            return

        self.setPlayStatus(self.NOT_PLAYING)
        DEBUG_LOG('PLAYBACK STOPPED')
        self.abort()

    @requiresStart
    def onPlayBackFailed(self):
        self.setPlayStatus(self.NOT_PLAYING)
        DEBUG_LOG('PLAYBACK FAILED')
        self.next()

    @requiresStart
    def onAbort(self):
        if self.abortAction:
            self.abortAction.run()
            DEBUG_LOG('Executing abort action: {0}'.format(self.abortAction))

    def getPlayingFile(self):
        if self.isPlaying():
            try:
                return xbmc.Player.getPlayingFile(self)
            except RuntimeError:
                pass
            return ''
        return ''

    def init(self):
        self.abortFlag = threading.Event()
        self.window = None
        self.volume = KodiVolumeControl(self.abortFlag)
        self.screensaver = SettingControl('screensaver.mode', 'Screensaver')
        self.visualization = SettingControl('musicplayer.visualisation', 'Visualization')
        self.playGUISounds = SettingControl('audiooutput.guisoundmode', 'Play GUI sounds', disable_value=0)
        self.features = []

        result = rpc.Playlist.GetItems(
            playlistid=xbmc.PLAYLIST_VIDEO,
            properties=['file', 'genre', 'mpaa', 'streamdetails', 'title', 'thumbnail', 'runtime', 'year', 'studio',
                        'director', 'cast', 'tag']
        )
        for r in result.get('items', []):
            feature = self.featureFromJSON(r)
            self.features.append(feature)

        if self.fromEditor and not self.features:
            feature = preshowexperience.sequenceprocessor.Feature(self.featureStub)
            feature.title = 'PreShow Feature'
            # Read Genres from settings
            feature_genres = kodiutil.getSetting('feature.genres')
            if feature_genres:
                feature.genres = [g.strip() for g in feature_genres.split(',') if g.strip()]
                valid_genres = list(GENRES.values())
                feature.genres = [g for g in feature.genres if g in valid_genres]
                if not feature.genres:
                    kodiutil.ERROR(f"All selected feature genres are invalid: {feature_genres}.")
            else:
                feature.genres = []  # Default empty list or set as needed

            # Read Rating from settings
            feature_rating = kodiutil.getSetting('feature.rating')
            kodiutil.LOG('feature_rating = {0}'.format(feature_rating))
            valid_ratings = [
                'MPAA:G', 'MPAA:PG', 'MPAA:PG-13',
                'MPAA:R', 'MPAA:NC-17', 'MPAA:NR'
            ]
            if feature_rating not in valid_ratings:
                kodiutil.ERROR(f"Invalid rating selected: {feature_rating}. Falling back to default.")
                feature_rating = 'MPAA:PG-13'
            feature.rating = feature_rating
            
            # Read Year from settings
            feature_year = kodiutil.getSetting('feature.year')
            
            if not feature_year:
                feature_year = str(datetime.datetime.now().year)  # Default to current year if not set
            else:
                # Validate Year
                try:
                    year_int = int(feature_year)
                    current_year = datetime.datetime.now().year
                    if year_int < 1950 or year_int > current_year:
                        raise ValueError("Year out of valid range.")
                    feature.year = str(year_int)
                except ValueError as ve:
                    kodiutil.ERROR(f"Invalid year selected: {feature_year}. Error: {ve}")
                    feature.year = str(datetime.datetime.now().year)  # Fallback to current year

            # Read Audio Format from settings
            feature_audio_format = kodiutil.getSetting('feature.audioFormat')
            valid_audio_formats = [
                'Auro-3D', 'Dolby Atmos', 'Dolby Digital', 'Dolby Digital Plus',
                'Dolby TrueHD', 'DTS', 'DTS-HD Master Audio', 'DTS-X',
                'Datasat', 'THX', 'Other'
            ]
            if feature_audio_format not in valid_audio_formats:
                kodiutil.ERROR(f"Invalid audio format selected: {feature_audio_format}. Falling back to default.")
                feature_audio_format = 'Dolby Digital'
            feature.audioFormat = feature_audio_format            

            self.features.append(feature)

    def loadActions(self):
        self.pauseAction = None
        self.resumeAction = None
        self.abortAction = None
        self.beforeFeatureAction = None
        self.beginningAction = None
        self.lastChapterAction = None
        self.middleChapterAction = None
        self.afterFeatureAction = None

        if kodiutil.getSetting('action.onPause', False):
            actionFile = kodiutil.getSetting('action.onPause.file')
            self.pauseAction = actionFile and preshowexperience.actions.ActionFileProcessor(actionFile) or None

        if kodiutil.getSetting('action.onResume', 0) == 2:
            actionFile = kodiutil.getSetting('action.onResume.file')
            self.resumeAction = actionFile and preshowexperience.actions.ActionFileProcessor(actionFile) or None
        elif kodiutil.getSetting('action.onResume', 0) == 1:
            self.resumeAction = True

        if kodiutil.getSetting('action.onAbort', False):
            actionFile = kodiutil.getSetting('action.onAbort.file')
            self.abortAction = actionFile and preshowexperience.actions.ActionFileProcessor(actionFile) or None
            
        if kodiutil.getSetting('action.BeforeFeature', False):
            actionFile = kodiutil.getSetting('action.BeforeFeature.file')
            if actionFile:
                self.beforeFeatureAction = preshowexperience.actions.ActionFileProcessor(actionFile)
                DEBUG_LOG(f"Before Feature Action loaded from file: {actionFile}")
            else:
                self.beforeFeatureAction = None
                DEBUG_LOG("Before Feature action file is not set.")
        else:
            self.beforeFeatureAction = None
            DEBUG_LOG("Before Feature action is disabled in settings.")
            
        if kodiutil.getSetting('action.PreshowBeginning', False):
            actionFile = kodiutil.getSetting('action.PreshowBeginning.file')
            if actionFile:
                self.PreshowBeginningAction = preshowexperience.actions.ActionFileProcessor(actionFile)
                DEBUG_LOG(f"Start of PreShow Action loaded from file: {actionFile}")
            else:
                self.PreshowBeginningAction = None
                DEBUG_LOG("Start of PreShow action file is not set.")
        else:
            self.PreshowBeginningAction = None
            DEBUG_LOG("Start of PreShow action is disabled in settings.")          
                        
        if kodiutil.getSetting('action.lastChapter', False):
            actionFile = kodiutil.getSetting('action.lastChapter.file')
            if actionFile:
                self.lastChapterAction = preshowexperience.actions.ActionFileProcessor(actionFile) or None
                DEBUG_LOG(f"Last Chapter Action loaded from file: {actionFile}")
            else:
                self.lastChapterAction = None
                DEBUG_LOG("No file selected for last chapter action.")
        else:
            self.lastChapterAction = None

        if kodiutil.getSetting('action.middleChapter', False):
            actionFile = kodiutil.getSetting('action.middleChapter.file')
            if actionFile:
                self.middleChapterAction = preshowexperience.actions.ActionFileProcessor(actionFile) or None
                DEBUG_LOG(f"Middle Chapter Action loaded from file: {actionFile}")
            else:
                self.middleChapterAction = None
                DEBUG_LOG("No file selected for last chapter action.")
        else:
            self.middleChapterAction = None            
                    
        if kodiutil.getSetting('action.onAfterFeature', False):
            actionFile = kodiutil.getSetting('action.onAfterFeature.file')
            self.afterFeatureAction = actionFile and preshowexperience.actions.ActionFileProcessor(actionFile) or None

    def formatStreamDetails(self, jsonstring):
        lines = json.dumps(jsonstring, indent=4, sort_keys=True).splitlines()
        lines = [l.replace('"', '').rstrip('[]{, ') for l in lines]
        return '\n'.join([l if not l.endswith('}') else ' ' for l in lines if l])

    def getCodecAndChannelsFromStreamDetails(self, details):
        try:
            streams = sorted(details['audio'], key=lambda x: x['channels'], reverse=True)
            for s in streams:
                codec = s['codec']
                if codec in AUDIO_FORMATS:
                    return (codec, s['channels'])
            return (streams[0]['codec'], streams[0]['channels'])
        except:
            return ('', '')
    
    def featureFromJSON(self, r):
        feature = preshowexperience.sequenceprocessor.Feature(r['file'])
        feature.title = r.get('title') or r.get('label', '')
        ratingString = preshowutil.ratingParser().getActualRatingFromMPAA(r.get('mpaa', ''), debug=True)
        if ratingString:
            feature.rating = ratingString
        feature.ID = kodiutil.intOrZero(r.get('movieid', r.get('episodeid', r.get('id', 0))))
        feature.dbType = r.get('type', '')
        feature.genres = r.get('genre', [])
        feature.tags = r.get('tag', [])
        feature.studios = r.get('studio', [])
        feature.directors = r.get('director', [])
        feature.cast = r.get('cast', [])
        feature.thumb = r.get('thumbnail', '')
        feature.runtime = r.get('runtime', 0)
        feature.year = r.get('year', 0)
        
        if kodiutil.getSetting('aspect.condition', "false").lower() == "true":

            if not self.fromEditor:
                aspect_source = kodiutil.getSetting('aspect.source', "1")

                if aspect_source == "0":  # IMDb
                    dialog = xbmcgui.Dialog()
                    dialog.notification('Aspect Ratio', 'Retrieving movie aspect ratio.', xbmcgui.NOTIFICATION_INFO, 3000)            
                    imdb_number = kodiutil.infoLabel('ListItem.IMDBNumber')
                    original_aspect_ratio = getIMDBAspectRatio(feature.title, imdb_number=imdb_number)
                    DEBUG_LOG('Original Aspect Ratio: {0}'.format(original_aspect_ratio))

                elif aspect_source == "1":  # Kodi
                    original_aspect_ratio = kodiutil.infoLabel('ListItem.VideoAspect') 
                    DEBUG_LOG('Original Aspect Ratio: {0}'.format(original_aspect_ratio))                

                original_aspect_ratio = float(original_aspect_ratio) if '.' in original_aspect_ratio else float(original_aspect_ratio) / 100
                aspect_ratios = ['1.33','1.78','1.85','2.0','2.2','2.35','2.4']
                aspect_ratios = [float(ar) for ar in aspect_ratios]
                closest_aspect_ratio = min(aspect_ratios, key=lambda x: abs(x - original_aspect_ratio))
                if closest_aspect_ratio not in aspect_ratios:
                    lower = max([ar for ar in aspect_ratios if ar < closest_aspect_ratio])
                    upper = min([ar for ar in aspect_ratios if ar > closest_aspect_ratio])
                    closest_aspect_ratio = lower if (original_aspect_ratio - lower) <= (upper - original_aspect_ratio) else upper
                original_aspect_ratio = "{:.2f}".format(closest_aspect_ratio)
                if original_aspect_ratio == '2.40':
                    original_aspect_ratio = '2.4'
                feature.videoaspect = original_aspect_ratio            

                DEBUG_LOG('Final Aspect Ratio: {0}'.format(feature.videoaspect))

        try:
            codec, channels = self.getCodecAndChannelsFromStreamDetails(r['streamdetails'])
            DEBUG_LOG('CODEC ({0}): {1} ({2} channels)'.format(kodiutil.strRepr(feature.title), codec, channels or '?'))
            DEBUG_LOG('STREAMDETAILS: \n{0}'.format(self.formatStreamDetails(r.get('streamdetails'))))
            DEBUG_LOG('Feature Genres: {0}'.format(feature.genres))

            feature.audioFormat = AUDIO_FORMATS.get(codec)
            feature.codec = codec
            feature.channels = channels
        except:
            kodiutil.ERROR()
            DEBUG_LOG('CODEC ({0}): NOT DETECTED'.format(kodiutil.strRepr(feature.title)))
            DEBUG_LOG('STREAMDETAILS: {0}'.format(repr(r.get('streamdetails'))))
            DEBUG_LOG('Feature Genres: {0}'.format(feature.genres))

        return feature

    def addCollectionMovies(self):
        DBID = kodiutil.intOrZero(xbmc.getInfoLabel('ListItem.DBID'))

        try:
            details = rpc.VideoLibrary.GetMovieSetDetails(setid=DBID)
            for m in details['setdetails']['movies']:
                try:
                    r = rpc.VideoLibrary.GetMovieDetails(
                        movieid=m['movieid'],
                        properties=['file', 'genre', 'tag', 'mpaa', 'streamdetails', 'title', 'thumbnail', 'runtime',
                                    'year', 'studio', 'director', 'cast']
                    )['moviedetails']
                    feature = self.featureFromJSON(r)
                    self.features.append(feature)
                except:
                    kodiutil.ERROR()
        except:
            kodiutil.ERROR()
            return False

        return True

    def getDBTypeAndID(self):
        return xbmc.getInfoLabel('ListItem.DBTYPE'), xbmc.getInfoLabel('ListItem.DBID')

    def addFromID(self, movieid=None, episodeid=None, selection=False, dbtype=None, dbid=None):
        if selection:
            DEBUG_LOG('Adding from selection')
            stype, ID = self.getDBTypeAndID()
            if stype == 'movie':
                movieid = ID
            elif stype in ('tvshow', 'episode'):
                episodeid = ID
            else:
                return False
        elif dbtype:
            DEBUG_LOG('Adding from DB: dbtype={0} dbid={1}'.format(dbtype, dbid))
            if dbtype == 'movie':
                movieid = dbid
            elif dbtype in ('tvshow', 'episode'):
                episodeid = dbid
        else:
            DEBUG_LOG('Adding from id: movieid={0} episodeid={1}'.format(movieid, episodeid))

        self.features = []

        feature = self.featureFromId(movieid, episodeid)
        if feature:
            self.features.append(feature)

        if not self.features:
            return False

        return True

    def featureFromId(self, movieid=None, episodeid=None):
        if movieid:
            for movieid in str(movieid).split('|'):  # ID could be int or \ seperated int string
                movieid = kodiutil.intOrZero(movieid)
                if not movieid:
                    continue

                r = rpc.VideoLibrary.GetMovieDetails(
                    movieid=movieid,
                    properties=['file', 'genre', 'tag', 'mpaa', 'streamdetails', 'title', 'thumbnail', 'runtime',
                                'year', 'studio', 'director', 'cast']
                )['moviedetails']
                r['type'] = 'movie'

                feature = self.featureFromJSON(r)
                self.features.append(feature)
        elif episodeid:
            for episodeid in str(episodeid).split('|'):  # ID could be int or \ seperated int string
                episodeid = kodiutil.intOrZero(episodeid)
                if not episodeid:
                    continue

                r = rpc.VideoLibrary.GetEpisodeDetails(
                    episodeid=episodeid,
                    properties=['file', 'streamdetails', 'title', 'thumbnail', 'runtime']
                )['episodedetails']
                r['type'] = 'tvshow'
                feature = self.featureFromJSON(r)
                self.features.append(feature)

        return None

    def addDBFeature(self, dbtype, dbid):
        return self.addFromID(dbtype=dbtype, dbid=dbid)
    
    def addSelectedFeature(self, movieid=None, episodeid=None, selection=False):
        if selection or movieid or episodeid:
            return self.addFromID(movieid, episodeid, selection)

        if xbmc.getCondVisibility('ListItem.IsCollection'):
            kodiutil.DEBUG_LOG('Selection is a collection')
            return self.addCollectionMovies()

        dbType = xbmc.getInfoLabel('ListItem.DBTYPE')
        dbID = kodiutil.infoLabel('ListItem.DBID')
        if dbType == 'movie':
            return self.addFromID(dbID, episodeid, selection)
        elif dbType == 'episode':
            return self.addFromID(movieid, dbID, selection)

        title = kodiutil.infoLabel('ListItem.Title')
        if not title:
            return False
        feature = preshowexperience.sequenceprocessor.Feature(kodiutil.infoLabel('ListItem.FileNameAndPath'))
        feature.title = title

        ratingString = preshowutil.ratingParser().getActualRatingFromMPAA(kodiutil.infoLabel('ListItem.Mpaa'), debug=True)
        if ratingString:
            feature.rating = ratingString

        feature.ID = kodiutil.intOrZero(dbID)
        feature.dbType = dbType
        feature.genres = kodiutil.infoLabel('ListItem.Genre').split(' / ')
        feature.tags = kodiutil.infoLabel('ListItem.Tag').split(' / ')
        feature.studios = kodiutil.infoLabel('ListItem.Studio').split(' / ')
        feature.directors = kodiutil.infoLabel('ListItem.Director').split(' / ')
        feature.cast = [{'name': a} for a in kodiutil.infoLabel('ListItem.Cast').split(' / ')]
        feature.thumb = kodiutil.infoLabel('ListItem.Art(thumb)')
        feature.year = kodiutil.infoLabel('ListItem.Year')

        if kodiutil.getSetting('aspect.condition', "false").lower() == "true":
            if not self.fromEditor:
                aspect_source = kodiutil.getSetting('aspect.source', "1")

                if aspect_source == "0":  # IMDb
                    dialog = xbmcgui.Dialog()
                    dialog.notification('Aspect Ratio', 'Retrieving movie aspect ratio.', xbmcgui.NOTIFICATION_INFO, 3000)            
                    imdb_number = kodiutil.infoLabel('ListItem.IMDBNumber')
                    original_aspect_ratio = getIMDBAspectRatio(feature.title, imdb_number=imdb_number)
                    DEBUG_LOG('Original Aspect Ratio: {0}'.format(original_aspect_ratio))

                elif aspect_source == "1":  # Kodi
                    original_aspect_ratio = kodiutil.infoLabel('ListItem.VideoAspect') 
                    DEBUG_LOG('Original Aspect Ratio: {0}'.format(original_aspect_ratio))                

                original_aspect_ratio = float(original_aspect_ratio) if '.' in original_aspect_ratio else float(original_aspect_ratio) / 100
                aspect_ratios = ['1.33','1.78','1.85','2.0','2.2','2.35','2.4']
                aspect_ratios = [float(ar) for ar in aspect_ratios]
                closest_aspect_ratio = min(aspect_ratios, key=lambda x: abs(x - original_aspect_ratio))
                if closest_aspect_ratio not in aspect_ratios:
                    lower = max([ar for ar in aspect_ratios if ar < closest_aspect_ratio])
                    upper = min([ar for ar in aspect_ratios if ar > closest_aspect_ratio])
                    closest_aspect_ratio = lower if (original_aspect_ratio - lower) <= (upper - original_aspect_ratio) else upper
                original_aspect_ratio = "{:.2f}".format(closest_aspect_ratio)
                if original_aspect_ratio == '2.40':
                    original_aspect_ratio = '2.4'
                feature.videoaspect = original_aspect_ratio            

                DEBUG_LOG('Final Aspect Ratio: {0}'.format(feature.videoaspect))

        try:
            feature.runtime = kodiutil.intOrZero(xbmc.getInfoLabel('ListItem.Duration')) * 60
        except TypeError:
            pass

        codec = xbmc.getInfoLabel('ListItem.AudioCodec')
        channels = kodiutil.intOrZero(xbmc.getInfoLabel('ListItem.AudioChannels'))

        if codec:
            feature.audioFormat = AUDIO_FORMATS.get(codec)
            feature.codec = codec
            feature.channels = channels
            DEBUG_LOG('CODEC ({0}): {1} ({2} channels)'.format(kodiutil.strRepr(feature.title), codec, channels or '?'))
        else:
            DEBUG_LOG('CODEC ({0}): NOT DETECTED'.format(kodiutil.strRepr(feature.title)))

        self.features.append(feature)
        return True

    def hasFeatures(self):
        return bool(self.features)

    def selectionAvailable(self):
        return bool(kodiutil.intOrZero(xbmc.getInfoLabel('ListItem.DBID')))

    def getPathAndListItemFromVideo(self, video):
        path = video.path

        if isURLFile(path):
            path = resolveURLFile(path)
        else:
            if video.userAgent:
                path += '|User-Agent=' + video.userAgent            

        li = xbmcgui.ListItem(video.title, 'PreShow Experience', path=path)
        li.setArt({'thumb': video.thumb, 'icon': video.thumb})
        vernum = xbmc.getInfoLabel('System.BuildVersion')
        if "19" in str(vernum):
            li.setInfo('video', {'title': video.title})
        else:
            item = xbmcgui.ListItem(label='Test Item', offscreen=True)
            videoInfoTag = item.getVideoInfoTag()
            videoInfoTag.setTitle(video.title)
        return path, li

    def playVideos(self, videos, features=None):
        self.playlist.clear()
        rpc.Playlist.Clear(playlistid=xbmc.PLAYLIST_VIDEO)

        xbmc.sleep(100)

        volume = (features or videos)[0].volume
        if volume != 100:
            self.volume.set(volume, relative=True)
        
        if features:
            rpc.Playlist.Add(playlistid=xbmc.PLAYLIST_VIDEO, item={'file': self.fakeFilePrev})
            for feature in features:
                self.addFeatureToPlaylist(feature)
            rpc.Playlist.Add(playlistid=xbmc.PLAYLIST_VIDEO, item={'file': self.fakeFileNext})
            self.is_feature_playing = True
            DEBUG_LOG("Setting feature to true.")
        else:
            for video in videos:
                pli = self.getPathAndListItemFromVideo(video)
                self.playlist.add(*pli)
                self.is_feature_playing = False              
                DEBUG_LOG("Setting feature to false.")

                self.playlist.add(self.fakeFileNext)
                self.playlist.add(self.fakeFilePrev, index=0)

        self.videoPreDelay()
        rpc.Player.Open(item={'playlistid': xbmc.PLAYLIST_VIDEO, 'position': 1},
                        options={'shuffled': False, 'resume': False, 'repeat': 'off'})
        xbmc.sleep(100)
        while not xbmc.getCondVisibility(
                'VideoPlayer.IsFullscreen') and not xbmc.Monitor().abortRequested() and not self.abortFlag.is_set() and self.isPlaying():
            xbmc.executebuiltin('ActivateWindow(fullscreenvideo)')
            xbmc.sleep(100)
        self.hasFullscreened = True
        DEBUG_LOG('VIDEO HAS GONE FULLSCREEN')

    def addFeatureToPlaylist(self, feature):
        if feature.dbType == 'movie':
            item = {'movieid': feature.ID}
        elif feature.dbType == 'tvshow':
            item = {'episodeid': feature.ID}
        else:
            item = {'file': feature.path}
        rpc.Playlist.Add(playlistid=xbmc.PLAYLIST_VIDEO, item=item)

    def videoPreDelay(self):
        delay = kodiutil.getSetting('video.preDelay', 0)
        if delay:
            kodiutil.DEBUG_LOG('Video pre-dalay: {0}ms'.format(delay))
            xbmc.sleep(delay)

    def isPlayingMinimized(self):
        if not xbmc.getCondVisibility(
                'Player.Playing'):  # isPlayingVideo() returns True before video actually plays (ie. is fullscreen)
            return False

        if xbmc.getCondVisibility('VideoPlayer.IsFullscreen'):  # If all is good, let's return now
            return False

        if self.playStatus <= 0:
            return False

        if xbmc.getCondVisibility('Window.IsVisible(busydialognocancel)'):
            return False

        if time.time() - self.playStatus < 5 and not self.hasFullscreened:  # Give it a few seconds to make sure fullscreen has happened
            return False

        if xbmcgui.getCurrentWindowId() == 10028:
            xbmc.executebuiltin('Action(back)')
            return False

        if xbmcgui.getCurrentWindowId() == 10000:
            self.window.show()
            xbmc.executebuiltin('ActivateWindow(fullscreenvideo)')
            return False

        if not xbmc.getCondVisibility('VideoPlayer.IsFullscreen'):
            xbmc.sleep(500)

        return not xbmc.getCondVisibility('VideoPlayer.IsFullscreen')

    def start(self, sequence_path):
        kodiutil.setGlobalProperty('running', '1')
        xbmcgui.Window(10025).setProperty('PreShowExperienceRunning', 'True')
        self.initSkinVars()
        self.playGUISounds.disable()
        self.screensaver.disable()
        self.visualization.disable()
        #kodiutil.DEBUG_LOG('Experience Start Sequence Path: {0}'.format(sequence_path))
        try:
            return self._start(sequence_path)
        finally:
            self.playGUISounds.restore()
            self.screensaver.restore()
            self.visualization.restore()
            kodiutil.setGlobalProperty('running', '')
            xbmcgui.Window(10025).setProperty('PreShowExperienceRunning', '')
            self.initSkinVars()

    def _start(self, sequence_path):
        from . import preshowutil

        self.processor = preshowexperience.sequenceprocessor.SequenceProcessor(sequence_path,
                                                                          content_path=preshowutil.getContentPath())
        [self.processor.addFeature(f) for f in self.features]

        kodiutil.DEBUG_LOG('\n.')
        DEBUG_LOG('[ -- Started --------------------------------------------------------------- ]')

        self.openWindow()
        self.processor.process()
        self.setSkinFeatureVars()
        self.next()
        self.waitLoop()

        del self.window
        self.window = None

    def openWindow(self):
        self.window = ExperienceWindow.create()
        self.window.player = self
        self.window.volume = self.volume
        self.window.abortFlag = self.abortFlag
        self.window.join()

    def waitLoop(self):
        while not kodiutil.wait(0.1) and self.window.isOpen:
            if self.processor.atEnd():
                break

            if self.isPlayingMinimized():
                DEBUG_LOG('Fullscreen video closed - stopping')
                self.stop()
        else:
            if not self.processor.atEnd():
                self.onAbort()

        DEBUG_LOG('[ -- Finished -------------------------------------------------------------- ]\n.')
        self.window.doClose()
        rpc.Playlist.Clear(playlistid=xbmc.PLAYLIST_VIDEO)
        self.stop()

    def initSkinVars(self):
        kodiutil.setGlobalProperty('module.current', '')
        kodiutil.setGlobalProperty('module.current.name', '')
        kodiutil.setGlobalProperty('module.next', '')
        kodiutil.setGlobalProperty('module.next.name', '')
        self.initSkinFeatureVars()

    def initSkinFeatureVars(self):
        kodiutil.setGlobalProperty('feature.next.title', '')
        kodiutil.setGlobalProperty('feature.next.dbid', '')
        kodiutil.setGlobalProperty('feature.next.dbtype', '')
        kodiutil.setGlobalProperty('feature.next.path', '')

    def setSkinFeatureVars(self):
        feature = self.processor.nextFeature()

        if feature:
            kodiutil.setGlobalProperty('feature.next.title', feature.title)
            kodiutil.setGlobalProperty('feature.next.dbid', str(feature.ID))
            kodiutil.setGlobalProperty('feature.next.dbtype', feature.dbType)
            kodiutil.setGlobalProperty('feature.next.path', feature.path)
        else:
            self.initSkinFeatureVars()

    def playMusic(self, image_queue):
        if not image_queue.music:
            return

        pl = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        pl.clear()
        for s in image_queue.music:
            pl.add(s.path)

        xbmc.sleep(250)  # Without this, it will sometimes not play anything

        DEBUG_LOG('Playing music playlist: {0} song(s)'.format(len(pl)))

        self.volume.store()
        self.volume.set(1)

        self.setPlayStatus(self.PLAYING_MUSIC)
        self.play(pl, windowed=True)

        self.waitForPlayStart()  # Wait playback so fade will work
        self.volume.set(image_queue.musicVolume, fade_time=int(image_queue.musicFadeIn * 1000), relative=True)

    def stopMusic(self, image_queue=None):
        try:
            rpc.Playlist.Clear(playlistid=xbmc.PLAYLIST_MUSIC)

            if image_queue and image_queue.music:
                self.volume.set(1, fade_time=int(image_queue.musicFadeOut * 1000))
                while self.volume.fading() and not self.abortFlag.is_set() and not kodiutil.wait(0.1):
                    if self.window.hasAction() and self.window.action != 'RESUME':
                        break

            kodiutil.DEBUG_LOG('Stopping music')
            self.stop()
            self.waitForPlayStop()
            self.setPlayStatus(self.MUSIC_STOPPED)
        finally:
            self.volume.restore(delay=500)

    def waitForPlayStart(self, timeout=10000):
        giveUpTime = time.time() + timeout / 1000.0
        while not xbmc.getCondVisibility('Player.Playing') and time.time() < giveUpTime and not self.abortFlag.is_set():
            xbmc.sleep(100)

    def waitForPlayStop(self):
        while self.isPlaying() and not self.abortFlag.is_set():
            xbmc.sleep(100)

    def showImage(self, image):
        try:
            if image.fade:
                self.window.setTransition('fadesingle', image.fade)

            self.window.setImage(image.path)

            stop = time.time() + image.duration
            fadeStop = image.fade and stop - (image.fade / 1000) or 0

            while not kodiutil.wait(0.1) and (time.time() < stop or self.window.paused()):
                if fadeStop and time.time() >= fadeStop and not self.window.paused():
                    fadeStop = None
                    self.window.fadeOut()

                if not self.window.isOpen:
                    return False
                elif self.window.action:
                    if self.window.next():
                        return 'NEXT'
                    elif self.window.prev():
                        return 'PREV'
                    elif self.window.skip():
                        return 'SKIP'
                    elif self.window.back():
                        return 'BACK'
                    elif self.window.resume():
                        stop += self.window.pauseDuration()
                        self.window.finishPause()

            return True
        except Exception as e:
            kodiutil.DEBUG_LOG(f"Error encountered: {str(e)}")
        finally:
            self.window.clear()
        
    def showImageFromQueue(self, image, info, first=None):
        kodiutil.DEBUG_LOG(f"Displaying image: {image.path}, Duration: {image.duration}")
        self.window.setImage(image.path)

        stop = time.time() + image.duration
        while not kodiutil.wait(0.1) and (time.time() < stop or self.window.paused()):
            if not self.window.isOpen:
                return False

            if info.musicEnd and time.time() >= info.musicEnd and not self.window.paused():
                info.musicEnd = None
                self.stopMusic(info.imageQueue)
            elif self.window.action:
                if self.window.next():
                    return 'NEXT'
                elif self.window.prev():
                    return 'PREV'
                elif self.window.bigNext():
                    return 'BIG_NEXT'
                elif self.window.bigPrev():
                    return 'BIG_PREV'
                elif self.window.skip():
                    return 'SKIP'
                elif self.window.back():
                    return 'BACK'
                elif self.window.resume():
                    stop += self.window.pauseDuration()
                    self.window.finishPause()

            if xbmcgui.getCurrentWindowId() != self.window._winID:  # Prevent switching to another window as it's not a good idea
                self.window.show()

        return True

    class ImageQueueInfo:
        def __init__(self, image_queue, music_end):
            self.imageQueue = image_queue
            self.musicEnd = music_end

    def showImageQueue(self, image_queue):
        image_queue.reset()
        image = image_queue.next()

        start = time.time()
        end = time.time() + image_queue.duration
        musicEnd = end + image_queue.musicFadeOut

        info = self.ImageQueueInfo(image_queue, musicEnd)

        self.window.initialize()
        self.window.setTransition('none')

        xbmc.enableNavSounds(False)

        self.playMusic(image_queue)

        if xbmc.getCondVisibility('Window.IsVisible(visualisation)'):
            DEBUG_LOG('Closing visualisation window')
            xbmc.executebuiltin('Action(back)')

        self.window.setTransition(image_queue.transition, image_queue.transitionDuration)

        action = None

        try:
            while image:
                #DEBUG_LOG(' -IMAGE.QUEUE: {0}'.format(image))
                action = self.showImageFromQueue(image, info, first=True)

                if action:
                    if action == 'NEXT':
                        image = image_queue.next(extend=True) or image
                        continue
                    elif action == 'PREV':
                        image = image_queue.prev() or image
                        continue
                    elif action == 'BIG_NEXT':
                        self.window.setSkipNotice('+3')
                        image = image_queue.next(count=3, extend=True) or image
                        continue
                    elif action == 'BIG_PREV':
                        self.window.setSkipNotice('-3')
                        image = image_queue.prev(count=3) or image
                        continue
                    elif action == 'BACK':
                        DEBUG_LOG(' -IMAGE.QUEUE: Skipped after {0}secs'.format(int(time.time() - start)))
                        return False
                    elif action == 'SKIP':
                        DEBUG_LOG(' -IMAGE.QUEUE: Skipped after {0}secs'.format(int(time.time() - start)))
                        return True
                    else:
                        if action is True:
                            image_queue.mark(image)

                        image = image_queue.next(start)
                else:
                    return
        except Exception as e:
            kodiutil.DEBUG_LOG(f"Error encountered: {str(e)}")
        finally:
            kodiutil.setGlobalProperty('paused', '')
            xbmc.enableNavSounds(True)
            self.stopMusic(action != 'BACK' and image_queue or None)
            if self.window.hasAction():
                if self.window.getAction() == 'BACK':
                    return False
            self.window.clear()

        DEBUG_LOG(' -IMAGE.QUEUE: Finished after {0}secs'.format(int(time.time() - start)))
        return True

    def showVideoQueue(self, video_queue):
        pl = []
        for v in video_queue.queue:
            pl.append(v.path)
            video_queue.mark(v)

        self.playVideos(pl)

    def showVideo(self, video):
        DEBUG_LOG('Video type is {0}.'.format(video.type))
        self.chapters_actions = bool(self.lastChapterAction or self.middleChapterAction)
        if kodiutil.getSetting('allow.video.skip', True) or self.chapters_actions:
            if video.type == 'FEATURE':
                self.playVideos(None, features=[video])
                self.setSkinFeatureVars()
            else:
                self.playVideos([video])
        else:
            self.play(*self.getPathAndListItemFromVideo(video))

    def doAction(self, action):
        action.run()

    def doGoto(self, goto):
        return goto.run()

    def next(self, prev=False):
        if not self.processor or self.processor.atEnd():
            return

        if not self.window.isOpen:
            self.abort()
            return

        xbmc.sleep(100)

        if prev:
            playable = self.processor.prev()
        else:
            playable = self.processor.next()

        if playable is None:
            self.window.doClose()
            return

        DEBUG_LOG('Playing next item: {0}'.format(playable))
        DEBUG_LOG('Playable type is {0}.'.format(playable.type))

        if playable.type not in ('ACTION', 'COMMAND', 'GOTO'):
            kodiutil.setGlobalProperty('module.current', playable.module._type)
            kodiutil.setGlobalProperty('module.current.name', playable.module.displayRaw())
            kodiutil.setGlobalProperty('module.next',
                                       self.processor.upNext() and self.processor.upNext().module._type or '')
            kodiutil.setGlobalProperty('module.next.name',
                                       self.processor.upNext() and self.processor.upNext().module.displayRaw() or '')

        if playable.type == 'IMAGE':
            try:
                action = self.showImage(playable)
            except Exception as e:
                kodiutil.DEBUG_LOG(f"Error encountered: {str(e)}")
            finally:
                self.window.clear()

            if action == 'BACK':
                self.next(prev=True)
            else:
                self.next()

        elif playable.type == 'IMAGE.QUEUE':
            if not self.showImageQueue(playable):
                self.next(prev=True)
            else:
                self.next()

        elif playable.type == 'VIDEO.QUEUE':
            self.showVideoQueue(playable)

        elif playable.type in ('VIDEO'):
            self.showVideo(playable)
        
        elif playable.type in ('FEATURE'):
            if self.beforeFeatureAction:
                try:
                    self.beforeFeatureAction.run()
                    DEBUG_LOG('Before Feature action executed successfully.')
                    xbmc.sleep(1000)
                except Exception as e:
                    DEBUG_LOG(f"Error executing Before Feature action: {str(e)}")
            else:
                DEBUG_LOG('No Before Feature action to execute.')
            self.showVideo(playable)            

        elif playable.type == 'ACTION':
            self.doAction(playable)
            self.next()

        elif playable.type == 'GOTO':
            offset = self.doGoto(playable)
            if offset == 0:
                self.next()
            else:
                self.processor.seekToFirstPlayableAtOffset(offset)
                if self.processor.pos == 0:
                    # As we are already at the beginning, we have to make sure that next() will retrieve the first playable
                    self.next(prev=True)
                else:
                    self.next()                                    
        else:
            DEBUG_LOG('NOT PLAYING: {0}'.format(playable))
            self.next()

    def abort(self):
        self.abortFlag.set()
        DEBUG_LOG('ABORT')
        self.window.doClose()
