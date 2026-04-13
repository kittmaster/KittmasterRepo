import os
import json

import xbmcgui
import xbmcvfs

from .kodiutil import T

from . import seqattreditor
from . import kodiutil
from . import kodigui
from .preshowexperience import content
from .preshowexperience import database as DB

kodiutil.LOG('Version: {0}'.format(kodiutil.ADDON.getAddonInfo('version')))

kodiutil.checkAPILevel()

from . import preshowutil  # noqa E402

from resources.lib import preshowexperience  # noqa E402

THEME = None

def setTheme(theme_path=None):
    global THEME

    default = os.path.join(kodiutil.ADDON_PATH, 'resources', 'themes', 'default') + '/'

    if theme_path is not None:
        kodiutil.setSetting('theme.path', theme_path)
    else:
        theme_path = kodiutil.getSetting('theme.path', default)

    cfg = preshowexperience.util.pathJoin(theme_path, 'theme.json')

    try:
        with preshowexperience.util.vfs.File(cfg, 'r') as f:
            THEME = json.loads(f.read())
            THEME['theme.path'] = theme_path
            kodiutil.DEBUG_LOG(THEME)
    except:
        kodiutil.ERROR('Could not read {0}'.format(cfg))
        THEME = {
            'theme.name': '[I]Default[/I]',
            'theme.color.icon': 'FF2F80ED',
            'theme.color.setting': 'FF2F80ED',
            'theme.color.move': 'FF2F80ED',
            'theme.color.button.selected': 'FF2F80ED',
            'theme.path': default
        }

    kodiutil.DEBUG_LOG(THEME)

    kodiutil.setGlobalProperty('theme.color.icon', THEME['theme.color.icon'])
    kodiutil.setGlobalProperty('theme.color.setting', THEME['theme.color.setting'])
    kodiutil.setGlobalProperty('theme.color.move', THEME['theme.color.move'])
    kodiutil.setGlobalProperty('theme.color.button.selected', THEME['theme.color.button.selected'])
    kodiutil.setGlobalProperty('theme.path', THEME['theme.path'])


class ItemSettingsWindow(kodigui.BaseDialog):
    xmlFile = 'script.preshowexperience-sequence-item-settings.xml'
    path = kodiutil.ADDON_PATH
    theme = 'Main'
    res = '1080i'

    SETTINGS_LIST_ID = 300
    SLIDER_ID = 401

    def __init__(self, *args, **kwargs):
        kodigui.BaseDialog.__init__(self, *args, **kwargs)
        self.main = kwargs['main']
        self.item = kwargs['item']
        self.pos = self.item.pos()
        seqSize = self.main.sequenceControl.size() - 1
        self.leftOffset = int((self.pos + 1) / 2) - 1
        self.rightOffset = int((seqSize - (self.pos + 1)) / 2)
        self.modified = False

    def onFirstInit(self):
        self.settingsList = kodigui.ManagedControlList(self, self.SETTINGS_LIST_ID, 10)
        self.sliderControl = self.getControl(self.SLIDER_ID)
        self.fillSettingsList()
        self.updateItem()

    def fillSettingsList(self, update=False):
        sItem = self.item.dataSource

        items = []
        for i, e in enumerate(sItem._elements):
            if not sItem.elementVisible(e):
                continue
            attr = e['attr']
            name = e['name']
            if sItem._type == 'video' and attr == 'vtype' and not sItem.getSetting(attr):
                name = '[COLOR FFFF0000]{0}[/COLOR]'.format(name)

            mli = kodigui.ManagedListItem(
                name, e['limits'] != preshowexperience.sequence.LIMIT_ACTION and str(sItem.getSettingDisplay(attr)) or '', data_source=attr
            )
            mli.setProperty('name', e['name'])
            if sItem.getType(attr) == int:
                mli.setProperty('type', 'integer')
            items.append(mli)

        items.append(kodigui.ManagedListItem('[B]{0}[/B]'.format(T(32611)), data_source='@RESET@'))

        if update:
            self.settingsList.replaceItems(items)
        else:
            self.settingsList.reset()
            self.settingsList.addItems(items)

        self.setFocusId(self.SETTINGS_LIST_ID)

    def onAction(self, action):
        try:
            self.updateItem()
        except Exception:
            kodiutil.ERROR()
            kodigui.BaseDialog.onAction(self, action)
            return

        kodigui.BaseDialog.onAction(self, action)

    def onClick(self, controlID):
        if not controlID == self.SETTINGS_LIST_ID:
            return

        self.editItemSetting()

    def updateItem(self):
        item = self.settingsList.getSelectedItem()
        if not item or not item.getProperty('type') == 'integer':
            return

        sItem = self.item.dataSource
        attr = item.dataSource
        self.main.updateItemSettings(self.item)

    def getLimits(self, sItem, attr):
        limits = sItem.getLimits(attr)
        if sItem._type == 'command':
            if sItem.command == 'back' and attr not in ['nbLoops', 'duration', 'timeOfDay']:
                return (limits[0], min(limits[1], self.leftOffset), limits[2])
            elif sItem.command == 'skip' and attr not in ['nbLoops', 'duration', 'timeOfDay']:
                return (limits[0], min(limits[1], self.rightOffset), limits[2])

        return limits

    def resetToDefaults(self):
        sItem = self.item.dataSource
        sItem.resetToDefaults()
        self.modified = True
        self.main.updateItemSettings(self.item)

    def editItemSetting(self):
        self._editItemSetting()
        self.fillSettingsList(update=True)

    def _editItemSetting(self):
        contentPath = kodiutil.getPathSetting('content.path')
        item = self.settingsList.getSelectedItem()
        if not item or item.getProperty('type') == 'integer':
            return

        sItem = self.item.dataSource

        attr = item.dataSource

        if attr == '@RESET@':
            return self.resetToDefaults()

        options = sItem.getSettingOptions(attr)

        if options in (preshowexperience.sequence.LIMIT_FILE, preshowexperience.sequence.LIMIT_FILE_DEFAULT):
            select = True
            if sItem.getSetting(attr):
                yes = xbmcgui.Dialog().yesno(
                    T(32517, 'Change Path'),
                    T(32518, 'Choose a new path, or clear the current path?'),
                    T(32519, 'Choose'),
                    T(32520, 'Clear')
                )
                if yes:
                    if options == preshowexperience.sequence.LIMIT_FILE:
                        value = ''
                    else:
                        value = None
                    select = False

            if select:
                if sItem.getSetting(attr):
                    value = xbmcgui.Dialog().browse(1, T(32521, 'Select File'), '', None, False, False, sItem.getSetting(attr))
                else:
                    value = xbmcgui.Dialog().browse(1, T(32521, 'Select File'), '', None, False, False, contentPath)
                if not value:
                    return
                value = value
        elif options == preshowexperience.sequence.LIMIT_DB_CHOICE:
            options = sItem.DBChoices(attr)
            if not options:
                xbmcgui.Dialog().ok(T(32508, 'No Content'), T(32522, 'No matching content found.'))
                return False
            options.insert(0, (None, T(32322, 'Default')))
            idx = xbmcgui.Dialog().select(T(32523, 'Options'), [x[1] for x in options])
            if idx < 0:
                return False
            value = options[idx][0]
        elif options == preshowexperience.sequence.LIMIT_DIR:
            select = True
            if sItem.getSetting(attr):
                yes = xbmcgui.Dialog().yesno(
                    T(32517, 'Change Path'),
                    T(32518, 'Choose a new path or clear the current path?'),
                    T(32519, 'Choose'),
                    T(32520, 'Clear')

                )
                if yes:
                    value = None
                    select = False

            if select:
                value = xbmcgui.Dialog().browse(0, T(32524, 'Select Directory'), 'files', defaultt=contentPath)
                if not value:
                    return
                value = value
        elif options == preshowexperience.sequence.LIMIT_MULTI_SELECT:
            options = sItem.Select(attr)
            if not options:
                xbmcgui.Dialog().ok(T(32525, 'No Options'), T(32526, 'No options found.'))
                return False
            result = preshowutil.multiSelect(options)
            if result is False:
                return False
            value = result
        elif options == preshowexperience.sequence.LIMIT_BOOL_DEFAULT:
            curr = sItem.getSetting(attr)
            if curr is None:
                value = True
            elif curr is True:
                value = False
            else:
                value = None
        elif options == preshowexperience.sequence.LIMIT_BOOL:
            value = not sItem.getSetting(attr)
        elif options == preshowexperience.sequence.LIMIT_ACTION:
            if self.item.dataSource._type == 'action':
                preshowutil.evalActionFile(self.item.dataSource.file)
            return False
        elif isinstance(options, list):
            title = T(32523, 'Options')
            for elem in sItem._elements:
                if elem['attr'] == attr:
                    title = elem['name']
                    break
            idx = xbmcgui.Dialog().select(title, [x[1] for x in options])
            if idx < 0:
                return False
            value = options[idx][0]
            kodiutil.LOG('Value: {0}'.format(value))
            if isinstance(value, str) and value.isdigit():
                value = int(value)
        else:
            return False

        sItem.setSetting(attr, value)

        if sItem._type == 'video' and attr == 'vtype':
            if not sItem.getSetting(attr):
                name = '[COLOR FFFF0000]{0}[/COLOR]'.format(item.getProperty('name'))
            else:
                name = item.getProperty('name')
            item.setLabel(name)

        item.setLabel2(str(sItem.getSettingDisplay(attr)))

        self.modified = True

        self.main.updateItemSettings(self.item)

        if sItem._type == 'command' and attr == 'command':
            self.main.updateSpecials()


