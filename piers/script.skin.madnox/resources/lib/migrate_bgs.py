import os
import re
import json
import xbmc
import xbmcvfs

# ---------------------------------------------------------------------------
# PLAYLIST BACKGROUND MAP
# Keys cover BOTH the old script path AND the new resource.images path,
# since either may be present in .properties depending on what ran before.
# XSP values use special://skin/ — the original skinshortcuts-native form.
# ---------------------------------------------------------------------------
PLAYLIST_BACKGROUND_MAP = {
    # --- Old script addon paths (pre-resource-addon move) ---
    "special://home/addons/script.skin.madnox/resources/extras/backgrounds/movies.jpg": (
        "playlist",
        "special://skin/extras/playlists/randommovies.xsp"
    ),
    "special://home/addons/script.skin.madnox/resources/extras/backgrounds/tvshows.jpg": (
        "playlist",
        "special://skin/extras/playlists/randomtvshows.xsp"
    ),
    "special://home/addons/script.skin.madnox/resources/extras/backgrounds/music.jpg": (
        "playlist",
        "special://skin/extras/playlists/randomalbums.xsp"
    ),
    # --- New resource.images addon paths (post-move) ---
    "special://home/addons/resource.images.skin.madnox/resources/backgrounds/movies.jpg": (
        "playlist",
        "special://skin/extras/playlists/randommovies.xsp"
    ),
    "special://home/addons/resource.images.skin.madnox/resources/backgrounds/tvshows.jpg": (
        "playlist",
        "special://skin/extras/playlists/randomtvshows.xsp"
    ),
    "special://home/addons/resource.images.skin.madnox/resources/backgrounds/music.jpg": (
        "playlist",
        "special://skin/extras/playlists/randomalbums.xsp"
    ),
}

PLAYLIST_BACKGROUND_NAMES = {
    "Random Movies Fanart",
    "Recent Movies Fanart",
    "Random TV Fanart",
    "Recent TV Fanart",
    "Random Music Fanart",
}

# ---------------------------------------------------------------------------
# FIX 4 regex: rewrites both script.skin.madnox and resource.images.skin.madnox
# image paths by removing the unwanted "extras/" directory, pointing them correctly
# to resource.images.skin.madnox/resources/. ONLY applies to image extensions.
# .xsp paths are intentionally excluded.
# ---------------------------------------------------------------------------
_FIX4_PATTERN = re.compile(
    r'(special://home/addons/)(?:script|resource\.images)\.skin\.madnox/resources/(?:extras/)?([^\s"<>\[\]]*?\.(?:jpg|jpeg|png|gif|webp|tbn|bmp))',
    re.IGNORECASE
)

def _apply_fix4(data):
    return _FIX4_PATTERN.sub(r'\1resource.images.skin.madnox/resources/\2', data)

# ---------------------------------------------------------------------------
# FIX 5 regex: restores any .xsp path that was incorrectly pushed to either
# the script addon absolute path OR the resource.images addon path back to
# the canonical special://skin/extras/ form that skinshortcuts expects.
#
# Matches variants with or without 'extras/':
#   special://home/addons/script.skin.madnox/resources/extras/...xsp
#   special://home/addons/resource.images.skin.madnox/resources/...xsp
# ---------------------------------------------------------------------------
_FIX5_PATTERN = re.compile(
    r'special://home/addons/(?:script|resource\.images)\.skin\.madnox/resources/(?:extras/)?([^\s"<>\[\]]*?\.xsp)',
    re.IGNORECASE
)

def _apply_fix5(data):
    return _FIX5_PATTERN.sub(r'special://skin/extras/\1', data)


