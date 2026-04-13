import time
import xbmc
import xbmcaddon

scriptAddon = xbmcaddon.Addon('script.preshowexperience')

def LOG(msg):
    xbmc.log(msg, xbmc.LOGNOTICE)

class Service(xbmc.Monitor):
    def __init__(self):
        self._pollInterval = 300
        self.start()

    def start(self):
        self.onKodiStarted()
        while not self.waitForAbort(self._pollInterval):
            self.poll()

    def onKodiStarted(self):
        if scriptAddon.getSetting('service.database.update.kodiStartup') == 'true':
            self.updateContent()

    def onScanFinished(self, library):
        if library == 'video' and scriptAddon.getSetting('service.database.update.scanFinished') == 'true':
            self.updateContent()

    def poll(self):
        try:
            interval = int(scriptAddon.getSetting('service.database.update.interval')) * 3600  # 1 hour
        except ValueError:
            return

        last = self.getUpdateTime()
        now = time.time()

        if now - last >= interval:
            self.updateContent()

    def updateContent(self):
        self.markUpdateTime()
        xbmc.executebuiltin('RunScript(script.preshowexperience,update.database)')

    def markUpdateTime(self):
        now = int(time.time())
        scriptAddon.setSetting('service.update.last', str(now))

    def getUpdateTime(self):
        try:
            return int(scriptAddon.getSetting('service.update.last'))
        except ValueError:
            return 0

Service()
