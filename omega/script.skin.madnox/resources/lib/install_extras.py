import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
import xml.etree.ElementTree as ET

ADDON = xbmcaddon.Addon('script.skin.madnox')

REPO_SOURCES = [
    ('lynxstrike.repo',         'https://lynxstrike.github.io/lynxstrike.repo/'),
    ('repository.jurialmunkey', 'https://jurialmunkey.github.io/repository.jurialmunkey/'),
]

OPTIONAL_EXTRAS = [
    ('script.cu.lrclyrics',                              'LRC Lyrics'),
    ('service.upnext',                                   'Up Next'),
    ('script.artistslideshow',                           'Artist Slideshow'),
    ('script.rss.editor',                                'RSS Editor'),
    ('plugin.library.node.editor',                       'Library Node Editor'),
    ('resource.images.weathericons.3d-coloured',         'Weather Icons (3D)'),
    ('resource.images.weatherfanart.multi',              'Weather Fanart'),
    ('resource.images.studios.white',                    'Studio Icons (White)'),
    ('resource.images.studios.coloured',                 'Studio Icons (Colour)'),
    ('resource.images.recordlabels.white',               'Record Labels'),
    ('resource.images.languageflags.rounded',            'Language Flags'),
    ('resource.images.musicgenreicons.text',             'Music Genre Icons'),
    ('resource.images.moviecountryicons.flags',          'Country Icons'),
    ('script.artwork.dump',                              'Artwork Dump'),
    ('service.tvtunes',                                  'TV Tunes'),
    ('script.wikipedia',                                 'Wikipedia'),
    ('script.preshowexperience',                         'Preshow Experience'),
    ('resource.images.moviegenreicons.filmstrip-hd.bw',      'Movie Genre Icons (B&W)'),
    ('resource.images.moviegenreicons.filmstrip-hd.colour',  'Movie Genre Icons (Colour)'),
    ('script.trakt',                                     'Trakt'),
]


def _set_addon_enabled(addon_id, enabled):
    xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "Addons.SetAddonEnabled",
        "params": {"addonid": addon_id, "enabled": enabled},
        "id": 1
    }))


def _indent_xml(elem, level=0):
    """Fallback XML indentation for Python versions older than 3.9"""
    i = "\n" + level * "    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            _indent_xml(child, level + 1)
        
        last_child = elem[-1]
        if not last_child.tail or not last_child.tail.strip():
            last_child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def _inject_repo_sources():
    """Returns the number of sources successfully injected."""
    sources_path = 'special://userdata/sources.xml'
    raw = ""

    try:
        if xbmcvfs.exists(sources_path):
            with xbmcvfs.File(sources_path, 'r') as fh:
                raw = fh.read()
    except Exception as exc:
        xbmc.log(f'[Madnox] Could not read sources.xml: {exc}', xbmc.LOGERROR)
        return 0

    if not raw or not raw.strip():
        root = ET.Element('sources')
    else:
        try:
            root = ET.fromstring(raw)
            if root is None:
                return 0
        except ET.ParseError as exc:
            xbmc.log(f'[Madnox] sources.xml parse error: {exc}', xbmc.LOGERROR)
            return 0

    files_node = root.find('files')
    if files_node is None:
        files_node = ET.SubElement(root, 'files')
        default_el = ET.SubElement(files_node, 'default')
        default_el.set('pathversion', '1')

    existing_paths = {
        src.findtext('path', '').rstrip('/')
        for src in files_node.findall('source')
    }

    injected = 0
    for name, url in REPO_SOURCES:
        if url.rstrip('/') in existing_paths:
            xbmc.log(f'[Madnox] Repo already present, skipping: {name}', xbmc.LOGDEBUG)
            continue

        source_el = ET.SubElement(files_node, 'source')
        ET.SubElement(source_el, 'name').text          = name
        path_el = ET.SubElement(source_el, 'path')
        path_el.text                                   = url
        path_el.set('pathversion', '1')
        ET.SubElement(source_el, 'allowsharing').text  = 'true'

        xbmc.log(f'[Madnox] Injected repo source: {name}', xbmc.LOGINFO)
        injected += 1

    if injected == 0:
        return 0

    if hasattr(ET, 'indent'):
        ET.indent(root, space='    ')
    else:
        _indent_xml(root)

    xml_str = ET.tostring(root, encoding='unicode')
    xml_out = '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n' + xml_str

    try:
        with xbmcvfs.File(sources_path, 'w') as fh:
            fh.write(xml_out)
        xbmc.log(f'[Madnox] sources.xml updated with {injected} new repo(s)', xbmc.LOGINFO)
        return injected
    except Exception as exc:
        xbmc.log(f'[Madnox] Could not write sources.xml: {exc}', xbmc.LOGERROR)
        return 0


def run():
    xbmc.sleep(2000)

    dialog = xbmcgui.Dialog()

    if not dialog.yesno(
        'Madnox — Optional Extras',
        'Download optional extras in the background?\n\n'
        '[B]Flags, studio icons, genre art, lyrics, TV tunes[/B] and more.\n\n'
        'Everything installs [B]disabled[/B] — enable only what you want\n'
        'in [I]Settings › Addons › My Addons[/I].'
    ):
        xbmc.executebuiltin('Skin.SetBool(madnox.extrasinstalled)')
        return

    # Inject repos and capture how many were added
    injected_count = _inject_repo_sources()

    progress = xbmcgui.DialogProgress()
    progress.create('Madnox Setup', 'Preparing optional extras...')

    total = len(OPTIONAL_EXTRAS)
    for i, (addon_id, label) in enumerate(OPTIONAL_EXTRAS):
        if progress.iscanceled():
            break

        pct = int((i / total) * 100)
        current_num = i + 1
        
        # Display multiline text on the progress bar
        status_text = f'Installing {current_num} of {total}\n[B]{label}[/B]'
        progress.update(pct, status_text)

        if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
            continue

        xbmc.executebuiltin(f'InstallAddon({addon_id})', False)

        elapsed = 0
        timeout_ms = 45000

        while elapsed < timeout_ms:
            if progress.iscanceled():
                break

            if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
                break

            if xbmc.getCondVisibility('Window.IsActive(dialogconfirm)'):
                xbmc.executebuiltin('SendClick(1301, 11)')

            if xbmc.getCondVisibility('Window.IsActive(yesnodialog)'):
                xbmc.executebuiltin('SendClick(1300, 11)')

            xbmc.sleep(250)
            elapsed += 250

        xbmc.sleep(1000)

        if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
            _set_addon_enabled(addon_id, False)

    progress.update(100, 'Done!')
    xbmc.sleep(800)
    progress.close()

    xbmc.executebuiltin('Skin.SetBool(madnox.extrasinstalled)')

    # Check if we need to offer a full application close
    if injected_count > 0:
        do_close = dialog.yesno(
            'Madnox Setup',
            'Optional extras installed and [B]disabled[/B].\n'
            'Enable what you want in [I]Settings › Addons › My Addons[/I].\n\n'
            '[COLOR yellow]Kodi must be restarted to show the new Repos in the File Manager.[/COLOR]\n\n'
            'Close Kodi now?'
        )
        if do_close:
            xbmc.executebuiltin('Quit')
    else:
        dialog.ok(
            'Madnox Setup',
            'Optional extras installed and [B]disabled[/B].\n\n'
            'Enable what you want in [I]Settings › Addons › My Addons[/I].'
        )