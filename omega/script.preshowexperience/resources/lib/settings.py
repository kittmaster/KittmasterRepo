import os
import re
import shutil
import xbmcvfs
import xbmc
import xbmcgui

from . import kodiutil
from . import preshowexperience
from . import preshowutil
from . import pyqrcode
from . import kodigui
from .pastebin_python import PastebinPython
from .preshowexperience import database as DB
from .kodiutil import T

def clearDBWatchedStatus():
    rows = DB.Trailers.update(watched=False).where(
        DB.Trailers.watched == 1
    ).execute()

    import xbmcgui
    xbmcgui.Dialog().ok(T(32515, 'Done'), T(32564, 'Removed watched status from {0} trailers.').format(rows))

def clearDBBrokenStatus():
    rows = DB.Trailers.update(broken=False).where(
        DB.Trailers.broken == 1
    ).execute()

    import xbmcgui
    xbmcgui.Dialog().ok(T(32515, 'Done'), T(32565, 'Removed broken status from {0} trailers.').format(rows))

def pasteLog():
    yes = xbmcgui.Dialog().yesno(
        T(32519, 'Choose'),
        T(32566, 'Would you like to paste the current old log?  Paste the old log if you are in a new session, ie. after a Kodi crash.'),
        T(32568, 'Current'),
        T(32569, 'Old')
    )
    if yes:
        _pasteLog('kodi.old.log')
    else:
        _pasteLog()

def _pasteLog(logName='kodi.log'):
    logPath = os.path.join(xbmcvfs.translatePath('special://logpath'), logName)

    if not os.path.exists(logPath):
        xbmcgui.Dialog().ok(T(32570, 'No Log'), T(32571, 'That log file does not exist!'))
        return False

    def debug_log(msg):
        kodiutil.DEBUG_LOG('PASTEBIN: {0}'.format(msg))

    replaces = (
        ('//.+?:.+?@', '//USER:PASSWORD@'),
        ('<user>.+?</user>', '<user>USER</user>'),
        ('<pass>.+?</pass>', '<pass>PASSWORD</pass>'),
    )

    apiUserKeyFile = os.path.join(kodiutil.PROFILE_PATH, 'settings.pb.key')
    apiUserKey = ''
    if os.path.exists(apiUserKeyFile):
        with open(apiUserKeyFile, 'r') as f:
            apiUserKey = f.read() or ''

    pb = PastebinPython(api_dev_key=kodiutil.getPeanutButter(), api_user_key=apiUserKey)

    apiUser = kodiutil.getSetting('pastebin.user')
    if apiUser and not apiUserKey:
        debug_log('Username set, asking user for password')
        password = xbmcgui.Dialog().input(
            T(32572, 'Enter Pastebin password (only needed 1st time - NOT stored)'),
            '',
            xbmcgui.INPUT_ALPHANUM,
            xbmcgui.ALPHANUM_HIDE_INPUT
        )
        if password:
            debug_log('Getting API user key')
            apiUserKey = pb.createAPIUserKey(apiUser, password)
            if apiUserKey.lower().startswith('bad'):
                xbmcgui.Dialog().ok(T(32573, 'Failed'), '{0}: {1}'.format(T(32574, 'Failed to create paste as user'), apiUser), '', apiUserKey)
                debug_log('Failed get user API key ({0}): {1}'.format(apiUser, apiUserKey))
            else:
                with open(apiUserKeyFile, 'w') as f:
                    f.write(apiUserKey)
        else:
            debug_log('User aborted')
            xbmcgui.Dialog().ok(T(32575, 'Aborted'), T(32576, 'Paste aborted!'))
            return False

    elif apiUserKey:
        debug_log('Creating paste with stored API key')

    with kodiutil.Progress('Pastebin', T(32577, 'Creating paste...')):
        with open(logPath, 'r', encoding='utf-8') as f:
            content = f.read()
            for pattern, repl in replaces:
                content = re.sub(pattern, repl, content)
            urlOrError = pb.createPaste(content, 'Kodi PreShow Experience LOG: {0}'.format(logName), api_paste_private=1, api_paste_expire_date='1W')

    showQR = False
    if urlOrError.startswith('http'):
        showQR = xbmcgui.Dialog().yesno(
            T(32515, 'Done'),
            T(32578, 'Paste created at:') + ' ' + urlOrError,
            T(32579, 'OK'),
            T(32580, 'Show QR Code')
        )
        debug_log('Paste created: {0}'.format(urlOrError))
    else:
        xbmcgui.Dialog().ok(T(32573, 'Failed'), T(32581, 'Failed to create paste:') + ' ' + urlOrError)
        debug_log('Failed to create paste: {0}'.format(urlOrError))

    if showQR:
        showQRCode(urlOrError)

    return True

