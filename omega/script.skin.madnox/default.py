import sys
import xbmc
import xbmcgui  # Added xbmcgui to interact with Kodi windows

# Core helpers
from resources.lib import apply_template
from resources.lib import color_loader
from resources.lib import core_color_helper
from resources.lib import intro_preview
from resources.lib import install_extras
from resources.lib import jump_to_letter
from resources.lib import madnox_cinema
from resources.lib import play_album_songs
from resources.lib import play_all_music_videos_from_container
from resources.lib import play_trailer
from resources.lib import preset_manager
from resources.lib import process_ratings
from resources.lib import migrate_bgs
from resources.lib import script_decrement_movie as decrement_movie
from resources.lib import script_decrement_person as decrement_person
from resources.lib import set_intro_label
from resources.lib import tmdb_helper_settingswriter as TMDb_Helper_SettingsWriter
from resources.lib import tmdb_installed_validation
from resources.lib import trailer_rolling
from resources.lib import collection_view_sync


def get_params():
    params = {}
    current_key = None
    for arg in sys.argv[1:]:
        clean_arg = arg.strip().rstrip(',')
        if "=" in clean_arg:
            key, val = clean_arg.split("=", 1)
            current_key = key.strip().lower()
            params[current_key] = val.strip()
        elif current_key:
            params[current_key] += "," + clean_arg.strip()
            
    return params

def main():
    params = get_params()
    action = params.get("action", "").strip()
    
    if not action:
        return

    home_window = xbmcgui.Window(10000)
    home_window.setProperty('scriptdialog', f'script.skin.madnox ({action})')

    try:
        if action == "play_trailer":
            play_trailer.run(params)
        elif action == "trailer_rolling":
            trailer_rolling.run()
        elif action == "play_album_songs":
            play_album_songs.run()
        elif action == "play_all_music_videos":
            play_all_music_videos_from_container.run()
        elif action == "decrement_movie":
            decrement_movie.run()
        elif action == "decrement_person":
            decrement_person.run()
        elif action == "validate_tmdb_helper":
            tmdb_installed_validation.run()
        elif action == "apply_template":
            apply_template.run()
        elif action == "intro_preview":
            intro_preview.run()
        elif action == "show_color_loader":
            color_loader.run(params)
        elif action == "write_setting":
            TMDb_Helper_SettingsWriter.run(params)
        elif action == "core_color_helper":
            core_color_helper.run(params)
        elif action == "set_intro_label":
            set_intro_label.run(params)
        elif action == "madnox_cinema":
            madnox_cinema.run(params)
        elif action == "process_ratings":
            process_ratings.run(params)
        elif action == "migrate_bgs":
            migrate_bgs.run(params)
        elif action == "smsjump":
            jump_to_letter.run(params)
        elif action == 'install_extras':
            from resources.lib.install_extras import run
            run()
        elif action == "manage_presets":
            preset_manager.run()
        elif action == "collection_view_sync":
            collection_view_sync.run(params)          

    finally:
        home_window.clearProperty('scriptdialog')

if __name__ == "__main__":
    main()
