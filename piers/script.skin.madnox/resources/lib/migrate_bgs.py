import os
import re
import json
import xbmc
import xbmcvfs

# ---------------------------------------------------------------------------
# CHANGELOG
# v2 fixes:
#   - Removed FIX 1 (special://skin/extras/ → script addon absolute path).
#     FIX 1 was corrupting icon/background paths that were already in the
#     correct special://skin/extras/ form by expanding them to the old script
#     addon path, which FIX 4 would then only partially repair. The canonical
#     special://skin/ paths for icons are intentional and must not be touched.
#   - Removed FIX 2 and FIX 3 (bare relative path rewrites). These were
#     defensive dead-code that only existed to feed FIX 1's now-removed
#     expansion step. No skinshortcuts file will ever contain a bare relative
#     path like 'skin.madnox/extras' in practice.
#   - Scoped FIX 4 to backgrounds/ subdirectory only. The regex previously
#     matched any image path under resources/ in either addon, which meant
#     icons served via special://skin/ that got incorrectly expanded by FIX 1
#     could be further mangled by FIX 4. Locking it to backgrounds/ makes the
#     intent explicit and prevents any future regression.
#   - Added the special://skin/extras/backgrounds/ form to FIX 4 so that
#     skinshortcuts-native background paths (the form most users will actually
#     have on a fresh upgrade) are correctly rewritten to the resource.images
#     addon without needing any prior expansion step.
#   - PLAYLIST_BACKGROUND_MAP extended to include the special://skin/extras/
#     canonical forms, so Pass 2 can correctly fix playlist sentinels even
#     when Pass 1 did not need to rewrite anything.
# ---------------------------------------------------------------------------

LOG_PREFIX = "migrate_bgs"


