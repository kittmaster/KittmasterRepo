import xbmc
import xbmcgui

LOG_TAG = "[MadnoxWidgetLabel]"


def _log(msg):
    xbmc.log("{} {}".format(LOG_TAG, msg), xbmc.LOGINFO)


def _flag_set():
    return xbmc.getCondVisibility(
        "!String.IsEmpty(Window(Home).Property(widgetTitlePrompt))"
    )


def _in_widget_settings():
    return xbmc.getCondVisibility(
        "!String.IsEmpty(Window(Home).Property(skinshortcuts-dialog))"
    )


def run(params):
    slot = params.get("slot", "1")
    monitor = xbmc.Monitor()

    # Record the dialog stack depth BEFORE picker opens.
    # script-skinshortcuts is itself a dialog, so baseline is already non-zero.
    baseline_id = xbmcgui.getCurrentWindowDialogId()
    _log("=== run() slot={} baseline_dialog_id={} flag_set={} in_widget_settings={} ===".format(
        slot, baseline_id, _flag_set(), _in_widget_settings()
    ))

    # Phase 1: wait for picker to push a NEW dialog on top (ID changes from baseline)
    _log("Phase 1: waiting for picker to open (dialog ID change from {})...".format(baseline_id))
    picker_detected = False
    for i in range(100):
        if monitor.waitForAbort(0.1):
            _log("Abort in Phase 1 at iteration {}".format(i))
            return
        if not _flag_set():
            _log("Phase 1: flag cleared at iteration {} — mouse-over handled it".format(i))
            return
        current_id = xbmcgui.getCurrentWindowDialogId()
        if current_id != baseline_id:
            picker_detected = True
            _log("Phase 1: picker detected at iteration {} — dialog_id={} (was {})".format(
                i, current_id, baseline_id
            ))
            break

    if not picker_detected:
        _log("Phase 1: picker NOT detected after 10s — dialog_id stayed at {}. Trying fallback.".format(baseline_id))
        if monitor.waitForAbort(2.0):
            _log("Abort during fallback wait")
            return
        if _flag_set() and _in_widget_settings():
            _log("Fallback: firing SendClick(820{})".format(slot))
            xbmc.executebuiltin("ClearProperty(widgetTitlePrompt,Home)")
            if monitor.waitForAbort(0.1):
                return
            xbmc.executebuiltin("SendClick(820{})".format(slot))
        else:
            _log("Fallback: flag or settings gone — aborting. flag_set={} in_widget_settings={}".format(
                _flag_set(), _in_widget_settings()
            ))
        return

    # Phase 2: wait for picker to close (dialog ID returns to baseline)
    _log("Phase 2: picker open, waiting for dialog_id to return to {}...".format(baseline_id))
    for i in range(1200):
        if monitor.waitForAbort(0.1):
            _log("Abort in Phase 2 at iteration {}".format(i))
            return
        if not _flag_set():
            _log("Phase 2: flag cleared at iteration {} — mouse-over handled it".format(i))
            return
        if not _in_widget_settings():
            _log("Phase 2: left widget settings at iteration {} — aborting".format(i))
            return
        current_id = xbmcgui.getCurrentWindowDialogId()
        if current_id == baseline_id:
            _log("Phase 2: picker closed at iteration {} — dialog_id back to {}".format(i, baseline_id))
            break
        if i % 20 == 0:
            _log("Phase 2: still waiting at iteration {}, dialog_id={}".format(i, current_id))
    else:
        _log("Phase 2: timed out after 120s")
        return

    # Phase 3: settle, check result, auto-write artwork, then fire keyboard
    _log("Phase 3: settling 400ms...")
    if monitor.waitForAbort(0.4):
        _log("Abort during settle")
        return

    _log("Phase 3: flag_set={} in_widget_settings={}".format(_flag_set(), _in_widget_settings()))
    if _flag_set() and _in_widget_settings():
        # Check whether the user selected None (clear) or cancelled the picker.
        # widgetType.N == "none" means no widget is assigned — keyboard is irrelevant.
        wtype = xbmc.getInfoLabel(
            "Container(211).ListItem.Property(widgetType.{})".format(slot)
        )
        _log("Phase 3: widgetType.{}='{}'".format(slot, wtype))
        if not wtype or wtype == "none":
            _log("Phase 3: slot cleared or picker cancelled — not firing keyboard")
            xbmc.executebuiltin("ClearProperty(widgetTitlePrompt,Home)")
            return

        _log("Phase 3: firing ClearProperty + SendClick(820{})".format(slot))
        xbmc.executebuiltin("ClearProperty(widgetTitlePrompt,Home)")
        if monitor.waitForAbort(0.1):
            return
        xbmc.executebuiltin("SendClick(820{})".format(slot))
        _log("Phase 3: done")
    else:
        _log("Phase 3: flag or settings gone — not firing")
