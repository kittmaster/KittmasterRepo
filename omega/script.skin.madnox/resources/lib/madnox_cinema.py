import xbmc
import xbmcgui
import xbmcvfs
import json
import random
import os
import sys
import re

# --- HELPER FUNCTIONS ---

def log(msg):
    xbmc.log('[Madnox Cinema] %s' % msg, level=xbmc.LOGINFO)

def get_skin_string(setting):
    value = xbmc.getInfoLabel('Skin.String(%s)' % setting)
    return value if value != '' else None

def set_skin_string(setting, value):
    xbmc.executebuiltin('Skin.SetString(%s, %s)' % (setting, value))

def is_disabled(feature_suffix):
    return xbmc.getCondVisibility('Skin.HasSetting(CinemaDisable%s)' % feature_suffix)

def json_call(method, params=None):
    payload = {
        'jsonrpc': '2.0', 'method': method, 'params': params or {}, 'id': 1
    }
    try:
        response = xbmc.executeJSONRPC(json.dumps(payload))
        return json.loads(response)
    except Exception as e:
        log('JSONRPC Error: %s' % str(e))
        return {}

# --- MAIN LOGIC ---

class CinemaMode(object):
    def __init__(self, params):
        # 1. READ ARGUMENTS
        self.params = params
        self.mode = self.params.get('mode', 'playback') 
        
        # 2. READ SETTINGS
        count_str = get_skin_string('TrailerCount')
        self.trailer_count = int(count_str) if count_str and count_str.isdigit() else 0
        
        raw_path = get_skin_string('IntroPath')
        if raw_path:
            self.intro_path = xbmcvfs.translatePath(raw_path).replace('\\', '/')
            if not self.intro_path.endswith('/'):
                self.intro_path += '/'
        else:
            self.intro_path = None
        
        self.trailer_source = get_skin_string('TrailerSource') 
        if not self.trailer_source: self.trailer_source = '0'
        
        self.active_theme = None 
        self.show_notifications = True if xbmc.getCondVisibility('Skin.HasSetting(CinemaNotifications)') else False

        # MASTER LIST OF REQUIRED FOLDERS
        self.required_structure = [
            'Feature_Intros',
            'Trailer_Intros',
            'Trailer_Outros',
            'Courtesy',
            'Countdowns',
            'Feature_Outros',
            'Intros',
            'Audio/Stereo',
            'Audio/Dolby TrueHD',
            'Audio/Dolby Atmos',
            'Audio/DTS-HD Master Audio',
            'Audio/DTS',
            'Audio/Dolby Digital Plus',
            'Audio/Dolby Digital',
            'Audio/Dolby Stereo',
            'Audio/Auro-3D',
            'Audio/DTS-X',
            'Audio/THX',
            'Audio/Datasat',
            'Ratings/G',
            'Ratings/PG',
            'Ratings/PG-13',
            'Ratings/R',
            'Ratings/NC-17',
            'Ratings/NR'
        ]

    def execute(self):
        if self.mode == 'setup':
            self.run_setup_wizard()
        elif self.mode == 'check':
            self.run_silent_check()
        else:
            # Playback Mode
            self.dbid = self.params.get('dbid')
            self.dbtype = self.params.get('dbtype')
            
            # FALLBACK: If params are empty/missing, grab from Kodi UI
            if not self.dbid or self.dbid == "":
                self.dbid = xbmc.getInfoLabel('ListItem.DBID')
            if not self.dbtype or self.dbtype == "":
                self.dbtype = xbmc.getInfoLabel('ListItem.DBType') or 'movie'

            if self.dbid and self.dbtype == 'movie':
                self.run()
            else:
                log('Skipping: No DBID found or not a movie.')
                if self.dbid:
                    xbmc.executebuiltin('PlayMedia(videodb://movies/titles/%s)' % self.dbid)

    def notify(self, msg, is_error=False, force=False):
        if force or self.show_notifications:
            icon = xbmcgui.NOTIFICATION_ERROR if is_error else xbmcgui.NOTIFICATION_INFO
            xbmcgui.Dialog().notification('Cinema Mode', msg, icon, 5000)
        else:
            log('SUPPRESSED NOTIFICATION: %s' % msg)

    # =========================================================================
    # SILENT CHECK (Status Updater)
    # =========================================================================
    def run_silent_check(self):
        if not self.intro_path:
            set_skin_string('CinemaAssetsStatus', 'Invalid')
            return

        missing = False
        for folder in self.required_structure:
            check_path = self.intro_path + folder
            if not xbmcvfs.exists(check_path) and not os.path.exists(xbmcvfs.translatePath(check_path)):
                missing = True
                break
        
        status = 'Invalid' if missing else 'Valid'
        set_skin_string('CinemaAssetsStatus', status)
        log('Silent Check Complete. Status: %s' % status)

    # =========================================================================
    # SETUP WIZARD LOGIC
    # =========================================================================
    def run_setup_wizard(self):
        if not self.intro_path:
            xbmcgui.Dialog().ok('Cinema Mode', 'Please set the "Intro Path" in settings first.')
            set_skin_string('CinemaAssetsStatus', 'Invalid')
            return

        missing_folders = []
        for folder in self.required_structure:
            check_path = self.intro_path + folder
            if not xbmcvfs.exists(check_path) and not os.path.exists(xbmcvfs.translatePath(check_path)):
                missing_folders.append(folder)

        if not missing_folders:
            set_skin_string('CinemaAssetsStatus', 'Valid')
            xbmcgui.Dialog().ok('Cinema Mode', 'Structure Verified!\nAll folders are present.')
            return

        set_skin_string('CinemaAssetsStatus', 'Invalid')

        msg = 'Found %s missing folders in your Cinema Assets root.\nDo you want to create them now?' % len(missing_folders)
        if xbmcgui.Dialog().yesno('Cinema Mode Setup', msg):
            created_count = 0
            error_count = 0
            
            for folder in missing_folders:
                full_path = self.intro_path + folder
                try:
                    xbmcvfs.mkdirs(full_path)
                    
                    os_path = xbmcvfs.translatePath(full_path)
                    if xbmcvfs.exists(full_path) or os.path.exists(os_path):
                        created_count += 1
                    else:
                        error_count += 1
                        log('Failed to verify folder creation: %s' % full_path)
                        
                except Exception as e:
                    error_count += 1
                    log('Exception creating folder: %s' % str(e))
            
            if error_count == 0:
                set_skin_string('CinemaAssetsStatus', 'Valid')
            
            result_msg = 'Setup Complete.\nCreated: %s\nErrors: %s' % (created_count, error_count)
            if error_count > 0:
                result_msg += '\n(Check write permissions on your drive)'
            
            xbmcgui.Dialog().ok('Cinema Mode', result_msg)

    # =========================================================================
    # PLAYBACK LOGIC
    # =========================================================================
    def run(self):
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()
        index = 0
        
        # --- PRE-FLIGHT CHECK ---
        if not self.intro_path:
            self.notify('Intro Path is not set! Check Settings.', is_error=True, force=True)

        movie_details = self.get_movie_details()
        assets_found = False 

        # --- SEQUENCE 1: FEATURE INTRO ---
        if self.intro_path and not is_disabled('FeatureIntro'):
            f_intro = self.select_feature_intro('Feature_Intros')
            if not f_intro: f_intro = self.select_feature_intro('Intros')
            
            if f_intro:
                self.add_to_playlist(playlist, f_intro, 'Feature Intro', index)
                index += 1
                assets_found = True
                filename = os.path.basename(f_intro)
                if ' - ' in filename:
                    self.active_theme = filename.rsplit(' - ', 1)[0]
                    log('Active Theme: "%s"' % self.active_theme)
                    set_skin_string('CinemaLastTheme', self.active_theme)

        # --- SEQUENCE 2: TRAILERS ---
        if self.trailer_count > 0:
            trailers = []
            if self.trailer_source == '2':
                log('Source: Local Library')
                trailers = self.get_local_trailers()
            elif self.trailer_source == '1':
                log('Source: TMDB Helper (Upcoming)')
                trailers = self.get_tmdb_trailers('info=upcoming&type=movie')
            else:
                log('Source: TMDB Helper (In Theaters)')
                trailers = self.get_tmdb_trailers('info=now_playing&type=movie')

            if trailers:
                if self.intro_path and not is_disabled('TrailerIntro'):
                    t_intro = self.get_smart_asset('Trailer_Intros', match_theme=True)
                    if t_intro:
                        self.add_to_playlist(playlist, t_intro, 'Trailers Intro', index)
                        index += 1
                        assets_found = True

                for t in trailers:
                    t['listitem'].setPath(t['url'])
                    playlist.add(url=t['url'], listitem=t['listitem'], index=index)
                    log('Queued Trailer: %s' % t['title'])
                    index += 1

                if self.intro_path and not is_disabled('TrailerOutro'):
                    t_outro = self.get_smart_asset('Trailer_Outros', match_theme=True)
                    if t_outro:
                        self.add_to_playlist(playlist, t_outro, 'Trailers Outro', index)
                        index += 1
                        assets_found = True
            
            elif self.trailer_source == '2':
                 log('No local trailers found.')
                 if self.trailer_count > 0:
                     self.notify('No Local Trailers found (Check Library)', is_error=True)

        # --- SEQUENCE 3: FORMAT BUMPERS ---
        if self.intro_path:
            if not is_disabled('Audio'):
                audio_bumper = self.get_audio_bumper(movie_details)
                if audio_bumper:
                    self.add_to_playlist(playlist, audio_bumper, 'Audio Format Bumper', index)
                    index += 1
                    assets_found = True

            if not is_disabled('Courtesy'):
                courtesy = self.get_smart_asset('Courtesy', match_theme=True)
                if courtesy:
                    self.add_to_playlist(playlist, courtesy, 'Courtesy Bumper', index)
                    index += 1
                    assets_found = True

            if not is_disabled('Ratings'):
                rating_bumper = self.get_rating_bumper(movie_details)
                if rating_bumper:
                    self.add_to_playlist(playlist, rating_bumper, 'Rating Bumper', index)
                    index += 1
                    assets_found = True

        # --- SEQUENCE 4: COUNTDOWN ---
        if self.intro_path and not is_disabled('Countdown'):
            countdown = self.get_smart_asset('Countdowns', match_theme=True)
            if countdown:
                self.add_to_playlist(playlist, countdown, 'Countdown', index)
                index += 1
                assets_found = True

        # --- SEQUENCE 5: MAIN MOVIE ---
        if self.dbid:
            json_call('Playlist.Add', 
                    params={'item': {'movieid': int(self.dbid)}, 'playlistid': 1}
            )
            log('Queued Movie. Index: %s' % index)
            index += 1
        else:
            log('Error: Failed to queue main movie.')
            return

        # --- SEQUENCE 6: FEATURE OUTRO ---
        if self.intro_path and not is_disabled('FeatureOutro'):
            f_outro = self.get_smart_asset('Feature_Outros', match_theme=True)
            if not f_outro: f_outro = self.get_smart_asset('Outros', match_theme=True)
            if f_outro:
                self.add_to_playlist(playlist, f_outro, 'Feature Outro', index)
                index += 1
                assets_found = True

        if self.intro_path and not assets_found:
             self.notify('No assets found in: %s' % self.intro_path, is_error=True)

        log('Starting Playback. Total items: %s' % index)
        xbmc.executebuiltin('Dialog.Close(all,true)')
        xbmc.Player().play(playlist)

    def add_to_playlist(self, playlist, url, title, index):
        li = xbmcgui.ListItem(title, offscreen=True)
        li.setInfo('video', {'Title': title})
        li.setPath(url)
        playlist.add(url=url, listitem=li, index=index)
        log('Queued: %s | File: %s' % (title, os.path.basename(url)))

    # --- SMART ASSET LOGIC ---

    def select_feature_intro(self, folder_name):
        if not self.intro_path: return None
        target_path = self.intro_path + folder_name + '/'
        
        if not xbmcvfs.exists(target_path): return None
        dirs, files = xbmcvfs.listdir(target_path)
        valid_ext = ('.mp4', '.mkv', '.mpg', '.mpeg', '.avi', '.mov', '.wmv')
        valid_files = [f for f in files if f.lower().endswith(valid_ext)]
        
        if not valid_files: return None

        last_theme = get_skin_string('CinemaLastTheme')
        if last_theme and len(valid_files) > 1:
            candidates = [f for f in valid_files if last_theme not in f]
            if candidates:
                log('Avoiding Repeat of "%s"' % last_theme)
                return target_path + random.choice(candidates)
        
        return target_path + random.choice(valid_files)

    def get_smart_asset(self, folder_name, allow_fallback=False, match_theme=False):
        if not self.intro_path: return None
        
        target_path = self.intro_path + folder_name + '/'
        
        file = self._scan_folder_for_video(target_path, match_theme, notify_on_fail=True)
        if file: return file
            
        if allow_fallback:
            if folder_name and self.intro_path.endswith(folder_name + '/'):
                return None 
            
            file = self._scan_folder_for_video(self.intro_path, match_theme, notify_on_fail=False)
            if file: return file
            
        return None

    def _scan_folder_for_video(self, path, match_theme=False, notify_on_fail=False):
        if not xbmcvfs.exists(path): 
            if notify_on_fail: 
                self.notify('Missing Folder: %s' % path, is_error=True)
            return None
        
        dirs, files = xbmcvfs.listdir(path)
        valid_ext = ('.mp4', '.mkv', '.mpg', '.mpeg', '.avi', '.mov', '.wmv')
        valid_files = [f for f in files if f.lower().endswith(valid_ext)]
        
        if not valid_files: 
            if notify_on_fail: 
                self.notify('Empty Folder: %s' % path, is_error=True)
            return None

        if match_theme and self.active_theme:
            matched_files = [f for f in valid_files if self.active_theme.lower() in f.lower()]
            if matched_files:
                log('Matched Theme "%s" in %s' % (self.active_theme, path))
                return path + random.choice(matched_files)
            else:
                log('Theme "%s" not found in %s. Falling back to random.' % (self.active_theme, path))
        
        return path + random.choice(valid_files)

    def get_audio_bumper(self, details):
        if not details or 'streamdetails' not in details: return None
        try:
            audio_streams = details['streamdetails'].get('audio', [])
            if not audio_streams: return None
            
            stream = audio_streams[0]
            codec = stream.get('codec', '').lower()
            try: channels = int(stream.get('channels', 2))
            except: channels = 2
            
            folder_name = 'Stereo'
            
            if 'truehd' in codec: folder_name = 'Dolby TrueHD'
            elif 'atmos' in codec: folder_name = 'Dolby Atmos'
            elif 'dtshd_ma' in codec or 'dts-hd' in codec: folder_name = 'DTS-HD Master Audio'
            elif 'dts' in codec and 'ma' in codec: folder_name = 'DTS-HD Master Audio'
            elif 'dts' in codec and 'x' in codec: folder_name = 'DTS-X'
            elif 'auro' in codec: folder_name = 'Auro-3D'
            elif 'dts' in codec: folder_name = 'DTS'
            elif 'eac3' in codec: folder_name = 'Dolby Digital Plus'
            elif 'ac3' in codec: 
                folder_name = 'Dolby Digital' if channels > 2 else 'Dolby Stereo'
            elif channels > 2: 
                folder_name = 'Dolby Digital'
            else:
                folder_name = 'Stereo'
            
            asset = self.get_smart_asset('Audio/%s' % folder_name, allow_fallback=False)
            
            if not asset:
                if folder_name == 'Dolby TrueHD': asset = self.get_smart_asset('Audio/Dolby Digital')
                elif folder_name == 'Dolby Atmos': asset = self.get_smart_asset('Audio/Dolby TrueHD') or self.get_smart_asset('Audio/Dolby Digital')
                elif folder_name == 'DTS-HD Master Audio': asset = self.get_smart_asset('Audio/DTS')
                elif folder_name == 'DTS-X': asset = self.get_smart_asset('Audio/DTS-HD Master Audio') or self.get_smart_asset('Audio/DTS')
                elif folder_name == 'Dolby Digital Plus': asset = self.get_smart_asset('Audio/Dolby Digital')
                elif folder_name == 'Dolby Stereo': asset = self.get_smart_asset('Audio/Stereo')
            
            return asset
        except Exception: pass
        return None

    def get_rating_bumper(self, details):
        if not details: return None
        mpaa = details.get('mpaa', '')
        clean_rating = mpaa.replace('Rated ', '').replace('USA:', '').strip().upper()
        
        target_folder = None
        if re.search(r'\bNC-?17\b', clean_rating): target_folder = 'NC-17'
        elif re.search(r'\bPG-?13\b', clean_rating): target_folder = 'PG-13'
        elif re.search(r'\bPG\b', clean_rating): target_folder = 'PG'
        elif re.search(r'\bNR\b', clean_rating) or 'NOT RATED' in clean_rating: target_folder = 'NR'
        elif re.search(r'\bR\b', clean_rating): target_folder = 'R'
        elif re.search(r'\bG\b', clean_rating): target_folder = 'G'
        
        if target_folder:
            return self.get_smart_asset('Ratings/%s' % target_folder, allow_fallback=False)
        return None

    def get_movie_details(self):
        if not self.dbid: return {}
        result = json_call('VideoLibrary.GetMovieDetails', {
            'movieid': int(self.dbid),
            'properties': ['mpaa', 'streamdetails']
        })
        if 'result' in result and 'moviedetails' in result['result']:
            return result['result']['moviedetails']
        return {}

    # --- TRAILER LOGIC ---
    def get_tmdb_trailers(self, query_params):
        tmdb_url = 'plugin://plugin.video.themoviedb.helper/?%s' % query_params
        valid_items = []
        try:
            log('Fetching List: %s' % tmdb_url)
            data = json_call('Files.GetDirectory', {
                'directory': tmdb_url, 'media': 'video', 'properties': ['title', 'art', 'plot', 'year', 'rating', 'file', 'trailer']
            })
            if 'result' in data and 'files' in data['result']:
                files = data['result']['files']
                random.shuffle(files)
                count = 0
                for item in files:
                    if count >= self.trailer_count: break
                    file_path = item.get('file', '')
                    tmdb_id_match = re.search(r'(?:tmdb_id|id)=(\d+)', file_path)
                    if tmdb_id_match and 'info=gemini' not in file_path:
                        tmdb_id = tmdb_id_match.group(1)
                        title = '%s (Trailer)' % item.get('title', 'Unknown')
                        trailer_url = self.resolve_online_trailer(tmdb_id)
                        if trailer_url:
                            li = xbmcgui.ListItem(title, offscreen=True)
                            li.setInfo('video', {'Title': title, 'plot': item.get('plot', '')})
                            li.setArt(item.get('art', {}))
                            valid_items.append({'url': trailer_url, 'listitem': li, 'title': title})
                            count += 1
        except Exception: pass
        return valid_items

    def resolve_online_trailer(self, tmdb_id):
        if not tmdb_id: return None
        try:
            details_url = 'plugin://plugin.video.themoviedb.helper/?info=details&type=movie&tmdb_id=%s' % tmdb_id
            data = json_call('Files.GetDirectory', {
                'directory': details_url, 'media': 'video', 'properties': ['trailer']
            })
            if 'result' in data and 'files' in data['result']:
                trailer = data['result']['files'][0].get('trailer', '')
                if 'plugin.video.youtube' in trailer: return trailer
        except Exception: pass
        return None

    def get_local_trailers(self):
        unwatched = self._query_local_db(unwatched=True, limit=self.trailer_count * 2)
        valid_items = self._process_local_candidates(unwatched, limit=self.trailer_count)
        if len(valid_items) < self.trailer_count:
            remaining = self.trailer_count - len(valid_items)
            watched = self._query_local_db(unwatched=False, limit=remaining * 4)
            existing_ids = [x['dbid'] for x in valid_items]
            for item in self._process_local_candidates(watched, limit=remaining * 2):
                if len(valid_items) >= self.trailer_count: break
                if item['dbid'] not in existing_ids: valid_items.append(item)
        return valid_items

    def _query_local_db(self, unwatched, limit):
        filters = [{'field': 'hastrailer', 'operator': 'true', 'value': []}]
        if unwatched: filters.append({'field': 'playcount', 'operator': 'lessthan', 'value': '1'})
        result = json_call('VideoLibrary.GetMovies', {
            'properties': ['title', 'plot', 'year', 'rating', 'art', 'trailer'],
            'filter': {'and': filters},
            'sort': {'method': 'random'}, 
            'limits': {'end': limit} 
        })
        if 'result' in result and 'movies' in result['result']: return result['result']['movies']
        return []

    def _process_local_candidates(self, movies, limit):
        processed = []
        random.shuffle(movies)
        for item in movies:
            if len(processed) >= limit: break
            if str(item.get('movieid')) == str(self.dbid): continue
            title = '%s (Trailer)' % item.get('title', 'Unknown')
            trailer_url = item.get('trailer') 
            if trailer_url:
                li = xbmcgui.ListItem(title, offscreen=True)
                li.setInfo('video', {'Title': title, 'plot': item.get('plot', '')})
                li.setArt(item.get('art', {}))
                processed.append({'url': trailer_url, 'listitem': li, 'title': title, 'dbid': item.get('movieid')})
        return processed

    def get_random_intro(self):
        return self.get_smart_asset('', allow_fallback=True)

def run(params):
    CinemaMode(params).execute()