def showQRCode(url):
    class ImageWindow(kodigui.BaseDialog):
        xmlFile = 'script.preshowexperience-image.xml'
        path = kodiutil.ADDON_PATH
        theme = 'Main'
        res = '1080i'

        def __init__(self, *args, **kwargs):
            kodigui.BaseDialog.__init__(self)
            self.image = kwargs.get('image')

        def onFirstInit(self):
            self.setProperty('image', self.image)

    with kodiutil.Progress(T(32582, 'QR Code'), T(32583, 'Creating QR code...')):
        code = pyqrcode.create(url)
        QRDir = os.path.join(kodiutil.PROFILE_PATH, 'settings', 'QR')
        if not os.path.exists(QRDir):
            os.makedirs(QRDir)
        QR = os.path.join(QRDir, 'QR.png')
        code.png(QR, scale=6)
    # rpc.Player.Open(item={'path': QRDir})
    ImageWindow.open(image=QR)

def deleteUserKey():
    apiUserKeyFile = os.path.join(kodiutil.PROFILE_PATH, 'settings.pb.key')
    if os.path.exists(apiUserKeyFile):
        os.remove(apiUserKeyFile)
    xbmcgui.Dialog().ok(T(32515, 'Done'), T(32585, 'User key deleted.'))

def removeContentDatabase():
    dbFile = os.path.join(kodiutil.PROFILE_PATH, 'content.db')
    if os.path.exists(dbFile):
        os.remove(dbFile)
    tmdb_path = os.path.join(kodiutil.PROFILE_PATH, 'tmdb.last')
    if os.path.exists(tmdb_path):
        os.remove(tmdb_path)
    imdb_path =os.path.join(kodiutil.PROFILE_PATH, 'imdb.last')
    if os.path.exists(imdb_path):
        os.remove(imdb_path)
    kodiutil.setSetting('content.initialized', False)
    xbmcgui.Dialog().ok(T(32515, 'Done'), T(32584, 'Database reset.'))

def setDefaultSequence(setting):
    selection = preshowutil.selectSequence()
    if not selection:
        return

    kodiutil.setSetting(setting, selection['name'])

def setScrapers():
    selected = [s.strip().lower() for s in kodiutil.getSetting('trailer.scrapers', '').split(',')]
    contentScrapers = preshowexperience.util.contentScrapers()
    temp = [list(x) for x in preshowexperience.sequence.Trailer._scrapers]
    options = []
    for s in temp:
        for ctype, c in contentScrapers:
            if ctype == 'trailers' and c == s[0]:
                s[2] = s[2] in selected
                options.append(s)
    options.sort(key=lambda i: i[0].lower() in selected and selected.index(i[0].lower())+1 or 99)

    result = preshowutil.multiSelect(options, default=True)

    if result is False or result is None:
        return

    kodiutil.setSetting('trailer.scrapers', result)

def testEventActions(action):
    path = None

    if action == 'PAUSE':
        if kodiutil.getSetting('action.onPause', False):
            path = kodiutil.getSetting('action.onPause.file', '')
    elif action == 'RESUME':
        if kodiutil.getSetting('action.onResume', 0) == 2:
            path = kodiutil.getSetting('action.onResume.file', '')
    elif action == 'ABORT':
        if kodiutil.getSetting('action.onAbort', False):
            path = kodiutil.getSetting('action.onAbort.file', '')
    elif action == 'lastChapter':
        if kodiutil.getSetting('action.lastChapter', False):
            path = kodiutil.getSetting('action.lastChapter.file', '')
    elif action == 'middleChapter':
        if kodiutil.getSetting('action.middleChapter', False):
            path = kodiutil.getSetting('action.middleChapter.file', '')            
    elif action == 'PreshowBeginning':
        if kodiutil.getSetting('action.PreshowBeginning', False):
            path = kodiutil.getSetting('action.PreshowBeginning.file', '')            
    elif action == 'BeforeFeature':
        if kodiutil.getSetting('action.BeforeFeature', False):
            path = kodiutil.getSetting('action.BeforeFeature.file', '')
    elif action == 'AfterFeature':
        if kodiutil.getSetting('action.AfterFeature', False):
            path = kodiutil.getSetting('action.AfterFeature.file', '')            

    if not path:
        xbmcgui.Dialog().ok(T(32090, 'Not Set'), T(32330, 'This action is not set or not yet applied.'))
        return

    preshowutil.evalActionFile(path)