class SequenceEditorWindow(kodigui.BaseWindow):
    xmlFile = 'script.preshowexperience-sequence-editor.xml'
    path = kodiutil.ADDON_PATH
    theme = 'Main'
    res = '1080i'
    width = 1920
    height = 1080

    SEQUENCE_LIST_ID = 201
    ADD_ITEM_LIST_ID = 202
    ITEM_OPTIONS_LIST_ID = 203
    DUMMY_BUTTON_ID = 900

    MENU_EDIT_BUTTON_ID = 401
    MENU_PLAY_BUTTON_ID = 403
    MENU_SEQUENCE_ACTIVE_BUTTON_ID = 402
    MENU_CONDITIONS_BUTTON_ID = 404
    MENU_SHOW_OPTION_BUTTON_ID = 405

    MENU_NEW_BUTTON_ID = 411
    MENU_LOAD_BUTTON_ID = 432
    MENU_SAVE_BUTTON_ID = 433
    MENU_EDIT_SEQ_NAME_ID = 434

    MENU_IMPORT_BUTTON_ID = 421
    MENU_EXPORT_BUTTON_ID = 422
    MENU_THEME_BUTTON_ID = 424
    MENU_ADDON_SETTINGS_BUTTON_ID = 425

    def __init__(self, *args, **kwargs):
        kodigui.BaseWindow.__init__(self, *args, **kwargs)
        self.move = None
        self.modified = False
        self.setName('')
        self.path = ''
        self.sequenceData = None
        self.editing = False

    def onFirstInit(self):
        self.sequenceControl = kodigui.ManagedControlList(self, self.SEQUENCE_LIST_ID, 22)
        self.addItemControl = kodigui.ManagedControlList(self, self.ADD_ITEM_LIST_ID, 22)
        self.itemOptionsControl = kodigui.ManagedControlList(self, self.ITEM_OPTIONS_LIST_ID, 22)
        self.start()

    def onClick(self, controlID):
        if self.editing:
            if self.focusedOnItem():
                self.itemOptions()
            else:
                self.addItem()
                self.updateFocus()
        else:
            if controlID == self.MENU_EDIT_BUTTON_ID:
                self.setEditMode()
            elif 400 < controlID < 440:
                self.doMenu(controlID)

    def onAction(self, action):
        try:
            if self.editing:
                if action == xbmcgui.ACTION_PREVIOUS_MENU or action == xbmcgui.ACTION_NAV_BACK:
                    if self.move:
                        return self.cancelMove()
                    elif self.editing:
                        return self.setEditMode(False)

                if self.move:
                    if action == xbmcgui.ACTION_MOVE_LEFT:
                        pos2 = self.sequenceControl.getSelectedPosition()
                        pos1 = pos2 - 2
                        if self.sequenceControl.swapItems(pos1, pos2):
                            self.selectSequenceItem(pos1)
                        self.updateFirstLast()
                        self.updateSpecials()
                        return
                    elif action == xbmcgui.ACTION_MOVE_RIGHT:
                        pos1 = self.sequenceControl.getSelectedPosition()
                        pos2 = pos1 + 2
                        if self.sequenceControl.swapItems(pos1, pos2):
                            self.selectSequenceItem(pos2)
                        self.updateFirstLast()
                        self.updateSpecials()
                        return
                else:
                    self.updateFocus()
                    if action == xbmcgui.ACTION_MOVE_LEFT or (action == xbmcgui.ACTION_MOUSE_WHEEL_UP and self.mouseYTrans(action.getAmount2()) < 505):
                        if self.sequenceControl.size() < 2:
                            return
                        oldPos = self.sequenceControl.getSelectedPosition()
                        pos = oldPos - 1
                        if not self.sequenceControl.positionIsValid(pos):
                            pos = self.sequenceControl.size() - 1
                            self.selectSequenceItem(pos)
                        else:
                            self.selectSequenceItem(pos)
                            self.updateFocus(pos=pos)
                        self.sequenceControl.getListItem(oldPos).setProperty('selected', '0')
                    elif action == xbmcgui.ACTION_MOVE_RIGHT or (action == xbmcgui.ACTION_MOUSE_WHEEL_DOWN and self.mouseYTrans(action.getAmount2()) < 505):
                        if self.sequenceControl.size() < 2:
                            return
                        oldPos = self.sequenceControl.getSelectedPosition()
                        pos  = oldPos + 1
                        if not self.sequenceControl.positionIsValid(pos):
                            pos = 0
                            self.selectSequenceItem(pos)
                        else:
                            self.selectSequenceItem(pos)
                            self.updateFocus(pos=pos)
                        self.sequenceControl.getListItem(oldPos).setProperty('selected', '0')
                    elif action == xbmcgui.ACTION_CONTEXT_MENU:
                        self.setEditMode(False)
            else:
                if action == xbmcgui.ACTION_PREVIOUS_MENU or action == xbmcgui.ACTION_NAV_BACK:
                    if self.handleClose():
                        return

        except Exception:
            kodiutil.ERROR()

        kodigui.BaseWindow.onAction(self, action)

    def onFocus(self, controlID):
        if controlID == self.MENU_ADDON_SETTINGS_BUTTON_ID:
            kodiutil.setGlobalProperty('option.hint', '[B]Settings[/B]: Customize PreShow Experience to your needs')
        elif controlID == self.MENU_NEW_BUTTON_ID:
           kodiutil.setGlobalProperty('option.hint', '[B]New[/B]: Create a new empty sequence')
        elif controlID == self.MENU_SAVE_BUTTON_ID:
            kodiutil.setGlobalProperty('option.hint', '[B]Save[/B]: Save or export the current sequence')
        elif controlID == self.MENU_LOAD_BUTTON_ID:
            kodiutil.setGlobalProperty('option.hint', '[B]Open[/B]: Load or import a sequence')
        elif controlID == self.MENU_PLAY_BUTTON_ID:
            kodiutil.setGlobalProperty('option.hint', '[B]Play[/B]: Test the current sequence with a placeholder feature')
        elif controlID == self.MENU_THEME_BUTTON_ID:
            kodiutil.setGlobalProperty('option.hint', '[B]Icons[/B]: Change icons for the sequence editor')
        elif controlID == self.MENU_CONDITIONS_BUTTON_ID:
            kodiutil.setGlobalProperty('option.hint', '[B] Conditions[/B]: Set the conditions for auto-selecting the current sequence')
        elif controlID == self.MENU_SEQUENCE_ACTIVE_BUTTON_ID:
            kodiutil.setGlobalProperty('option.hint', '[B]Auto Select[/B]: Set whether this sequnce is active for auto-selection')
        elif controlID == self.MENU_SHOW_OPTION_BUTTON_ID:
            kodiutil.setGlobalProperty('option.hint', '[B]Show In Dialog[/B]: Set whether this sequence will be shown on the sequence selection dialog')
        elif controlID == self.MENU_EDIT_BUTTON_ID:
            kodiutil.setGlobalProperty('option.hint', '[B]Edit[/B]: Bring up the sequence editor for the current PreShow')
        elif controlID == self.MENU_EDIT_SEQ_NAME_ID:
            kodiutil.setGlobalProperty('option.hint', '[B]Name[/B]: Name or rename this sequence')

    def setEditMode(self, on=True):
        self.editing = on
        self.setProperty('editing', on and '1' or '')
        if not on:
            self.setFocusId(self.MENU_EDIT_BUTTON_ID)

    def selectSequenceItem(self, pos):
        self.sequenceControl.selectItem(pos)
        self.sequenceControl.getListItem(pos).setProperty('selected', '1')
        dataSource = self.sequenceControl[pos].dataSource
        kodiutil.setGlobalProperty('sequence.item.enabled', dataSource and dataSource.enabled and '1' or '')

    def handleClose(self):
        yes = True
        if self.modified:
            yes = xbmcgui.Dialog().yesno(
                T(32527, 'Confirm'),
                T(32528, 'Sequence was modified.  Do you really want to exit without saving changes?')
            )

        if yes:
            return False
        else:
            yes = xbmcgui.Dialog().yesno(
                'Options',
                'Would you like to save and exit or abort',
                'Abort',
                'Save and exit'
            )
            if yes:
                self.save()
                return False

        return True

    def updateFocus(self, pos=None):
        if self.focusedOnItem(pos):
            self.setFocusId(self.ITEM_OPTIONS_LIST_ID)
        else:
            self.setFocusId(self.ADD_ITEM_LIST_ID)

    def start(self):
        self.loadContent()
        self.fillOptions()
        self.fillSequence()
        self.loadDefault()
        self.setFocusId(self.MENU_EDIT_BUTTON_ID)

    def loadContent(self):
        if self.checkForContentDB() and not kodiutil.getSetting('database.autoUpdate', False):
            return

        preshowutil.loadContent()

    def checkForContentDB(self):
        if kodiutil.getPathSetting('content.path'):
            kodiutil.setGlobalProperty('DEMO_MODE', '')
            if kodiutil.getSetting('content.initialized', False) and kodiutil.getPathSetting('content.path') == kodiutil.getSetting('content.last.path'):
                return True
            else:
                kodiutil.setSetting('content.last.path', kodiutil.getPathSetting('content.path'))
                return False
        else:
            kodiutil.setGlobalProperty('DEMO_MODE', '1')
            return True

    def fillOptions(self):
        for i in preshowexperience.sequence.ITEM_TYPES:
            item = kodigui.ManagedListItem(
                '{0}: {1}'.format(T(32530, 'Add'), i[1]),
                thumbnailImage='{0}large/script.preshow-{1}.png'.format(THEME['theme.path'], i[2]),
                data_source=i[0]
            )
            item.setProperty('thumb.focus', '{0}large/script.preshow-{1}_Selected.png'.format(THEME['theme.path'], i[2]))
            self.addItemControl.addItem(item)

        basePath = THEME['theme.path'] + 'options/script.preshow-'

        item = kodigui.ManagedListItem(T(32713, 'Edit'), T(32713, 'Edit'), thumbnailImage=basePath + 'ModuleEdit.png', data_source='edit')
        item.setProperty('alt.thumb', basePath + 'ModuleEdit.png')
        item.setProperty('thumb.focus', basePath + 'Module_Selected.png')
        self.itemOptionsControl.addItem(item)

        item = kodigui.ManagedListItem(T(32707, 'Preview'), T(32707, 'Preview'), thumbnailImage=basePath + 'ModulePreview.png', data_source='preview')
        item.setProperty('alt.thumb', basePath + 'ModulePreview.png')
        item.setProperty('thumb.focus', basePath + 'Module_Selected.png')
        self.itemOptionsControl.addItem(item)
        
        item = kodigui.ManagedListItem(T(32532, 'Rename'), T(32532, 'Rename'), thumbnailImage=basePath + 'ModuleRename.png', data_source='rename')
        item.setProperty('alt.thumb', basePath + 'ModuleRename.png')
        item.setProperty('thumb.focus', basePath + 'Module_Selected.png')
        self.itemOptionsControl.addItem(item)

        item = kodigui.ManagedListItem(T(32533, 'Copy'), T(32533, 'Copy'), thumbnailImage=basePath + 'ModuleCopy.png', data_source='copy')
        item.setProperty('alt.thumb', basePath + 'ModuleCopy.png')
        item.setProperty('thumb.focus', basePath + 'Module_Selected.png')
        self.itemOptionsControl.addItem(item)

        item = kodigui.ManagedListItem(T(32534, 'Move'), T(32534, 'Move'), thumbnailImage=basePath + 'ModuleMove.png', data_source='move')
        item.setProperty('alt.thumb', basePath + 'ModuleMove.png')
        item.setProperty('thumb.focus', basePath + 'Module_Selected.png')
        self.itemOptionsControl.addItem(item)

        item = kodigui.ManagedListItem(T(32535, 'Disable'), T(32610, 'Enable'), thumbnailImage=basePath + 'ModuleEnabled.png', data_source='enable')
        item.setProperty('alt.thumb', basePath + 'ModuleDisabled.png')
        item.setProperty('thumb.focus', basePath + 'Module_Selected.png')
        self.itemOptionsControl.addItem(item)

        item = kodigui.ManagedListItem(T(32536, 'Remove'), T(32536, 'Remove'), thumbnailImage=basePath + 'ModuleRemove.png', data_source='remove')
        item.setProperty('alt.thumb', basePath + 'ModuleRemove.png')
        item.setProperty('thumb.focus', basePath + 'Module_Selected.png')
        self.itemOptionsControl.addItem(item)

    def fillSequence(self):
        mli = kodigui.ManagedListItem()

        self.sequenceControl.addItem(mli)
        # self.setFocusId(self.SEQUENCE_LIST_ID)

    def addItem(self):
        item = self.addItemControl.getSelectedItem()
        if not item:
            return

        pos = self.sequenceControl.getSelectedPosition()

        sItem = preshowexperience.sequence.getItem(item.dataSource)()

        self.insertItem(sItem, pos)

    def insertItem(self, sItem, pos, modify=True):
        mli = kodigui.ManagedListItem(sItem.display(), data_source=sItem)
        mli.setProperty('type', sItem.fileChar)
        mli.setProperty('type.name', sItem.displayName)
        mli.setProperty('enabled', sItem.enabled and '1' or '')
        mli.setProperty('theme.path', THEME['theme.path'])

        if not self.updateItemSettings(mli):
            mli.setProperty('error', '1')

        self.sequenceControl.insertItems(pos, [kodigui.ManagedListItem(), mli])

        self.updateFirstLast()

        self.modified = modify
        self.updateSpecials()

    def addItems(self, items):
        final = []
        for sItem in items:
            mli = kodigui.ManagedListItem(sItem.display(), data_source=sItem)
            mli.setProperty('type', sItem.fileChar)
            mli.setProperty('type.name', sItem.displayName)
            mli.setProperty('enabled', sItem.enabled and '1' or '')
            mli.setProperty('theme.path', THEME['theme.path'])

            if not self.updateItemSettings(mli):
                mli.setProperty('error', '1')
            final.append(mli)
            final.append(kodigui.ManagedListItem())

        self.sequenceControl.addItems(final)

        # Navigation issue if this is not done
        dummy = kodigui.ManagedListItem()
        self.sequenceControl.addItem(dummy)
        self.sequenceControl.removeItem(dummy.pos())

        self.updateFirstLast()

        self.modified = True
        self.updateSpecials()

    def updateFirstLast(self):
        for i in self.sequenceControl:
            i.setProperty('first', '')
            i.setProperty('last', '')
            i.setProperty('second', '')
            i.setProperty('almost.last', '')
        self.sequenceControl[0].setProperty('first', '1')
        self.sequenceControl[self.sequenceControl.size() - 1].setProperty('last', '1')
        if self.sequenceControl.size() > 1:
            self.sequenceControl[1].setProperty('second', '1')
            self.sequenceControl[self.sequenceControl.size() - 2].setProperty('almost.last', '1')

    def updateSpecials(self):
        skip = 0
        for i in self.sequenceControl:
            sItem = i.dataSource

            i.setProperty('connect.start', '')
            i.setProperty('connect.join', '')
            i.setProperty('connect.end', '')
            i.setProperty('connect.skip.start', '')
            i.setProperty('connect.skip.join', '')
            i.setProperty('connect.skip.end', '')

            if not sItem:
                continue

            i.setLabel(sItem.display())

            if sItem.enabled and sItem._type == 'command':
                if sItem.command == 'back':
                    pos = i.pos()
                    all = list(range(1, (sItem.arg * 2) + 1))
                    last = pos - all[-1]

                    i.setProperty('connect.end', '1')
                    prev = None

                    for x in all:
                        modPos = pos - x
                        if modPos < 0:
                            break
                        item = self.sequenceControl[modPos]
                        if not item.dataSource:
                            continue

                        if item.dataSource._type == 'command' and item.dataSource.command == 'back':
                            if prev:
                                prev.setProperty('connect.start', '1')
                                prev.setProperty('connect.join', '')
                            break

                        if modPos == 1 or modPos == last:
                            item.setProperty('connect.start', '1')
                        else:
                            item.setProperty('connect.join', '1')

                        prev = item
                elif sItem.command == 'skip':
                    skip = sItem.arg
                    i.setProperty('connect.skip.start', '1')

            if skip:
                if not i.getProperty('connect.skip.start'):
                    skip -= 1
                    if skip == 0:
                        i.setProperty('connect.skip.end', '1')
                    else:
                        i.setProperty('connect.skip.join', '1')

    def itemOptions(self):
        if self.move:
            return self.moveItem()
        item = self.itemOptionsControl.getSelectedItem()
        if not item:
            return

        if item.dataSource == 'enable':
            self.toggleItemEnabled()
        elif item.dataSource == 'remove':
            selectedItem = self.sequenceControl.getSelectedItem()
            kodiutil.DEBUG_LOG('Module Type: {0}'.format(selectedItem.dataSource._type))
            if selectedItem.dataSource._type == 'feature':
                items = [li.dataSource for li in self.sequenceControl if li.dataSource]
                if not preshowexperience.sequence.sequenceHasFeatures(items):
                    xbmcgui.Dialog().ok(T(32573, 'Failed'),T(32739, 'The preshow must have a feature module.'))
                    return
            self.removeItem()
            self.updateFocus()
        elif item.dataSource == 'copy':
            self.copyItem()
            self.updateFocus()
        elif item.dataSource == 'move':
            self.moveItem()
        elif item.dataSource == 'preview':
            self.preview()
        elif item.dataSource == 'edit':
            self.editItem()
            self.updateFocus()
        elif item.dataSource == 'rename':
            self.renameItem()

        self.updateSpecials()

    def toggleItemEnabled(self):
        item = self.sequenceControl.getSelectedItem()
        if not item:
            return

        sItem = item.dataSource
        sItem.enabled = not sItem.enabled
        item.setProperty('enabled', sItem.enabled and '1' or '')
        kodiutil.setGlobalProperty('sequence.item.enabled', item.getProperty('enabled'))
        self.updateItemSettings(item)

        self.modified = True
        
    def preview(self):
	    cpos = 1
	    pos = self.sequenceControl.getSelectedPosition()
	    last = self.sequenceControl.size()

        # Disable everything except the selected item
	    items_to_reenable = []
	    items_to_disable = []
	    while cpos < last:
	        item = self.sequenceControl.getListItem(cpos)
	        sItem = item.dataSource
	        if cpos != pos:
	            if sItem.enabled:
	                sItem.enabled = False
	                item.setProperty('enabled', '')
	                items_to_reenable.append(item)
	        else:
	            if not sItem.enabled:
	                sItem.enabled = True
	                item.setProperty('enabled', '1')
	                items_to_disable.append(item)
	        cpos += 2

	    self.test()

        # Re-enable the previously disabled items
	    for item in items_to_reenable:
	        sItem = item.dataSource
	        sItem.enabled = True
	        item.setProperty('enabled', '1')
	    # Disable the selected item if it was originally disabled 
	    for item in items_to_disable:
	        sItem = item.dataSource
	        sItem.enabled = False
	        item.setProperty('enabled', '')            
            
    def selectSequenceItem(self, pos):
        self.sequenceControl.selectItem(pos)
        self.sequenceControl.getListItem(pos).setProperty('selected', '1')
        dataSource = self.sequenceControl[pos].dataSource
        kodiutil.setGlobalProperty('sequence.item.enabled', dataSource and dataSource.enabled and '1' or '')            

    def removeItem(self):
        if not xbmcgui.Dialog().yesno(T(32527, 'Confirm'), T(32537, 'Do you really want to remove this module?')):
            return

        pos = self.sequenceControl.getSelectedPosition()
        if pos < 0:
            return
        self.sequenceControl.removeItem(pos)
        self.sequenceControl.removeItem(pos)

        self.updateFirstLast()

        self.modified = True

    def copyItem(self):
        item = self.sequenceControl.getSelectedItem()
        if not item:
            return

        sItem = item.dataSource.copy()

        self.insertItem(sItem, item.pos() + 1)

    def moveItem(self):
        if self.move:
            kodiutil.DEBUG_LOG('Move item: Finished')
            self.move.setProperty('moving', '')
            self.move = None
            self.modified = True
        else:
            kodiutil.DEBUG_LOG('Move item: Started')
            item = self.sequenceControl.getSelectedItem()
            if not item:
                return
            self.move = item
            self.move.setProperty('moving', str(self.sequenceControl.getSelectedPosition()))
            self.setFocusId(self.DUMMY_BUTTON_ID)

    def cancelMove(self):
        kodiutil.DEBUG_LOG('Move item: Canceled')

        self.setFocusId(self.ITEM_OPTIONS_LIST_ID)

        try:
            oldPos = int(self.move.getProperty('moving'))
        except:
            oldPos = -1

        pos = self.sequenceControl.getSelectedPosition()

        self.move.setProperty('moving', '')

        if oldPos > -1 and oldPos != pos:
            if oldPos < pos:
                self.insertItem(self.move.dataSource, oldPos - 1, modify=False)
                self.sequenceControl.removeItem(pos + 1)
                self.sequenceControl.removeItem(pos + 1)
            elif oldPos > pos:
                self.insertItem(self.move.dataSource, oldPos + 1, modify=False)
                self.sequenceControl.removeItem(pos - 1)
                self.sequenceControl.removeItem(pos - 1)

            self.updateFirstLast()
            self.updateSpecials()

            self.selectSequenceItem(oldPos)

        self.move = None

    def editItem(self):
        item = self.sequenceControl.getSelectedItem()
        if not item:
            return
        isw = ItemSettingsWindow.open(main=self, item=item)
        self.modified = self.modified or isw.modified
        del isw

        self.updateItemSettings(item)

    def updateItemSettings(self, item):
        sItem = item.dataSource

        ct = 0

        error = False
        for e in sItem._elements:
            if not sItem.elementVisible(e):
                continue

            if e['limits'] == preshowexperience.sequence.LIMIT_ACTION:
                continue

            name = e['name']
            if sItem._type == 'video' and e['attr'] == 'vtype' and not sItem.getSetting(e['attr']):
                error = True
                name = '[COLOR FFFF0000]{0}[/COLOR]'.format(name)

            disp = sItem.getSettingDisplay(e['attr'])
            item.setProperty('setting{0}'.format(ct), disp)
            item.setProperty('setting{0}_name'.format(ct), name)
            ct += 1
        for i in range(ct, 8):
            item.setProperty('setting{0}'.format(i), '')
            item.setProperty('setting{0}_name'.format(i), '')

        item.setProperty('error', error and '1' or '')

        return not error

    def renameItem(self):
        item = self.sequenceControl.getSelectedItem()
        if not item:
            return

        sItem = item.dataSource

        name = xbmcgui.Dialog().input(T(32539, 'Enter a name for this item'), sItem.name)

        if name == sItem.name:
            return

        sItem.name = name or ''

        self.modified = True

    def focusedOnItem(self, pos=None):
        if pos is not None:
            item = self.sequenceControl[pos]
        else:
            item = self.sequenceControl.getSelectedItem()
        return bool(item.dataSource)

    def doMenu(self, controlID):
        if controlID == self.MENU_ADDON_SETTINGS_BUTTON_ID:
            self.settings()
        elif controlID == self.MENU_NEW_BUTTON_ID:
            self.new()
        elif controlID == self.MENU_SAVE_BUTTON_ID:
            self.saveMenu()
        elif controlID == self.MENU_LOAD_BUTTON_ID:
            self.loadMenu()
        elif controlID == self.MENU_PLAY_BUTTON_ID:
            self.test()
        elif controlID == self.MENU_THEME_BUTTON_ID:
            self.themeMenu()
        elif controlID == self.MENU_CONDITIONS_BUTTON_ID:
            self.setAttributes()
        elif controlID == self.MENU_SEQUENCE_ACTIVE_BUTTON_ID:
            if self.sequenceData is None:
                xbmcgui.Dialog().ok(T(32747, 'Save Required'),T(32748, 'This setting can only be changed after the sequence has been saved.'))
            else:
                val = not self.sequenceData.active
                self.sequenceData.active = val
                kodiutil.setGlobalProperty('ACTIVE', self.sequenceData.active and '1' or '0')
                self.modified = True
        elif controlID == self.MENU_SHOW_OPTION_BUTTON_ID:
            if self.sequenceData is None:
                xbmcgui.Dialog().ok(T(32747, 'Save Required'),T(32748, 'This setting can only be changed after the sequence has been saved.'))
            else:        
                self.sequenceData.visibleInDialog(not self.sequenceData.visibleInDialog())
                kodiutil.setGlobalProperty('sequence.visible.dialog', self.sequenceData.visibleInDialog() and "1" or "")
                self.modified = True
        elif controlID == self.MENU_EDIT_SEQ_NAME_ID:
            name = xbmcgui.Dialog().input(T(32616, 'Rename current sequence'), self.sequenceData.name)
            if not name:
                return
            self.sequenceData.name = pathName
            self.setName(pathName)
            self.modified = True


    def loadMenu(self):
        options = [('load', 'Load'), ('import', 'Import')]

        idx = xbmcgui.Dialog().select('Load Options', [x[1] for x in options])
        if idx < 0:
            return

        choice = options[idx][0]

        if choice == 'load':
            self.load()
        elif choice == 'import':
            self.load(import_=True)

    def saveMenu(self):
        options = [('save', 'Save'), ('saveas', 'Save as...'), ('export', 'Export')]

        idx = xbmcgui.Dialog().select('Save Options', [x[1] for x in options])
        if idx < 0:
            return

        choice = options[idx][0]

        if choice == 'save':
            self.save()
        elif choice == 'saveas':
            self.save(as_new=True)
        elif choice == 'export':
            self.save(export=True)

    def themeMenu(self):
        themes = sorted(self.getThemes(os.path.join(kodiutil.ADDON_PATH, 'resources', 'themes')), key=lambda x: x["theme.path"])
        if kodiutil.getPathSetting('content.path'):
            themes += self.getThemes()

        idx = xbmcgui.Dialog().select('Choose Theme', [x['theme.name'] for x in themes])
        if idx < 0:
            return False

        setTheme(themes[idx]['theme.path'])

        for mli in self.sequenceControl:
            if mli.getProperty('theme.path'):
                mli.setProperty('theme.path', THEME['theme.path'])

        self.itemOptionsControl.reset()
        self.addItemControl.reset()
        self.fillOptions()

    def getThemes(self, themes_path=None):
        themesPath = themes_path or preshowexperience.util.pathJoin(kodiutil.getPathSetting('content.path'), 'Themes')
        themePaths = [preshowexperience.util.pathJoin(themesPath, p) for p in preshowexperience.util.vfs.listdir(themesPath)]

        themes = []
        for tp in themePaths:
            cfg = preshowexperience.util.pathJoin(tp, 'theme.json')
            try:
                with preshowexperience.util.vfs.File(cfg, 'r') as f:
                    themeInfo = json.loads(f.read())
                    themeInfo['theme.path'] = tp + '/'
                themes.append(themeInfo)
            except Exception:
                kodiutil.ERROR('Failed to load: {0}'.format(kodiutil.strRepr(cfg)))

        return themes

    def settings(self):
        kodiutil.ADDON.openSettings()

        kodiutil.setScope()
        preshowexperience.init(kodiutil.DEBUG())

        for item in self.sequenceControl:
            if item.dataSource:
                self.updateItemSettings(item)

        if not self.checkForContentDB():
            preshowutil.loadContent()

    def test(self):
        from . import experience

        os.environ['isTestOrPreview'] = 'True'
        savePath = os.path.join(kodiutil.PROFILE_PATH, 'temp.seq')
        self._save(savePath, temp=True)

        e = experience.ExperiencePlayer().create(from_editor=True)
        e.start(savePath)   

    def setAttributes(self):
        self.modified = seqattreditor.setAttributes(self.sequenceData) or self.modified

    def abortOnModified(self):
        if self.modified:
            if not xbmcgui.Dialog().yesno(
                T(32527, 'Confirm'),
                T(32549, 'Sequence has been modified.  This will delete all changes.  Do you really want to do this?')
            ):
                return True
        return False

    def new(self):
        if self.abortOnModified():
            return

        self.sequenceData = preshowexperience.sequence.SequenceData()
        self.setName('')
        kodiutil.setGlobalProperty('ACTIVE', self.sequenceData.active and '1' or '0')
        kodiutil.setGlobalProperty('sequence.visible.dialog', self.sequenceData.visibleInDialog() and "1" or "")
        self.sequenceControl.reset()
        self.fillSequence()                                                     
        new_feature = preshowexperience.sequence.getItem('Feature')()
        new_feature.type = 'Feature'  
        new_feature.typeName = 'Feature'  
        new_feature.enabled = True  
        self.insertItem(new_feature, 0, modify=False)
        self.updateFirstLast()
        self.updateSpecials()
        
    def savePath(self, path=None, pathName=None):
        if pathName is None and self.sequenceData is not None:
            pathName = self.sequenceData.pathName

        if not path:
            contentPath = kodiutil.getPathSetting('content.path')
            if not contentPath:
                return

            path = preshowexperience.util.pathJoin(contentPath, 'Sequences')

        if not pathName or not path:
            return None         
        return preshowexperience.util.pathJoin(path, pathName) + '.seq'

    def setName(self, name):
        self.name = os.path.splitext(name)[0]
        kodiutil.setGlobalProperty('EDITING', self.name)

    def defaultSavePath(self):
        return preshowutil.defaultSavePath()

    def save(self, as_new=False, export=False):
        if export:
            path = xbmcgui.Dialog().browse(3, T(32552, 'Select Save Directory'), 'files', None, False, False)
            if not path:
                return
        else:
            contentPath = kodiutil.getPathSetting('content.path')
            if not contentPath:
                xbmcgui.Dialog().ok(T(32503, 'No Content Path'), T(32553, 'Please set the content path in addon settings.'))
                return

            path = preshowexperience.util.pathJoin(contentPath, 'Sequences')

        pathName = self.sequenceData.name

        if not pathName or as_new or export:
            pathName = xbmcgui.Dialog().input(T(32554, 'Enter name for file'), self.sequenceData.name)
            if not pathName:
                return

        fullPath = self.savePath(path, pathName)
        self.sequenceData.name = pathName
        kodiutil.DEBUG_LOG('Path Name: {0}'.format(pathName))
        self.setName(pathName)
        self._save(fullPath, temp=export)

    def _save(self, full_path, temp=False):
        items = [li.dataSource for li in self.sequenceControl if li.dataSource]

        if not preshowexperience.sequence.sequenceHasFeature(items):
            yes = xbmcgui.Dialog().yesno(
                T(32561, 'No Feature'),
                T(32561, 'Sequence does not have a feature module, which is required to play items selected in Kodi.  Do you wish to continue?')
            )
            if not yes:
                return

        self.sequenceData.setItems(items)

        kodiutil.DEBUG_LOG('Saving to: {0}'.format(full_path))
        saveName = self.sequenceData.name
        kodiutil.setSetting('save.path', self.path)
        kodiutil.setSetting('save.path.name', saveName)

        try:
            success = self.sequenceData.save(full_path)
        except preshowexperience.exceptions.SequenceWriteReadEmptyException:
            xbmcgui.Dialog().ok(
                T(32573, 'Failed'),
                'Failed to verify sequence file after write!  Kodi may be unable to save to this location.'
            )
            return
        except preshowexperience.exceptions.SequenceWriteReadBadException:
            xbmcgui.Dialog().ok(
                T(32573, 'Failed'),
                'Bad sequence file verification after write!  The sequence file seems to have been corrupted when saving.'
            )
            return
        except preshowexperience.exceptions.SequenceWriteReadUnknownException:
            xbmcgui.Dialog().ok(
                T(32573, 'Failed'),
                'Unknown error when verifying sequence file after write!  The sequence file may not have been saved.'
            )
            return
        if not success:
            xbmcgui.Dialog().ok(
                T(32573, 'Failed'),
                T(32606, 'Failed to write sequence file!  Kodi may be unable to save to this location.')
            )
            return
        
        if not temp:
            self.modified = False
            self.setName(self.sequenceData.name)
            self.saveDefault()

    def _savePreview(self, full_path, temp=False):
        items = [li.dataSource for li in self.sequenceControl if li.dataSource]
        kodiutil.DEBUG_LOG('Items:')
        kodiutil.DEBUG_LOG(items)
        if not preshowexperience.sequence.sequenceHasFeature(items):
            yes = xbmcgui.Dialog().yesno(
                T(32603, 'No Feature'),
                T(32604, 'Sequence does not have a feature module, which is required to play items selected in Kodi.  Do you wish to continue?')
            )
            if not yes:
                return

        self.sequenceData.setItems(items)

        kodiutil.DEBUG_LOG('Saving to: {0}'.format(full_path))
        saveName = self.sequenceData.name
        kodiutil.setSetting('save.path', self.path)
        kodiutil.setSetting('save.path.name', saveName)

        try:
            success = self.sequenceData.save(full_path)
        except preshowexperience.exceptions.SequenceWriteReadEmptyException:
            xbmcgui.Dialog().ok(
                T(32573, 'Failed'),
                'Failed to verify sequence file after write!  Kodi may be unable to save to this location.'
            )
            return
        except preshowexperience.exceptions.SequenceWriteReadBadException:
            xbmcgui.Dialog().ok(
                T(32573, 'Failed'),
                'Bad sequence file verification after write!  The sequence file seems to have been corrupted when saving.'
            )
            return
        except preshowexperience.exceptions.SequenceWriteReadUnknownException:
            xbmcgui.Dialog().ok(
                T(32573, 'Failed'),
                'Unknown error when verifying sequence file after write!  The sequence file may not have been saved.'
            )
            return
        if not success:
            xbmcgui.Dialog().ok(
                T(32573, 'Failed'),
                T(32606, 'Failed to write sequence file!  Kodi may be unable to save to this location.')
            )
            return
        
        if not temp:
            self.modified = False
            self.setName(self.sequenceData.name)
            self.saveDefault()
            
    def load(self, import_=False):
        if self.abortOnModified():
            return

        if import_:
            path = xbmcgui.Dialog().browse(1, T(32521, 'Select File'), 'files', '*.seq|*.pseseq|*.cvseq', False, False)
            if not path:
                return
        else:
            selection = preshowutil.selectSequence(active=False)

            if not selection:
                return

            path = selection['path']
            kodiutil.DEBUG_LOG('Sequence Selected: {0}'.format(path))

        self._load(path)

        sep = preshowexperience.util.getSep(path)

        self.path, pathName = path.rsplit(sep, 1)
        self.path += sep
        self.setName(self.sequenceData.pathName)
        self.saveDefault()

    def _load(self, path):
        try:
            sData = preshowexperience.sequence.SequenceData.load(path)
        except preshowexperience.exceptions.EmptySequenceFileException:
            xbmcgui.Dialog().ok(
                T(32573, 'Failed'),
                'Failed to read sequence file!',
                'Kodi may be unable to read from this location.'
            )
            return
        except preshowexperience.exceptions.BadSequenceFileException:
            xbmcgui.Dialog().ok(
                T(32573, 'Failed'),
                'Failed to read sequence file!  The sequence file may have been corrupted.'
            )
            return
        except:
            kodiutil.ERROR()
            xbmcgui.Dialog().ok(
                T(32573, 'Failed'),
                'Failed to read sequence file!  There was an unknown error. See kodi.log for details.'
            )
            return

        if not sData:
            xbmcgui.Dialog().ok(T(32601, 'ERROR'), T(32602, 'Error parsing sequence'))
            return

        self.sequenceControl.reset()
        self.fillSequence()

        self.sequenceData = sData
        kodiutil.setGlobalProperty('ACTIVE', self.sequenceData.active and '1' or '0')
        kodiutil.setGlobalProperty('sequence.visible.dialog', self.sequenceData.visibleInDialog() and "1" or "")
        self.addItems(sData)

        if self.sequenceControl.positionIsValid(1):
            self.selectSequenceItem(1)
        else:
            self.selectSequenceItem(0)

        self.modified = False

    def saveDefault(self, force=True):
        if (self.sequenceData is None or not self.path) and not force:
            return

        savePathName = ''
        if self.sequenceData is not None:
            savePathName = self.sequenceData.pathName

        kodiutil.setSetting('save.path', self.path)
        if not savePathName:
            savePath = self.defaultSavePath()
        else:
            kodiutil.setSetting('save.path.name', self.sequenceData.name)

    def loadDefault(self):
        savePathName = kodiutil.getSetting('save.path.name', '')

        if not savePathName:
            savePath = self.defaultSavePath()
        else:
            savePath = self.savePath(pathName=savePathName)
            if not xbmcvfs.exists(savePath):
                self.setName('')
                self.saveDefault(force=True)
                new = xbmcgui.Dialog().yesno(
                    T(32558, 'Missing'),
                    T(32559, 'Previous save not found.  Load the default or start a new sequence?'),
                    T(32322, 'Default'),
                    T(32541, 'New')
                )
                if new:
                    self.setName('')
                    self.new()
                    return
                else:
                    savePath = self.defaultSavePath()

        kodiutil.DEBUG_LOG('Loading previous save: {0}'.format(savePath))

        self._load(savePath)
        self.setName(self.sequenceData.pathName)

        kodiutil.DEBUG_LOG('Previous save loaded')


def main():
    setTheme()
    kodiutil.setScope()
    kodiutil.setGlobalProperty('VERSION', kodiutil.ADDON.getAddonInfo('version'))
    kodiutil.setGlobalProperty('option.hint', '')
    kodiutil.LOG('Sequence editor: OPENING')
    w = SequenceEditorWindow.open()
    del w
    kodiutil.LOG('Sequence editor: CLOSED')
