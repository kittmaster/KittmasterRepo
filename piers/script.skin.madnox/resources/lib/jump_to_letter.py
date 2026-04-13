# coding: utf-8
# resources/lib/jump_to_letter.py
#
# Replicates script.embuary.helper's smsjump logic as a native
# Madnox helper module. Called via:
#   RunScript(script.skin.madnox, action=smsjump, letter=A)
#
# The XML jump bar panel (container id 61500 vertical / 61600 horizontal)
# is populated by Kodi's native JumpToLetter infolabels — no plugin
# container needed. This script only handles the CLICK action when a
# letter button is pressed.

import xbmc
import xbmcgui


# SMS key map: letter -> jumpsms action name
_SMS_MAP = {
    'A': 'jumpsms2', 'B': 'jumpsms2', 'C': 'jumpsms2',
    'D': 'jumpsms3', 'E': 'jumpsms3', 'F': 'jumpsms3',
    'G': 'jumpsms4', 'H': 'jumpsms4', 'I': 'jumpsms4',
    'J': 'jumpsms5', 'K': 'jumpsms5', 'L': 'jumpsms5',
    'M': 'jumpsms6', 'N': 'jumpsms6', 'O': 'jumpsms6',
    'P': 'jumpsms7', 'Q': 'jumpsms7', 'R': 'jumpsms7', 'S': 'jumpsms7',
    'T': 'jumpsms8', 'U': 'jumpsms8', 'V': 'jumpsms8',
    'W': 'jumpsms9', 'X': 'jumpsms9', 'Y': 'jumpsms9', 'Z': 'jumpsms9',
}

# Container IDs to try to focus for the jump action.
# Matches all container IDs used in NewJumpbarVertical / NewJumpbarHorizontal
# onleft/onright targets. Order matters — first one that is visible wins.
_CONTAINER_IDS = [50, 51, 53, 54, 55, 57, 58, 541]


def _get_active_container():
    """Return the first visible container ID from the known list, else 50."""
    for cid in _CONTAINER_IDS:
        if xbmc.getCondVisibility('Control.IsVisible(%d)' % cid):
            return cid
    return 50


def run(params):
    """
    Entry point called by default.py router:
        RunScript(script.skin.madnox, action=smsjump, letter=X)

    params dict keys:
        letter  - single character A-Z, #, or 0-9
    """
    letter = params.get('letter', '').strip().upper()

    if not letter:
        xbmc.log('[script.skin.madnox] smsjump: no letter param', xbmc.LOGWARNING)
        return

    container_id = _get_active_container()

    # ------------------------------------------------------------------ #
    # Case 1: Number / # symbol → jump to first or last page              #
    # ------------------------------------------------------------------ #
    if letter in ('#', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9'):
        # Descending sort → lastpage puts numbers at end; ascending → firstpage
        if xbmc.getInfoLabel('Container.SortOrder') == 'Descending':
            jumpcmd = 'lastpage'
        else:
            jumpcmd = 'firstpage'

        xbmc.executebuiltin('SetFocus(%d)' % container_id)
        xbmc.executeJSONRPC(
            '{"jsonrpc":"2.0","method":"Input.ExecuteAction",'
            '"params":{"action":"%s"},"id":1}' % jumpcmd
        )
        return

    # ------------------------------------------------------------------ #
    # Case 2: Standard letter A-Z                                         #
    # ------------------------------------------------------------------ #
    jumpcmd = _SMS_MAP.get(letter)
    if jumpcmd is None:
        xbmc.log('[script.skin.madnox] smsjump: unknown letter "%s"' % letter, xbmc.LOGWARNING)
        return

    # Focus the container first so jumpsms actions land on the right list
    xbmc.executebuiltin('SetFocus(%d)' % container_id)

    # Loop up to 40 iterations × 50 ms = 2 s max, matching embuary's timing.
    # Each iteration fires the sms action and checks whether the current
    # ListItem.SortLetter has reached the target.
    for _ in range(40):
        xbmc.executeJSONRPC(
            '{"jsonrpc":"2.0","method":"Input.ExecuteAction",'
            '"params":{"action":"%s"},"id":1}' % jumpcmd
        )
        xbmc.sleep(50)

        current = xbmc.getInfoLabel('ListItem.SortLetter').upper()
        if current == letter:
            break