def fix_playlist_backgrounds(entries):
    """
    Scan a .properties JSON entry list and fix any background entries that were
    incorrectly saved as a static JPG path when they should be playlist sentinels.

    Returns (fixed_entries, was_changed).
    """
    bg_index = {}
    bgname_index = {}
    bgplaylist_index = {}

    for i, entry in enumerate(entries):
        if len(entry) == 4:
            group, item_id, prop, value = entry
            key = (group, item_id)
            if prop == "background":
                bg_index[key] = i
            elif prop == "backgroundName":
                bgname_index[key] = i
            elif prop == "backgroundPlaylist":
                bgplaylist_index[key] = i

    changed = False

    for key, idx in bg_index.items():
        group, item_id = key
        current_bg_value = entries[idx][3]

        if current_bg_value not in PLAYLIST_BACKGROUND_MAP:
            continue

        name_idx = bgname_index.get(key)
        if name_idx is not None:
            stored_name = entries[name_idx][3]
            if stored_name not in PLAYLIST_BACKGROUND_NAMES:
                continue

        sentinel, xsp_path = PLAYLIST_BACKGROUND_MAP[current_bg_value]

        entries[idx][3] = sentinel
        changed = True
        xbmc.log(
            "migrate_bgs: Fixed background for [{}/{}]: '{}' -> '{}'".format(
                group, item_id, current_bg_value, sentinel
            ),
            xbmc.LOGINFO
        )

        playlist_idx = bgplaylist_index.get(key)
        if playlist_idx is not None:
            # XSP path already present — leave it alone, it may be a valid
            # user-picked absolute path that skinshortcuts wrote directly
            xbmc.log(
                "migrate_bgs: backgroundPlaylist for [{}/{}] already present — not overwriting '{}'".format(
                    group, item_id, entries[playlist_idx][3]
                ),
                xbmc.LOGINFO
            )
        else:
            new_entry = [group, item_id, "backgroundPlaylist", xsp_path]
            entries.insert(idx + 1, new_entry)
            xbmc.log(
                "migrate_bgs: Inserted backgroundPlaylist for [{}/{}]: '{}'".format(
                    group, item_id, xsp_path
                ),
                xbmc.LOGINFO
            )
            bgplaylist_index[key] = idx + 1

    return entries, changed


def run(params=None):
    userdata_dir = xbmcvfs.translatePath('special://profile/addon_data/script.skinshortcuts/')

    changes_made = False

    if os.path.exists(userdata_dir):
        for filename in os.listdir(userdata_dir):
            file_path = os.path.join(userdata_dir, filename)

            # --- Pass 1: String replacement fixes (path migration) ---
            if filename.endswith('.properties') or filename.endswith('.DATA.xml'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = f.read()

                original_data = data

                # FIX 1: special://skin/ -> script addon absolute path
                # (only for non-xsp paths; xsp will be caught by FIX 5 anyway)
                data = data.replace(
                    'special://skin/extras/',
                    'special://home/addons/script.skin.madnox/resources/extras/'
                )
                # FIX 2: Bare relative path (forward slash)
                data = data.replace(
                    'skin.madnox/extras',
                    'script.skin.madnox/resources/extras'
                )
                # FIX 3: Bare relative path (Windows backslash)
                data = data.replace(
                    'skin.madnox\\extras',
                    'script.skin.madnox\\resources\\extras'
                )
                # FIX 4: script/resource addon image paths -> resource.images addon paths,
                # explicitly removing "extras/" from the path.
                # Regex-guarded: ONLY rewrites paths ending in image extensions.
                # .xsp paths are excluded here — FIX 5 handles those instead.
                data = _apply_fix4(data)

                # FIX 5: Restore any .xsp path that was incorrectly pushed to
                # script.skin.madnox or resource.images.skin.madnox back to the
                # canonical special://skin/extras/ form skinshortcuts expects.
                data = _apply_fix5(data)

                if data != original_data:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(data)
                    changes_made = True
                    xbmc.log(
                        "migrate_bgs: Rewrote paths in '{}'".format(filename),
                        xbmc.LOGINFO
                    )

            # --- Pass 2: JSON-aware playlist background fix (.properties only) ---
            if filename.endswith('.properties'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    raw = f.read()

                try:
                    entries = json.loads(raw)
                except (json.JSONDecodeError, ValueError) as e:
                    xbmc.log(
                        "migrate_bgs: Could not parse JSON in '{}': {}".format(filename, e),
                        xbmc.LOGWARNING
                    )
                    continue

                fixed_entries, was_changed = fix_playlist_backgrounds(entries)

                if was_changed:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(fixed_entries, f, indent=4, ensure_ascii=False)
                    changes_made = True

    # Rebuild the menu if anything changed
    if changes_made:
        xbmc.log("migrate_bgs: Changes detected — triggering skinshortcuts rebuild.", xbmc.LOGINFO)
        xbmc.executebuiltin(
            'RunScript(script.skinshortcuts,type=buildxml&mainmenuID=9000&group=mainmenu|shortcuts)'
        )
    else:
        xbmc.log("migrate_bgs: No changes needed — all paths already current.", xbmc.LOGINFO)

    # Mark as done so this never runs again
    xbmc.executebuiltin('Skin.SetBool(Madnox_Backgrounds_Migrated)')