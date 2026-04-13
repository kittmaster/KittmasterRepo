import xbmc
import xbmcgui
import xbmcaddon
import json

ADDON = xbmcaddon.Addon('script.skin.madnox')

# (addon_id, friendly_label)
OPTIONAL_EXTRAS = [
    ('script.cu.lrclyrics',                                 'LRC Lyrics'),
    ('service.upnext',                                      'Up Next'),
    ('script.artistslideshow',                              'Artist Slideshow'),
    ('script.rss.editor',                                   'RSS Editor'),
    ('plugin.library.node.editor',                          'Library Node Editor'),
    ('resource.images.weathericons.3d-coloured',            'Weather Icons (3D)'),
    ('resource.images.weatherfanart.multi',                 'Weather Fanart'),
    ('resource.images.studios.white',                       'Studio Icons (White)'),
    ('resource.images.studios.coloured',                    'Studio Icons (Colour)'),
    ('resource.images.recordlabels.white',                  'Record Labels'),
    ('resource.images.languageflags.rounded',               'Language Flags'),
    ('resource.images.musicgenreicons.text',                'Music Genre Icons'),
    ('resource.images.moviecountryicons.flags',             'Country Icons'),
    ('script.artwork.dump',                                 'Artwork Dump'),
    ('service.tvtunes',                                     'TV Tunes'),
    ('script.wikipedia',                                    'Wikipedia'),
    ('script.preshowexperience',                            'Preshow Experience'),
    ('resource.images.moviegenreicons.filmstrip-hd.bw',     'Movie Genre Icons (B&W)'),
    ('resource.images.moviegenreicons.filmstrip-hd.colour', 'Movie Genre Icons (Colour)'),
    ('script.trakt',                                        'Trakt'),
]

def _set_addon_enabled(addon_id, enabled):
    xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "Addons.SetAddonEnabled",
        "params": {"addonid": addon_id, "enabled": enabled},
        "id": 1
    }))

def run():
    # Delay for 2 seconds to let the Home Screen fully build and settle.
    xbmc.sleep(2000)

    dialog = xbmcgui.Dialog()

    if not dialog.yesno(
        'Madnox — Optional Extras',
        'Download optional extras in the background?\n\n'
        '[B]Flags, studio icons, genre art, lyrics, TV tunes[/B] and more.\n\n'
        'Everything installs [B]disabled[/B] — enable only what you want\n'
        'in [I]Settings > Skin Settings > Addons[/I].'
    ):
        xbmc.executebuiltin('Skin.SetBool(madnox.extrasinstalled)')
        return

    progress = xbmcgui.DialogProgress()
    progress.create('Madnox Setup', 'Preparing optional extras...')

    total = len(OPTIONAL_EXTRAS)
    for i, (addon_id, label) in enumerate(OPTIONAL_EXTRAS):
        if progress.iscanceled():
            break

        pct = int((i / total) * 100)
        progress.update(pct, f'Wait For Closing Dialog - Installing: [B]{label}[/B]')

        if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
            continue

        xbmc.executebuiltin(f'InstallAddon({addon_id})', False)

        # Polling Loop
        elapsed = 0
        timeout_ms = 45000
        
        while elapsed < timeout_ms:
            if progress.iscanceled():
                break
                
            if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
                break
            
            # --- THE BYPASS (FIXED) ---
            # We MUST use string names (dialogconfirm, yesnodialog) for visibility checks.
            # 1301 is DialogConfirm, 1300 is DialogYesNo
            # Button 11 is Kodi's standard ID for the "Yes" button
            if xbmc.getCondVisibility('Window.IsActive(dialogconfirm)'):
                xbmc.executebuiltin('SendClick(1301, 11)')
            
            if xbmc.getCondVisibility('Window.IsActive(yesnodialog)'):
                xbmc.executebuiltin('SendClick(1300, 11)')

            xbmc.sleep(250)
            elapsed += 250

        # Wait an extra second for Kodi's internal database to settle before disabling
        xbmc.sleep(1000)
        
        if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
            _set_addon_enabled(addon_id, False)

    progress.update(100, 'Done!')
    xbmc.sleep(800)
    progress.close()

    xbmc.executebuiltin('Skin.SetBool(madnox.extrasinstalled)')

    dialog.ok(
        'Madnox Setup',
        'Optional extras installed and [B]disabled[/B].\n\n'
        'Enable what you want in [I]Settings > Skin Settings > Addons[/I].'
    )