# ---------------------------------------------------------------------------
# PLAYLIST BACKGROUND MAP
# Keys cover ALL known forms a background value may be stored as:
#   1. special://skin/extras/   — skinshortcuts-native canonical form
#   2. script.skin.madnox       — old pre-resource-addon absolute path
#   3. resource.images.skin.madnox — post-resource-addon absolute path
#       (this form is written by FIX 4 in Pass 1, so Pass 2 sees it)
#
# Values are (sentinel, xsp_path).  The sentinel "playlist" is the value
# skinshortcuts stores in the 'background' field when a playlist background
# is active.  The xsp_path uses special://skin/ — the skinshortcuts-native
# form that Kodi resolves at runtime.
# ---------------------------------------------------------------------------
PLAYLIST_BACKGROUND_MAP = {
    # --- skinshortcuts-native form (most users on a clean upgrade) ---
    "special://skin/extras/backgrounds/movies.jpg": (
        "playlist",
        "special://skin/extras/playlists/randommovies.xsp"
    ),
    "special://skin/extras/backgrounds/tvshows.jpg": (
        "playlist",
        "special://skin/extras/playlists/randomtvshows.xsp"
    ),
    "special://skin/extras/backgrounds/music.jpg": (
        "playlist",
        "special://skin/extras/playlists/randomalbums.xsp"
    ),
    # --- Old script addon absolute paths (pre-resource-addon move) ---
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
    # --- resource.images addon paths (written by FIX 4 in Pass 1) ---
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

# Background names that indicate a skinshortcuts-managed playlist background.
# If a background value matches PLAYLIST_BACKGROUND_MAP but the backgroundName
# is NOT in this set, the entry is a user-customised static image and must be
# left alone.
PLAYLIST_BACKGROUND_NAMES = {
    "Random Movies Fanart",
    "Recent Movies Fanart",
    "Random TV Fanart",
    "Recent TV Fanart",
    "Random Music Fanart",
}


# ---------------------------------------------------------------------------
# FIX 4
# Rewrites background image paths from either:
#   special://skin/extras/backgrounds/...          (skinshortcuts-native)
#   special://home/addons/script.skin.madnox/resources/[extras/]backgrounds/...
#   special://home/addons/resource.images.skin.madnox/resources/[extras/]backgrounds/...
# to the canonical resource.images addon form:
#   special://home/addons/resource.images.skin.madnox/resources/backgrounds/...
#
# Intentionally scoped to the backgrounds/ subdirectory only.
# Icon paths under special://skin/extras/icons/ are NOT matched and are
# left exactly as skinshortcuts wrote them.
# .xsp paths are excluded by requiring an image file extension.
# ---------------------------------------------------------------------------
_FIX4_PATTERN = re.compile(
    r'(?:'
    r'special://skin/extras/'                                                       # skinshortcuts-native form
    r'|'
    r'special://home/addons/(?:script|resource\.images)\.skin\.madnox/resources/(?:extras/)?'  # absolute forms
    r')'
    r'(backgrounds/[^\s"<>\[\]]*?\.(?:jpg|jpeg|png|gif|webp|tbn|bmp))',
    re.IGNORECASE
)

def _apply_fix4(data):
    return _FIX4_PATTERN.sub(
        r'special://home/addons/resource.images.skin.madnox/resources/\1',
        data
    )


# ---------------------------------------------------------------------------
# FIX 5
# Restores any .xsp path that ended up with a script.skin.madnox or
# resource.images.skin.madnox absolute prefix back to the canonical
# special://skin/extras/ form that skinshortcuts expects at runtime.
#
# This is a safety net. With FIX 1 removed it should never fire, but it
# is kept because it is cheap and harmless, and guards against any future
# code inadvertently expanding .xsp paths.
# ---------------------------------------------------------------------------
_FIX5_PATTERN = re.compile(
    r'special://home/addons/(?:script|resource\.images)\.skin\.madnox/resources/(?:extras/)?'
    r'([^\s"<>\[\]]*?\.xsp)',
    re.IGNORECASE
)

def _apply_fix5(data):
    return _FIX5_PATTERN.sub(r'special://skin/extras/\1', data)


# ---------------------------------------------------------------------------
# Pass 2 — JSON-aware playlist background sentinel fix
# ---------------------------------------------------------------------------

def fix_playlist_backgrounds(entries):
    """
    Scan a parsed .properties JSON entry list and fix any background entries
    that are stored as a static JPG path when they should be the "playlist"
    sentinel that skinshortcuts uses to activate playlist-driven backgrounds.

    Logic:
      - Find every entry with prop == "background" whose value is a key in
        PLAYLIST_BACKGROUND_MAP.
      - If a backgroundName entry exists for the same (group, item_id) pair,
        verify it is in PLAYLIST_BACKGROUND_NAMES before touching anything.
        This prevents overwriting a user's custom static background that
        happens to point to one of the Madnox default images.
      - Replace the background value with the "playlist" sentinel.
      - If no backgroundPlaylist entry exists for that pair, insert one
        immediately after the background entry with the correct .xsp path.
        If one already exists, leave it alone (it may be a user-chosen path).

    Returns (fixed_entries, was_changed).
    """
    # Build index maps so we can find related entries by (group, item_id)
    bg_index = {}
    bgname_index = {}
    bgplaylist_index = {}

    for i, entry in enumerate(entries):
        if len(entry) != 4:
            continue
        group, item_id, prop, _value = entry
        key = (group, item_id)
        if prop == "background":
            bg_index[key] = i
        elif prop == "backgroundName":
            bgname_index[key] = i
        elif prop == "backgroundPlaylist":
            bgplaylist_index[key] = i

    changed = False

    # Iterate over a snapshot of keys so list.insert() doesn't shift indices
    # we haven't visited yet.  We re-read entry positions from the live list
    # inside the loop via the stored index, which may be stale after an
    # insert.  To keep this safe we process entries in reverse index order
    # so that any insert at idx+1 only shifts entries we have already handled.
    for key in sorted(bg_index.keys(), key=lambda k: bg_index[k], reverse=True):
        idx = bg_index[key]
        group, item_id = key
        current_bg_value = entries[idx][3]

        if current_bg_value not in PLAYLIST_BACKGROUND_MAP:
            continue

        # If a backgroundName is present, verify it belongs to a known
        # playlist background before proceeding.
        name_idx = bgname_index.get(key)
        if name_idx is not None:
            stored_name = entries[name_idx][3]
            if stored_name not in PLAYLIST_BACKGROUND_NAMES:
                xbmc.log(
                    "{}: Skipping [{}/{}] — backgroundName '{}' is not a known "
                    "playlist background name, treating as user custom.".format(
                        LOG_PREFIX, group, item_id, stored_name
                    ),
                    xbmc.LOGINFO
                )
                continue

        sentinel, xsp_path = PLAYLIST_BACKGROUND_MAP[current_bg_value]

        # Rewrite the background value to the "playlist" sentinel
        entries[idx][3] = sentinel
        changed = True
        xbmc.log(
            "{}: Fixed background for [{}/{}]: '{}' -> '{}'".format(
                LOG_PREFIX, group, item_id, current_bg_value, sentinel
            ),
            xbmc.LOGINFO
        )

        playlist_idx = bgplaylist_index.get(key)
        if playlist_idx is not None:
            xbmc.log(
                "{}: backgroundPlaylist for [{}/{}] already present ('{}') — not overwriting.".format(
                    LOG_PREFIX, group, item_id, entries[playlist_idx][3]
                ),
                xbmc.LOGINFO
            )
        else:
            new_entry = [group, item_id, "backgroundPlaylist", xsp_path]
            entries.insert(idx + 1, new_entry)
            # Update our local index map in case we process another key that
            # sits below this insertion point (reverse ordering makes this
            # moot, but it keeps the map accurate for the log message above).
            bgplaylist_index[key] = idx + 1
            xbmc.log(
                "{}: Inserted backgroundPlaylist for [{}/{}]: '{}'".format(
                    LOG_PREFIX, group, item_id, xsp_path
                ),
                xbmc.LOGINFO
            )

    return entries, changed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(params=None):
    userdata_dir = xbmcvfs.translatePath(
        'special://profile/addon_data/script.skinshortcuts/'
    )

    changes_made = False

    if not os.path.exists(userdata_dir):
        xbmc.log(
            "{}: skinshortcuts userdata directory not found — nothing to migrate.".format(LOG_PREFIX),
            xbmc.LOGWARNING
        )
        # Still mark as done so we don't retry on every boot.
        xbmc.executebuiltin('Skin.SetBool(Madnox_Backgrounds_Migrated)')
        return

    for filename in os.listdir(userdata_dir):
        file_path = os.path.join(userdata_dir, filename)

        # Only touch regular files
        if not os.path.isfile(file_path):
            continue

        # ---------------------------------------------------------------
        # Pass 1 — String-level path rewrite (.properties and .DATA.xml)
        # Rewrites background image paths to the canonical resource.images
        # addon form.  Icon paths (special://skin/extras/icons/) are NOT
        # matched by FIX 4 and are left untouched.
        # ---------------------------------------------------------------
        if filename.endswith('.properties') or filename.endswith('.DATA.xml'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = f.read()
            except (IOError, OSError) as e:
                xbmc.log(
                    "{}: Could not read '{}': {}".format(LOG_PREFIX, filename, e),
                    xbmc.LOGWARNING
                )
                continue

            original_data = data

            # FIX 4: Rewrite background image paths to resource.images addon.
            #   Handles all three source forms:
            #     special://skin/extras/backgrounds/...
            #     special://home/addons/script.skin.madnox/resources/[extras/]backgrounds/...
            #     special://home/addons/resource.images.skin.madnox/resources/[extras/]backgrounds/...
            data = _apply_fix4(data)

            # FIX 5: Safety net — restore any .xsp path that ended up with
            # an absolute addon prefix back to special://skin/extras/.
            data = _apply_fix5(data)

            if data != original_data:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(data)
                    changes_made = True
                    xbmc.log(
                        "{}: Rewrote paths in '{}'.".format(LOG_PREFIX, filename),
                        xbmc.LOGINFO
                    )
                except (IOError, OSError) as e:
                    xbmc.log(
                        "{}: Could not write '{}': {}".format(LOG_PREFIX, filename, e),
                        xbmc.LOGWARNING
                    )
                    continue

        # ---------------------------------------------------------------
        # Pass 2 — JSON-aware playlist background sentinel fix
        # Re-reads the file after Pass 1 so it sees the already-rewritten
        # paths, which means PLAYLIST_BACKGROUND_MAP only needs to cover
        # the resource.images form for paths that came through Pass 1.
        # The special://skin/ and script.skin.madnox forms are still
        # included in the map as a fallback for .DATA.xml files or any
        # file that Pass 1 did not modify.
        # ---------------------------------------------------------------
        if filename.endswith('.properties'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    raw = f.read()
            except (IOError, OSError) as e:
                xbmc.log(
                    "{}: Could not re-read '{}' for Pass 2: {}".format(LOG_PREFIX, filename, e),
                    xbmc.LOGWARNING
                )
                continue

            try:
                entries = json.loads(raw)
            except (json.JSONDecodeError, ValueError) as e:
                xbmc.log(
                    "{}: Could not parse JSON in '{}': {}".format(LOG_PREFIX, filename, e),
                    xbmc.LOGWARNING
                )
                continue

            if not isinstance(entries, list):
                xbmc.log(
                    "{}: Unexpected JSON structure in '{}' (not a list) — skipping.".format(
                        LOG_PREFIX, filename
                    ),
                    xbmc.LOGWARNING
                )
                continue

            fixed_entries, was_changed = fix_playlist_backgrounds(entries)

            if was_changed:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(fixed_entries, f, indent=4, ensure_ascii=False)
                    changes_made = True
                    xbmc.log(
                        "{}: Wrote playlist sentinel fixes to '{}'.".format(LOG_PREFIX, filename),
                        xbmc.LOGINFO
                    )
                except (IOError, OSError) as e:
                    xbmc.log(
                        "{}: Could not write Pass 2 result to '{}': {}".format(
                            LOG_PREFIX, filename, e
                        ),
                        xbmc.LOGWARNING
                    )

    # Trigger a skinshortcuts menu rebuild if any file was changed so the
    # corrected paths are reflected in the generated XML immediately.
    if changes_made:
        xbmc.log(
            "{}: Migration complete — triggering skinshortcuts rebuild.".format(LOG_PREFIX),
            xbmc.LOGINFO
        )
        xbmc.executebuiltin(
            'RunScript(script.skinshortcuts,type=buildxml&mainmenuID=9000&group=mainmenu|shortcuts)'
        )
    else:
        xbmc.log(
            "{}: No changes needed — all paths already current.".format(LOG_PREFIX),
            xbmc.LOGINFO
        )

    # Mark migration as complete so Custom_1101_IntroRouter.xml does not
    # fire this script again on subsequent boots.
    xbmc.executebuiltin('Skin.SetBool(Madnox_Backgrounds_Migrated)')
