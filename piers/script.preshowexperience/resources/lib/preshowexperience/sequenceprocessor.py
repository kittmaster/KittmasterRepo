import os
import random
import re
import time
import datetime
import xbmc
import xbmcaddon
import xbmcgui
from . import database as DB
from . import sequence
from . import scrapers
from . import ratings
from . import actions
from . import util

TRAILER_FAIL_THRESHOLD = 10

# PlayableBase is implemented as a dict to be easily serializable to JSON
class PlayableBase(dict):
    type = None

    @property
    def module(self):
        if hasattr(self, '_module'):
            return self._module

    def fromModule(self, module):
        self._module = module
        self['module'] = module._type
        return self

class Playable(PlayableBase):
    type = None

    def __init__(self):
        self['from'] = -1
        
    @property
    def path(self):
        return self['path']
        
    def setFrom(self, pos):
        self['from'] = pos

    def __repr__(self):
        return '{0}: {1}'.format(self.type, repr(self.path))

class PlayableQueue(PlayableBase):
    pass

class Image(Playable):
    type = 'IMAGE'

    def __init__(self, path, duration=10, set_number=0, set_id=None, fade=0, *args, **kwargs):
        Playable.__init__(self, *args, **kwargs)
        self['path'] = path
        self['duration'] = duration
        self['setNumber'] = set_number
        self['setID'] = set_id
        self['fade'] = fade

    def __repr__(self):
        return 'IMAGE ({0}s): {1}'.format(self.duration, repr(self.path))

    @property
    def setID(self):
        return self['setID']

    @property
    def duration(self):
        return self['duration']

    @duration.setter
    def duration(self, val):
        self['duration'] = val

    @property
    def setNumber(self):
        return self['setNumber']

    @property
    def fade(self):
        return self['fade']

class Song(Playable):
    type = 'SONG'

    def __init__(self, path, duration=0, *args, **kwargs):
        self['path'] = path
        self['duration'] = duration
        Playable.__init__(self, *args, **kwargs)

    @property
    def duration(self):
        return self['duration']

    @property
    def durationInt(self):
        return int(self['duration'])

class ImageQueue(PlayableQueue):
    type = 'IMAGE.QUEUE'

    def __init__(self, handler, s_item, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self._handler = handler
        self.sItem = s_item
        duration = s_item.getLive('duration') 
        # Check if the duration is an integer
        if isinstance(duration, int):
            # If it's an integer, assume it's in minutes and convert to seconds
            self.maxDuration = duration * 60
            util.DEBUG_LOG('Duration is an integer. Max duration set to: {0} seconds'.format(self.maxDuration))
        else:
            # If it's a string, convert it to seconds using the method
            duration = self.convert_duration_to_seconds(duration)
            self.maxDuration = duration
            util.DEBUG_LOG('Duration is a string. Converted max duration to: {0} seconds'.format(self.maxDuration))
        self.pos = -1
        self.transition = None
        self.transitionDuration = 500
        self.music = None
        self.musicVolume = 85
        self.musicFadeIn = 3.0
        self.musicFadeOut = 3.0
        
    def convert_duration_to_seconds(self, duration_option):
        util.DEBUG_LOG('Conversion')
        time_mapping = {
            'minute': 60,
            'hour': 3600
        }

        parts = duration_option.split()
        if len(parts) == 2:
            quantity, unit = parts
            unit = unit.rstrip('s')
        else:
            quantity, unit = '1', parts[0]

        return int(quantity) * time_mapping.get(unit, 1)
        
    def __iadd__(self, other):
        for o in other:
            self.duration += o.duration

        self.queue += other
        return self

    def __contains__(self, images):
        paths = [i.path for i in self.queue]
        if isinstance(images, list):
            for i in images:
                if i.path in paths:
                    return True
        else:
            return images.path in paths

        return False

    def __repr__(self):
        return '{0}: {1}secs'.format(self.type, self.duration)

    def reset(self):
        self.pos = -1

    def size(self):
        return len(self.queue)

    @property
    def duration(self):
        return self.get('duration', 0)

    @duration.setter
    def duration(self, val):
        self['duration'] = val

    @property
    def queue(self):
        return self.get('queue', [])

    @queue.setter
    def queue(self, q):
        self['queue'] = q

    def current(self):
        return self.queue[self.pos]

    def add(self, image):
        util.DEBUG_LOG(f"Adding image to queue: {image.path}")
        self.queue.append(image)
        self.duration += image.duration  # Update the queue's duration

    def next(self, start=0, count=1, extend=False):
        #util.DEBUG_LOG(f"Retrieving next image from queue. Current position: {self.pos}")
        overtime = start and time.time() - start >= self.maxDuration
        util.DEBUG_LOG('Overtime : {0}'.format(overtime)) 
        util.DEBUG_LOG('Start : {0}'.format(start))
        util.DEBUG_LOG('time.time() : {0}'.format(time.time()))
        util.DEBUG_LOG('Max Duration : {0}'.format(self.maxDuration))
        if overtime and not self.current().setNumber:
            return None

        if count > 1:  # Handle big skips. Here we skip by slide sets
            self.pos += self.current().setNumber  # Move to the end of the current set

            for c in range(count - 1):
                while True:
                    if self.pos >= self.size() - 1:  # We need more slides
                        if not self._next():
                            break
                    else:
                        self.pos += 1

                    if not self.current().setNumber:  # We're at the end of a set
                        break

        if self.pos >= self.size() - 1:
            if extend or not overtime:
                return self._next()
            else:
                return None

        self.pos += 1

        return self.current()

    def _next(self):
        util.DEBUG_LOG('ImageQueue: Requesting next...')
        images = self._handler.next(self)
        if not images:
            util.DEBUG_LOG('ImageQueue: No next images')
            return None

        util.DEBUG_LOG('ImageQueue: {0} returned'.format(len(images)))
        self.queue += images
        self.pos += 1

        return self.current()

    def prev(self, count=1):
        if self.pos < 1:
            return None

        if count > 1:
            for c in range(count + 1):
                while self.pos > -1:
                    self.pos -= 1
                    if not self.current().setNumber:  # We're at the end of a set
                        break

            self.pos += 1

            return self.current()

        self.pos -= 1

        if self.pos < 0:
            self.pos = 0

        return self.current()

    def mark(self, image):
        if not image.setNumber and os.environ.get('isTestOrPreview') != 'True':
                util.DEBUG_LOG('ImageQueue: Marking image as watched')
                self._handler.mark(image)

    def onFirst(self):
        return self.pos == 0

    def onLast(self):
        return self.pos == self.size() - 1


class Video(Playable):
    type = 'VIDEO'

    def __init__(self, path, user_agent='', duration=0, set_id=None, title='', thumb='', volume=100):
        self['path'] = path
        self['userAgent'] = user_agent
        self['duration'] = duration
        self['setID'] = set_id
        self['title'] = title or os.path.splitext(os.path.basename(path))[0]
        self['thumb'] = thumb
        self['volume'] = volume

    @property
    def title(self):
        return self.get('title', '')

    @title.setter
    def title(self, val):
        self['title'] = val

    @property
    def thumb(self):
        return self.get('thumb', '')

    @thumb.setter
    def thumb(self, val):
        self['thumb'] = val

    @property
    def setID(self):
        return self['setID']

    @property
    def userAgent(self):
        return self['userAgent']

    @property
    def duration(self):
        return self.get('duration', 0)

    @property
    def volume(self):
        return self.get('volume', 100)

    @volume.setter
    def volume(self, val):
        self['volume'] = val


class VideoQueue(PlayableQueue):
    type = 'VIDEO.QUEUE'

    def __init__(self, handler, s_item, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self._handler = handler
        self.sItem = s_item
        self.duration = 0
        self['queue'] = []

    def __contains__(self, video):
        paths = [v.path for v in self.queue]
        return video.path in paths

    def __repr__(self):
        return '{0}: {1}secs'.format(self.type, self.duration)

    def append(self, video):
        self.duration += video.duration

        self['queue'].append(video)

    @property
    def queue(self):
        return self['queue']

    @queue.setter
    def queue(self, q):
        self['queue'] = q

    def mark(self, video):
        util.DEBUG_LOG('VideoQueue: Marking video as watched')
        self._handler.mark(video)

class Feature(Video):
    type = 'FEATURE'

    def __repr__(self):
        return ('FEATURE [ {0} ]:\n    Path: {1}\n    Rating: {2}\n    Year: {3}\n    Studios: {4}\n    ' +
                'Directors: {5}\n    Cast: {6}\n    Genres: {7}\n    Tags: {8}\n    Audio: {9}\n    Aspect Ratio: {10}').format(
            util.strRepr(self.title),
            util.strRepr(self.path),
            util.strRepr(self.rating),
            util.strRepr(self.year),
            ', '.join([util.strRepr(s) for s in self.studios]),
            ', '.join([util.strRepr(d) for d in self.directors]),
            ', '.join([util.strRepr(c['name']) for c in self.cast]),
            ', '.join([util.strRepr(g) for g in self.genres]),
            ', '.join([util.strRepr(t) for t in self.tags]),
            util.strRepr(self.audioFormat),
            util.strRepr(self.videoaspect)
        )

    @property
    def ID(self):
        return self.get('ID', '')

    @ID.setter
    def ID(self, val):
        self['ID'] = val

    @property
    def dbType(self):
        return self.get('dbType', '')

    @dbType.setter
    def dbType(self, val):
        self['dbType'] = val

    @property
    def rating(self):
        if not getattr(self, '_rating', None):
            ratingString = self.get('rating')
            if ratingString:
                self._rating = ratings.getRating(ratingString)
            else:
                self._rating = None
        return self._rating

    @rating.setter
    def rating(self, val):
        self['rating'] = val

    @property
    def genres(self):
        return self.get('genres', [])

    @genres.setter
    def genres(self, val):
        self['genres'] = val

    @property
    def tags(self):
        return self.get('tags', [])

    @tags.setter
    def tags(self, val):
        self['tags'] = val

    @property
    def studios(self):
        return self.get('studio', [])

    @studios.setter
    def studios(self, val):
        self['studio'] = val

    @property
    def directors(self):
        return self.get('director', [])

    @directors.setter
    def directors(self, val):
        self['director'] = val

    @property
    def cast(self):
        return self.get('cast', [])

    @cast.setter
    def cast(self, val):
        self['cast'] = val

    @property
    def featuretitle(self):
        return self.get('featuretitle', '')

    @featuretitle.setter
    def featuretitle(self, val):
        self['featuretitle'] = val   

    @property
    def videoaspect(self):
        return self.get('videoaspect', '')

    @videoaspect.setter
    def videoaspect(self, val):
        self['videoaspect'] = val   

    @property
    def audioFormat(self):
        return self.get('audioFormat', '')

    @audioFormat.setter
    def audioFormat(self, val):
        self['audioFormat'] = val

    @property
    def codec(self):
        return self.get('codec', '')

    @codec.setter
    def codec(self, val):
        self['codec'] = val

    @property
    def channels(self):
        return self.get('channels', '')

    @channels.setter
    def channels(self, val):
        self['channels'] = val

    @property
    def thumb(self):
        return self.get('thumbnail', '')

    @thumb.setter
    def thumb(self, val):
        self['thumbnail'] = val

    @property
    def runtime(self):
        return self.get('runtime', '')

    @runtime.setter
    def runtime(self, val):
        self['runtime'] = val

    @property
    def year(self):
        return self.get('year', '')

    @year.setter
    def year(self, val):
        self['year'] = val

    @property
    def durationMinutesDisplay(self):
        if not self.runtime:
            return

        sec = self.runtime % (24 * 3600)
        hour = sec // 3600
        sec %= 3600
        min = sec // 60
        sec %= 60
        return "%01d:%02d:%02d" % (hour, min, sec)


class Action(dict):
    type = 'ACTION'

    def __init__(self, processor, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.processor = processor
        self['path'] = processor.path

    def __repr__(self):
        return '{0}: {1} - {2}'.format(self.type, repr(self['path']), self.processor)

    def run(self):
        self.processor.run()

class Goto(Playable):
    type = 'GOTO'

    def __init__(self, command, *args, **kwargs):
        util.DEBUG_LOG('[Goto] {0}'.format(command.condition))
        self['command'] = command.command
        self['arg'] = command.arg
        self['condition'] = command.condition
        self['duration'] = command.duration
        self['timeOfDay'] = command.timeOfDay
        self['started'] = 0
        self['until'] = 0
        Playable.__init__(self, *args, **kwargs)

    def __repr__(self):
        return '{0}: {1} {2} - {3} duration {4} time of day {5}'.format(self.type, self['command'], self['arg'], self['condition'], self['duration'], self['timeOfDay'])

    def run(self):
        now = time.time()
        if self['started'] == 0:
            self['started'] = now
            if self['condition'] == 'feature.duration':
                self['until'] = now + ( self['duration'] * 60 )
            elif self['condition'] == 'feature.timeofday':
                if str(self['timeOfDay']).find(':') != -1:
                    n = datetime.datetime.fromtimestamp(now)
                    v = datetime.datetime.strptime(self['timeOfDay'], '%I:%M %p')
                    s = n.strftime('%m/%d/%Y')
                    s = s + ' ' + v.strftime('%I:%M') + ':00' + ' ' + v.strftime('%p')
                    r = datetime.datetime.strptime(s, '%m/%d/%Y %I:%M:%S %p')
                    tod = int(r.strftime('%s'))
                    if tod < now:
                        # Given value is next day => add 24 hours
                        tod = tod + (24 * 60 * 60)
                else:
                    tod = now
                self['until'] = tod
            util.DEBUG_LOG('Starting the loop at {0} with condition {1} until {2}'.format(str(now), self['condition'], self['until']))
        if self['until'] > 0 and now >= self['until']:
                util.DEBUG_LOG('Stopping the loop as the duration or time of day is reached')
                self['until'] = 0
                return 0
        if self['command'] == 'back':
            return self['arg'] * -1
        elif self['command'] == 'skip':
            return self['arg']        
        
class FeatureHandler:
    @DB.session
    def getRatingBumper(self, sItem, feature, image=False):
        try:
            if not feature.rating:
                return None

            if sItem.getLive('ratingStyleSelection') == 'style':
                return DB.RatingsBumpers.select().where(
                    (DB.RatingsBumpers.system == feature.rating.system) &
                    (DB.RatingsBumpers.name == feature.rating.name) &
                    (DB.RatingsBumpers.isImage == image) &
                    (DB.RatingsBumpers.style == sItem.getLive('ratingStyle'))
                )[0]

            else:
                return random.choice(
                    [
                        x for x in DB.RatingsBumpers.select().where(
                            (DB.RatingsBumpers.system == feature.rating.system) &
                            (DB.RatingsBumpers.name == feature.rating.name) &
                            (DB.RatingsBumpers.isImage == image)
                        )
                    ]
                )
        except IndexError:
            return None

    def __call__(self, caller, sItem):
        count = sItem.getLive('count')

        util.DEBUG_LOG('[{0}] x {1}'.format(sItem.typeChar, count))

        features = caller.getNextFeatures(count)

        playables = []
        mediaType = sItem.getLive('ratingBumper')

        for f in features:
            f.fromModule(sItem)
            f.volume = sItem.getLive('volume')
            bumper = None
            if mediaType == 'video':
                bumper = self.getRatingBumper(sItem, f)
                if bumper:
                    playables.append(Video(bumper.path, volume=sItem.getLive('volume')).fromModule(sItem))
                    util.DEBUG_LOG('    - Video Rating: {0}'.format(repr(bumper.path)))
            if mediaType == 'image' or mediaType == 'video' and not bumper:
                bumper = self.getRatingBumper(sItem, f, image=True)
                if bumper:
                    playables.append(Image(bumper.path, duration=8, fade=1000).fromModule(sItem))
                    util.DEBUG_LOG('    - Image Rating: {0}'.format(repr(bumper.path)))
            playables.append(f)
            
        return playables

class TriviaHandler:
    def __init__(self):
        pass

    def __call__(self, caller, sItem):
        duration = sItem.getLive('duration')
        util.DEBUG_LOG('[{0}] {1}m'.format(sItem.typeChar, duration))
        queue = ImageQueue(self, sItem).fromModule(sItem)
        queue.transition = sItem.getLive('transition')
        queue.transitionDuration = sItem.getLive('transitionDuration')

        for slides in self.getTriviaImages(sItem):
            queue += slides

        ret = []

        if queue.duration:
            ret.append(queue)

        self.addMusic(sItem, queue)

        return ret

    @DB.session
    def addMusic(self, sItem, queue):
        mode = sItem.getLive('music')
        if mode == 'off':
            return

        if mode == 'content':
            queue.music = [Song(s.path, s.duration) for s in DB.Song.select().order_by(DB.fn.Random())]
        elif mode == 'dir':
            path = sItem.getLive('musicDir')
            if not path:
                return

            import mutagen
            mutagen.setFileOpener(util.vfs.File)

            queue.music = []
            for p in util.listFilePaths(path):
                try:
                    data = mutagen.File(p)
                except:
                    data = None
                    util.ERROR()

                d = 0
                if data:
                    d = data.info.length
                queue.music.append(Song(p, d))

            random.shuffle(queue.music)
        elif mode == 'file':
            path = sItem.getLive('musicFile')
            if not path:
                return

            import mutagen
            mutagen.setFileOpener(util.vfs.File)

            data = mutagen.File(path)
            d = 0
            if data:
                d = data.info.length
            queue.music = [Song(path, d)]

        duration = sum([s.duration for s in queue.music])

        if duration:  # Maybe they were all zero - we'll be here forever :)
            while duration < queue.duration:
                for i in range(len(queue.music)):
                    song = queue.music[i]
                    duration += song.duration
                    queue.music.append(song)
                    if duration >= queue.duration:
                        break

        queue.musicVolume = util.getSettingDefault('trivia.musicVolume')
        queue.musicFadeIn = util.getSettingDefault('trivia.musicFadeIn')
        queue.musicFadeOut = util.getSettingDefault('trivia.musicFadeOut')

    @DB.session
    
    def extract_directory(path):
        util.DEBUG_LOG('Content Full Path: {0}'.format(path))
        if '@' in path:
            result = path.split('@')[1]
        elif '//' in path:
            result = path.rsplit('//', 1)[1]
        else:
            result = path
        return result
        
    def getTriviaImages(self, sItem): 
        util.DEBUG_LOG('Select Trivia : {0}'.format(sItem.getLive('triviaSelect')))
        if sItem.getLive('triviaSelect') == 'Directory':
            triviadirectory = TriviaHandler.extract_directory(sItem.getLive('triviaDir'))
            contentPath = util.getSettingDefault('content.path')
            contentPath = TriviaHandler.extract_directory(contentPath) + 'Trivia/'

            util.DEBUG_LOG('Content Full Path: {0}'.format(contentPath))
            util.DEBUG_LOG('Trivia Full Directory: {0}'.format(triviadirectory))

            triviadirectory = triviadirectory.replace(contentPath, '')
            util.DEBUG_LOG('Final Trivia Directory: {0}'.format(triviadirectory))
            
        else:
            triviadirectory = ''
            util.DEBUG_LOG('Final Trivia Directory: {0}'.format(triviadirectory))
        
        clue = sItem.getLive('cDuration')
        durations = (
            sItem.getLive('aDuration'),
            clue, clue, clue, clue, clue, clue, clue, clue, clue, clue,
            sItem.getLive('qDuration')
        )  
        # Calculate the date 3 months ago from now
        trivia_refresh_period = datetime.datetime.now() - datetime.timedelta(days=90)
        util.DEBUG_LOG('Trivia Refresh Time: {0}'.format(trivia_refresh_period))

        for trivia in DB.Trivia.select().where(DB.Trivia.accessed < trivia_refresh_period).order_by(DB.fn.Random()):
            if triviadirectory in str(trivia.answerPath):
                yield self.createTriviaImages(sItem, trivia, durations)

        # Grab the oldest 4 trivias, shuffle and yield... repeat
        pool = []
        for trivia in DB.Trivia.select().where(DB.Trivia.accessed >= trivia_refresh_period).order_by(DB.Trivia.accessed):
            pool.append(trivia)

            if len(pool) > 3:
                random.shuffle(pool)
                for t in pool:
                    yield self.createTriviaImages(sItem, t, durations)
                pool = []

        if pool:
            random.shuffle(pool)
            for t in pool:
                yield self.createTriviaImages(sItem, t, durations)  

    def createTriviaImages(self, sItem, trivia, durations):
        clues = [getattr(trivia, 'cluePath{0}'.format(x)) for x in range(9, -1, -1)]
        paths = [trivia.answerPath] + clues + [trivia.questionPath]
        # util.DEBUG_LOG('paths: {0}'.format(paths))
        slides = []
        setNumber = 0
        for p, d in zip(paths, durations):
            if p:
                slides.append(Image(p, d, setNumber, trivia.TID).fromModule(sItem))
                setNumber += 1

        slides.reverse()  # Slides are backwards
        # util.DEBUG_LOG('slides: {0}'.format(slides))

        if len(slides) == 1:  # This is a still - set duration accordingly
            slides[0].duration = sItem.getLive('sDuration')

        return slides

    def next(self, image_queue):
        for slides in self.getTriviaImages(image_queue.sItem):
            if slides not in image_queue:
                return slides
        return None

    @DB.session
    def mark(self, image):        
        trivia = DB.Trivia.get(TID=image.setID)  
        trivia.accessed = datetime.datetime.now()
        trivia.save()

class SlideshowHandler:
    def __init__(self):
        pass
    
    def __call__(self, caller, sItem):
        duration = sItem.getLive('duration') 
        util.DEBUG_LOG('Duration : {0}'.format(duration)) 
        duration = self.convert_duration_to_seconds(duration)   
        util.DEBUG_LOG('Duration : {0}'.format(duration))         
        util.DEBUG_LOG('[{0}] {1}'.format(sItem.typeChar, duration))
        queue = ImageQueue(self, sItem).fromModule(sItem)
        queue.transition = sItem.getLive('transition')
        queue.transitionDuration = sItem.getLive('transitionDuration')

        for slides in self.getSlideshowImages(sItem):
            queue += slides

        ret = []
        util.DEBUG_LOG('queue.duration: {0}'.format(queue.duration))

        if queue.duration:
            ret.append(queue)

        self.addMusic(sItem, queue)

        return ret

    @DB.session
    def addMusic(self, sItem, queue):
        mode = sItem.getLive('music')
        if mode == 'off':
            return

        if mode == 'content':
            queue.music = [Song(s.path, s.duration) for s in DB.Song.select().order_by(DB.fn.Random())]
        elif mode == 'dir':
            path = sItem.getLive('musicDir')
            if not path:
                return

            import mutagen
            mutagen.setFileOpener(util.vfs.File)

            queue.music = []
            for p in util.listFilePaths(path):
                try:
                    data = mutagen.File(p)
                except:
                    data = None
                    util.ERROR()

                d = 0
                if data:
                    d = data.info.length
                queue.music.append(Song(p, d))

            random.shuffle(queue.music)
        elif mode == 'file':
            path = sItem.getLive('musicFile')
            if not path:
                return

            import mutagen
            mutagen.setFileOpener(util.vfs.File)

            data = mutagen.File(path)
            d = 0
            if data:
                d = data.info.length
            queue.music = [Song(path, d)]

        duration = sum([s.duration for s in queue.music])

        if duration:  # Maybe they were all zero - we'll be here forever :)
            while duration < queue.duration:
                for i in range(len(queue.music)):
                    song = queue.music[i]
                    duration += song.duration
                    queue.music.append(song)
                    if duration >= queue.duration:
                        break

        queue.musicVolume = util.getSettingDefault('slideshow.musicVolume')
        queue.musicFadeIn = util.getSettingDefault('slideshow.musicFadeIn')
        queue.musicFadeOut = util.getSettingDefault('slideshow.musicFadeOut')

    @DB.session    
    def getSlideshowImages(self, sItem):        
        util.DEBUG_LOG('Select Slideshow : {0}'.format(sItem.getLive('slideshowSelect')))
        slideshow_order = sItem.getLive('slideshoworder')
        sDuration = sItem.getLive('sDuration')
        util.DEBUG_LOG('Slide Duration: {0}'.format(sDuration))
        sDuration = self.convert_duration_to_seconds(sDuration)
        util.DEBUG_LOG('Slide Duration: {0}'.format(sDuration))
        durations = (
            sDuration,
            sDuration
        )
        
        if sItem.getLive('slideshowSelect') == 'Directory':
            slideshowdirectory = SlideshowHandler.extract_directory(sItem.getLive('slideshowDir'))
            contentPath = util.getSettingDefault('content.path')
            contentPath = SlideshowHandler.extract_directory(contentPath) + 'Slideshow/'

            util.DEBUG_LOG('Content Full Path: {0}'.format(contentPath))
            util.DEBUG_LOG('Slideshow Full Directory: {0}'.format(slideshowdirectory))

            slideshowdirectory = slideshowdirectory.replace(contentPath, '')
            util.DEBUG_LOG('Final Slideshow Directory: {0}'.format(slideshowdirectory))
            
            if slideshow_order == 'Alphabetical':
                for slidesimages in DB.Slideshow.select().where(DB.Slideshow.slidePath.contains(slideshowdirectory)).order_by(DB.Slideshow.slidePath):
                    yield self.createSlideshowImages(sItem, slidesimages, durations)
            elif slideshow_order == 'Random':
                for slidesimages in DB.Slideshow.select().where(DB.Slideshow.slidePath.contains(slideshowdirectory)).order_by(DB.fn.Random()):
                    yield self.createSlideshowImages(sItem, slidesimages, durations)            
        else:
            slideshowdirectory = ''
            util.DEBUG_LOG('Final Slideshow Directory: {0}'.format(slideshowdirectory))                   
            if slideshow_order == 'Alphabetical':
                for slidesimages in DB.Slideshow.select().order_by(DB.Slideshow.slidePath):
                    yield self.createSlideshowImages(sItem, slidesimages, durations)
            elif slideshow_order == 'Random':
                for slidesimages in DB.Slideshow.select().order_by(DB.fn.Random()):
                    yield self.createSlideshowImages(sItem, slidesimages, durations)

    def convert_duration_to_seconds(self, duration_option):
        util.DEBUG_LOG('Conversion')
        time_mapping = {
            'minute': 60,
            'hour': 3600
        }

        parts = duration_option.split()
        if len(parts) == 2:
            quantity, unit = parts
            unit = unit.rstrip('s')
        else:
            quantity, unit = '1', parts[0]

        return int(quantity) * time_mapping.get(unit, 1)
        
    def extract_directory(path):
        util.DEBUG_LOG('Content Full Path: {0}'.format(path))
        if '@' in path:
            result = path.split('@')[1]
        elif '//' in path:
            result = path.rsplit('//', 1)[1]
        else:
            result = path
        return result

    def createSlideshowImages(self, sItem, slidesimages, durations):
        paths = [slidesimages.slidePath]
        #util.DEBUG_LOG('paths: {0}'.format(paths))
        slides = []
        setNumber = 0
        for p, d in zip(paths, durations):
            if p:
                slides.append(Image(p, d, setNumber, slidesimages.TID).fromModule(sItem))
                setNumber += 1

        slides.reverse()  # Slides are backwards
        #util.DEBUG_LOG('slides: {0}'.format(slides))
        sDuration = sItem.getLive('sDuration')
        util.DEBUG_LOG('Slide Duration: {0}'.format(sDuration))
        sDuration = self.convert_duration_to_seconds(sDuration)
        slides[0].duration = sDuration

        return slides
        
    def convert_duration_to_seconds(self, duration_option):
        util.DEBUG_LOG('Conversion')
        time_mapping = {
            'minute': 60,
            'hour': 3600
        }

        parts = duration_option.split()
        if len(parts) == 2:
            quantity, unit = parts
            unit = unit.rstrip('s')
        else:
            quantity, unit = '1', parts[0]

        return int(quantity) * time_mapping.get(unit, 1)
        
    def next(self, image_queue):
        for slides in self.getSlideshowImages(image_queue.sItem):
            if slides not in image_queue:
                return slides
        return None
        
    def mark(self, image):
        return None
        
class TrailerHandler:
    def __init__(self):
        self.caller = None
        self.sItem = None

    def __call__(self, caller, sItem):
        self.caller = caller
        self.sItem = sItem

        source = sItem.getLive('source')
        count = sItem.getLive('count')

        playables = []
        if source == 'content':
            scrapers.setContentPath(self.caller.contentPath)
            util.DEBUG_LOG('[{0}] {1} x {2}'.format(self.sItem.typeChar, source, count))
            scrapersList = (sItem.getLive('scrapers') or '').split(',')
            if util.getSettingDefault('trailer.preferUnwatched'):
                scrapersInfo = [(s.strip(), True, False) for s in scrapersList]
                scrapersInfo += [(s.strip(), False, True) for s in scrapersList]
            else:
                scrapersInfo = [(s.strip(), True, True) for s in scrapersList]

            for scraper, unwatched, watched in scrapersInfo:
                util.DEBUG_LOG('    - [{0}]'.format(scraper))
                playables += self.scraperHandler(scraper, count, unwatched=unwatched, watched=watched)
                count -= min(len(playables), count)
                if count <= 0:
                    break

        elif source == 'dir' or source == 'content':
            playables = self.dirHandler(sItem)
        elif source == 'file':
            playables = self.fileHandler(sItem)

        if not playables:
            util.DEBUG_LOG('    - NOT SHOWING')

        return playables

    def _getTrailersFromDBRating(self, source, watched=False):
        ratingLimitMethod = self.sItem.getLive('ratingLimit')
        false = False

        where = [
            DB.Trailers.source == source,
            DB.Trailers.broken == false,
            DB.Trailers.watched == watched
        ]

        if self.sItem.getLive('order') == 'newest':
            util.DEBUG_LOG('    - Order: Newest')
            orderby = [
                DB.Trailers.release.desc(),
                DB.Trailers.date
            ]
        else:
            util.DEBUG_LOG('    - Order: Random')
            orderby = [
                DB.fn.Random()
            ]

        if ratingLimitMethod and ratingLimitMethod != 'none':
            if ratingLimitMethod == 'max':
                maxr = ratings.getRating(self.sItem.getLive('ratingMax').replace('.', ':', 1))
                for t in DB.Trailers.select().where(*where).order_by(*orderby):
                    if ratings.getRating(t.rating).value <= maxr.value:
                        yield t
            elif self.caller.ratings:
                minr = min(self.caller.ratings, key=lambda x: x.value)
                maxr = max(self.caller.ratings, key=lambda x: x.value)

                for t in DB.Trailers.select().where(*where).order_by(*orderby):
                    if minr.value <= ratings.getRating(t.rating).value <= maxr.value:
                        yield t
        else:
            for t in DB.Trailers.select().where(*where).order_by(*orderby):
                yield t

    def _getTrailersFromDBGenre(self, source, watched=False):
        if self.sItem.getLive('limitGenre') and self.caller.genres:
            for t in self._getTrailersFromDBRating(source, watched=watched):
                if any(x in self.caller.genres for x in (t.genres or '').split(',')):
                    yield t
        else:
            for t in self._getTrailersFromDBRating(source, watched=watched):
                yield t

    def getTrailersFromDB(self, source, count, watched=False):
        # Get trailers + a few to make the random more random
        quality = self.sItem.getLive('quality')

        poolSize = count + 5
        trailers = []
        pool = []
        ct = 0
        fail = 0
        for t in self._getTrailersFromDBGenre(source, watched=watched):
            pool.append(t)
            ct += 1
            if ct >= poolSize:
                random.shuffle(pool)

                for t in pool:
                    t = self.updateTrailer(t, source, quality)
                    if t:
                        fail = 0
                        trailers.append(t)
                        if len(trailers) >= count:
                            break
                    else:
                        fail += 1
                        if fail >= TRAILER_FAIL_THRESHOLD:
                            util.DEBUG_LOG('Exceeded trailer fail threshold - aborting.')
                            break
                pool = []
                ct = 0

            if len(trailers) >= count or fail >= TRAILER_FAIL_THRESHOLD:
                break
        else:
            if pool:
                for t in pool:
                    t = self.updateTrailer(t, source, quality)
                    if t:
                        fail = 0
                        trailers.append(t)
                        if len(trailers) >= count:
                            break
                    else:
                        fail += 1
                        if fail >= TRAILER_FAIL_THRESHOLD:
                            util.DEBUG_LOG('Exceeded trailer fail threshold - aborting.')
                            break

        return [
            Video(
                trailer.url,
                trailer.userAgent,
                title=trailer.title,
                thumb=trailer.thumb,
                volume=self.sItem.getLive('volume')
            ).fromModule(self.sItem) for trailer in trailers
        ]

    def updateTrailer(self, t, source, quality):
        try:
            url = scrapers.getPlayableURL(t.WID.split(':', 1)[-1], quality, source, t.url) or ''
        except:
            util.ERROR()
            url = ''

        watched = t.watched

        if os.environ.get('isTestOrPreview') != 'True':
            t.watched = True
            t.date = datetime.datetime.now()
        t.url = url
        t.broken = not url
        t.save()
        if not t.broken:
            util.DEBUG_LOG(
                '    - {0}: {1} ({2:%Y-%m-%d}){3}'.format(repr(t.title).lstrip('u').strip("'"), t.rating, t.release, watched and ' - WATCHED' or '')
            )
            return t

        return None

    def updateTrailers(self, source):
        try:
            self._updateTrailers(source)
        except:
            util.ERROR()

    def _updateTrailers(self, source):
        trailers = scrapers.updateTrailers(source)
        if trailers:
            total = len(trailers)
            util.DEBUG_LOG('    - Received {0} trailers'.format(total))
            total = float(total)
            ct = 0

            for t in trailers:
                try:
                    DB.Trailers.get(DB.Trailers.WID == t.ID)
                except DB.peewee.DoesNotExist:
                    ct += 1
                    url = t.getStaticURL()
                    DB.Trailers.create(
                        WID=t.ID,
                        source=source,
                        watched=False,
                        title=t.title,
                        url=url,
                        userAgent=t.userAgent,
                        rating=str(t.rating),
                        genres=','.join(t.genres),
                        thumb=t.thumb,
                        release=t.release or datetime.date(1900, 1, 1)
                    )

            util.DEBUG_LOG('    - {0} trailers added to database'.format(ct))

    @DB.session
    def scraperHandler(self, source, count, unwatched=False, watched=False):
        trailers = []

        if unwatched:
            self.updateTrailers(source)
            util.DEBUG_LOG('    - Searching un-watched trailers')
            trailers += self.getTrailersFromDB(source, count)
            if not watched:
                return trailers

            count -= min(len(trailers), count)
            if count <= 0:
                return trailers

        if watched:
            util.DEBUG_LOG('    - Searching watched trailers')
            trailers += self.getTrailersFromDB(source, count, watched=True)

        return trailers

    def dirHandler(self, sItem):
        count = sItem.getLive('count')

        path = sItem.getLive('dir')
        util.DEBUG_LOG('[{0}] Directory x {1}'.format(sItem.typeChar, count))

        if not path:
            util.DEBUG_LOG('    - Empty path!')
            return []

        try:
            files = [f for f in util.vfs.listdir(path) if os.path.splitext(f)[-1].lower() in util.videoExtensions]
            files = random.sample(files, min((count, len(files))))
            [util.DEBUG_LOG('    - Using: {0}'.format(repr(f))) for f in files] or util.DEBUG_LOG('    - No matching files')
            return [Video(util.pathJoin(path, p), volume=sItem.getLive('volume')).fromModule(sItem) for p in files]
        except:
            util.ERROR()
            return []

    def fileHandler(self, sItem):
        path = sItem.getLive('file')
        if not path:
            return []

        util.DEBUG_LOG('[{0}] File: {1}'.format(sItem.typeChar, repr(path)))
        return [Video(path, volume=sItem.getLive('volume')).fromModule(sItem)]

class VideoBumperHandler:
    def __init__(self):
        self.caller = None
        self.handlers = {
            'preshow': self.preshow,
            'sponsors': self.sponsors,
            'commercials': self.commercials,            
            'countdown': self.countdown,
            'courtesy': self.courtesy,
            'feature.intro': self.featureIntro,
            'feature.outro': self.featureOutro,
            'intermission': self.intermission,
            'short.film': self.shortFilm,
            'theater.intro': self.theaterIntro,
            'theater.outro': self.theaterOutro,
            'trailers.intro': self.trailersIntro,
            'trailers.outro': self.trailersOutro,
            'trivia.intro': self.triviaIntro,
            'trivia.outro': self.triviaOutro,
            'dir': self.dir,
            'file': self.file
        }
        self.default_youtube_links = {
            'preshow': 'plugin://plugin.video.youtube/play/?video_id=Duoy0gd-PAU',
            'sponsors': 'plugin://plugin.video.youtube/play/?video_id=9bVilFsFlRk',
            'commercials': 'plugin://plugin.video.youtube/play/?video_id=Q70dMEHV-Vo',     
            'countdown': 'plugin://plugin.video.youtube/play/?video_id=5ivgwp8AYac',
            'courtesy': 'plugin://plugin.video.youtube/play/?video_id=dwEIxiMfQJY',
            'feature.intro': 'plugin://plugin.video.youtube/play/?video_id=q__lEWLxSm8',
            'feature.outro': 'plugin://plugin.video.youtube/play/?video_id=Kpm8FmBWSw0',
            'intermission': 'plugin://plugin.video.youtube/play/?video_id=-EmyFEamvN8',
            'short.film': 'plugin://plugin.video.youtube/play/?video_id=-EmyFEamvN8',
            'theater.intro': 'plugin://plugin.video.youtube/play/?video_id=AA6u3aO1oDM',
            'theater.outro': 'plugin://plugin.video.youtube/play/?video_id=KTYDIiUffZw',
            'trailers.intro': 'plugin://plugin.video.youtube/play/?video_id=oFoY0m1T_nk',
            'trailers.outro': 'plugin://plugin.video.youtube/play/?video_id=c6ys96aZ0sQ',
            'trivia.intro': 'plugin://plugin.video.youtube/play/?video_id=VmIyAIo4k-0',
            'trivia.outro': 'plugin://plugin.video.youtube/play/?video_id=5BesAADNV6M'
        }

    def __call__(self, caller, sItem):
        self.caller = caller
        util.DEBUG_LOG('[{0}] {1}'.format(sItem.typeChar, repr(sItem.display())))

        if not sItem.vtype:
            util.DEBUG_LOG('    - {0}'.format('No bumper type - SKIPPING'))
            return []

        playables = self.handlers[sItem.vtype](sItem)
        if playables:
            if sItem.vtype == 'dir':
                util.DEBUG_LOG('    - {0}'.format(' x {0}'.format(sItem.count) or ''))
        else:
            util.DEBUG_LOG('    - {0}'.format('NOT SHOWING'))

        return playables

    @DB.session
    def defaultHandler(self, sItem):

        if sItem.random:
            util.DEBUG_LOG('    - Random')

            bumpers = [x for x in DB.VideoBumpers.select().where((DB.VideoBumpers.type == sItem.vtype))]
            bumpers = random.sample(bumpers, min(sItem.count, len(bumpers)))
            bumpers = [Video(bumper.path, volume=sItem.getLive('volume')).fromModule(sItem) for bumper in bumpers]

            if not bumpers:
                util.DEBUG_LOG('    - No matches! Using default YouTube link.')
                default_link = self.default_youtube_links.get(sItem.vtype)
                if default_link:
                    return [Video(default_link, volume=sItem.getLive('volume')).fromModule(sItem)]

            return bumpers

        else:
            util.DEBUG_LOG('    - Via source')
            if sItem.source:
                return [Video(sItem.source, volume=sItem.getLive('volume')).fromModule(sItem)]
            else:
                util.DEBUG_LOG('    - Empty path!')

        return []

    def countdown(self, sItem):
        return self.defaultHandler(sItem)

    def courtesy(self, sItem):
        return self.defaultHandler(sItem)

    def featureIntro(self, sItem):
        return self.defaultHandler(sItem)

    def featureOutro(self, sItem):
        return self.defaultHandler(sItem)

    def intermission(self, sItem):
        return self.defaultHandler(sItem)
        
    def sponsors(self, sItem):
        return self.defaultHandler(sItem)        

    def commercials(self, sItem):
        return self.defaultHandler(sItem)

    def preshow(self, sItem):
        return self.defaultHandler(sItem)
        
    def shortFilm(self, sItem):
        return self.defaultHandler(sItem)

    def theaterIntro(self, sItem):
        return self.defaultHandler(sItem)

    def theaterOutro(self, sItem):
        return self.defaultHandler(sItem)

    def trailersIntro(self, sItem):
        return self.defaultHandler(sItem)

    def trailersOutro(self, sItem):
        return self.defaultHandler(sItem)

    def triviaIntro(self, sItem):
        return self.defaultHandler(sItem)

    def triviaOutro(self, sItem):
        return self.defaultHandler(sItem)

    def file(self, sItem):
        if sItem.file:
            return [Video(sItem.file, volume=sItem.getLive('volume')).fromModule(sItem)]
        else:
            return []

    def dir(self, sItem):
        if not sItem.dir:
            return []

        try:
            files = util.vfs.listdir(sItem.dir)
            if sItem.random:
                files = random.sample(files, min((sItem.count, len(files))))
            else:
                files = files[:sItem.count]

            return [Video(util.pathJoin(sItem.dir, p), volume=sItem.getLive('volume')).fromModule(sItem) for p in files]
        except:
            util.ERROR()
            return []

class AudioFormatHandler:
    def __init__(self):
        self.default_youtube_links = {
            'Auro-3D': 'plugin://plugin.video.youtube/play/?video_id=4uUy-rhIrw4',
            'Datasat': 'plugin://plugin.video.youtube/play/?video_id=O6Jiv_U5rPU',
            'Dolby Atmos': 'plugin://plugin.video.youtube/play/?video_id=pd_6WN9GVtQ',
            'Dolby Digital': 'plugin://plugin.video.youtube/play/?video_id=zwul5nW9xHU',
            'Dolby Digital Plus': 'plugin://plugin.video.youtube/play/?video_id=zwul5nW9xHU',
            'Dolby TrueHD': 'plugin://plugin.video.youtube/play/?video_id=77fAMqoYPPM',
            'DTS': 'plugin://plugin.video.youtube/play/?video_id=slDSieDA7EE',
            'DTS-HD Master Audio': 'plugin://plugin.video.youtube/play/?video_id=nU_lXddJPvE',
            'DTS-X': 'plugin://plugin.video.youtube/play/?video_id=qEbRNeOcf9c',
            'THX': 'plugin://plugin.video.youtube/play/?video_id=_s-6pSdoctI',
        }
    _atmosRegex = re.compile('atmos', re.IGNORECASE)
    _dtsxRegex = re.compile('dtsx', re.IGNORECASE)
    _auro3dRegex = re.compile('auro3d', re.IGNORECASE)      

    def _checkFileNameForFormat(self, feature):
        featureFileName = os.path.basename(feature.path)

        if re.search(self._atmosRegex, featureFileName):
            util.DEBUG_LOG('    - Detect: Used file path {0} to determine audio format is {1}'.format(repr(featureFileName), 'Dolby Atmos'))
            return 'Dolby Atmos'
        elif re.search(self._dtsxRegex, featureFileName):
            util.DEBUG_LOG('    - Detect: Used file path {0} to determine audio format is {1}'.format(repr(featureFileName), 'DTS-X'))
            return 'DTS-X'
        elif re.search(self._auro3dRegex, featureFileName):
            util.DEBUG_LOG('    - Detect: Used file path {0} to determine audio format is {1}'.format(repr(featureFileName), 'Auro-3D'))
            return 'Auro-3D'         
        else:
            util.DEBUG_LOG(
                '    - Detect: Looked at the file path {0} and decided to keep audio format {1}'.format(repr(featureFileName), repr(feature.audioFormat))
            )
            return feature.audioFormat

    @DB.session
    def __call__(self, caller, sItem):
        bumper = None
        method = sItem.getLive('method')
        fallback = sItem.getLive('fallback')
        format_ = sItem.getLive('format')

        util.DEBUG_LOG('[{0}] Method: {1} Fallback: {2} Format: {3}'.format(sItem.typeChar, method, fallback, format_))

        if method == 'af.detect':
            util.DEBUG_LOG('    - Detect')
            audioFormat = self._checkFileNameForFormat(caller.nextQueuedFeature)
            if audioFormat:
                try:
                    bumper = random.choice(
                        [x for x in DB.AudioFormatBumpers.select().where(
                            (DB.AudioFormatBumpers.format == audioFormat)
                        )]
                    )
                    util.DEBUG_LOG('    - Detect: Using bumper based on feature codec info ({0})'.format(repr(caller.nextQueuedFeature.title)))
                except IndexError:
                    util.DEBUG_LOG('    - Detect: No codec matches!')
            else:
                util.DEBUG_LOG('    - No feature audio format!')

        if (
            format_ and not bumper and (
                method == 'af.format' or (
                    method == 'af.detect' and fallback == 'af.format'
                )
            )
        ):
            util.DEBUG_LOG('    - Format')
            try:
                bumper = random.choice(
                    [x for x in DB.AudioFormatBumpers.select().where(
                        (DB.AudioFormatBumpers.format == format_)
                    )]
                )
                util.DEBUG_LOG('    - Format: Using bumper based on setting ({0})'.format(repr(caller.nextQueuedFeature.title)))
            except IndexError:
                util.DEBUG_LOG('    - Format: No matches!')
        if (
            sItem.getLive('file') and not bumper and (
                method == 'af.file' or (
                    method == 'af.detect' and fallback == 'af.file'
                )
            )
        ):
            util.DEBUG_LOG('    - File: Using bumper based on setting ({0})'.format(repr(caller.nextQueuedFeature.title)))
            return [Video(sItem.getLive('file'), volume=sItem.getLive('volume')).fromModule(sItem)]

        if bumper:
            return [Video(bumper.path, volume=sItem.getLive('volume')).fromModule(sItem)]
            
        if not bumper:
            util.DEBUG_LOG('    - No bumper found. Checking for default YouTube link.')
            # Use the detected audio format or the format specified in the settings
            audio_format_to_use = audioFormat if method == 'af.detect' else format_
            default_link = self.default_youtube_links.get(audio_format_to_use)

            if default_link:
                util.DEBUG_LOG('    - Using default YouTube link for {0}'.format(audio_format_to_use))
                return [Video(default_link, volume=sItem.getLive('volume')).fromModule(sItem)]
            else:
                util.DEBUG_LOG('    - No default YouTube link found for {0}'.format(audio_format_to_use))

        util.DEBUG_LOG('    - NOT SHOWING')
        return []


class ActionHandler:
    def __call__(self, caller, sItem):
        if not sItem.file:
            util.DEBUG_LOG('[{0}] NO PATH SET'.format(sItem.typeChar))
            return []

        util.DEBUG_LOG('[{0}] {1}'.format(sItem.typeChar, repr(sItem.file)))
        processor = actions.ActionFileProcessor(sItem.file)
        return [Action(processor)]


class SequenceProcessor:
    def __init__(self, sequence_path, db_path=None, content_path=None):
        DB.initialize(db_path)
        self.pos = -1
        self.size = 0
        self.sequence = []
        self.featureQueue = []
        self.playables = []
        self.genres = []
        self.contentPath = content_path
        self.lastFeature = None
        self._lastAction = None
        self.end = -1
        self.loadSequence(sequence_path)
        self.createDefaultFeature()

        self.beginningAction = None
        self.PreshowBeginningAction = None
        self.initialize_beginning_action()        
   
    def initialize_beginning_action(self):
        addon = xbmcaddon.Addon()
        PreshowBeginning = addon.getSetting('action.PreshowBeginning')
        #util.DEBUG_LOG('PreshowBeginning Status: {0}'.format(repr(PreshowBeginning)))
        if PreshowBeginning == 'true':
            actionFile = addon.getSetting('action.PreshowBeginning.file')
            if actionFile:
                self.PreshowBeginningAction = actions.ActionFileProcessor(actionFile) 
                self.PreshowBeginningAction.run()                
                util.DEBUG_LOG(f"Start of PreShow Action loaded from file: {actionFile}")
                #xbmc.sleep(5000)
      
    def atEnd(self, pos=None):
        if pos is None:
            pos = self.pos
        return pos >= self.end

    @property
    def nextQueuedFeature(self):
        return self.featureQueue and self.featureQueue[0] or self.lastFeature

    def getNextFeatures(self, count):
        features = self.featureQueue[:count]
        self.featureQueue = self.featureQueue[count:]
        if features:
            self.lastFeature = features[-1]
        return features

    def createDefaultFeature(self):
        self.defaultFeature = Feature('')
        self.defaultFeature.title = 'Default Feature'
        self.defaultFeature.rating = 'MPAA:NR'
        self.defaultFeature.audioFormat = 'Other'

    def addFeature(self, feature):
        if feature.genres:
            self.genres += feature.genres

        self.featureQueue.append(feature)

    @property
    def ratings(self):
        return [feature.rating for feature in self.featureQueue if feature.rating]

    def commandHandler(self, sItem):
        if sItem.condition == 'feature.queue=full' and not self.featureQueue:
            return 0
        if sItem.condition == 'feature.queue=empty' and self.featureQueue:
            return 0
        if sItem.command == 'back' and sItem.condition == 'feature.nbloops':
            if sItem.nbLoops > 0:
                sItem.nbLoops = sItem.nbLoops - 1
                if sItem.nbLoops == 0:
                    util.DEBUG_LOG('Stopping the loop as the number of loops is reached')
                    sItem.nbLoops = 0
                    return 0
                else:
                    return sItem.arg * -1
        if sItem.command == 'back' and ( sItem.condition == 'feature.duration' or sItem.condition == 'feature.timeofday' ):
            return Goto(sItem)
        if sItem.command == 'back':
            return sItem.arg * -1
        elif sItem.command == 'skip':
            return sItem.arg

    # SEQUENCE PROCESSING
    handlers = {
        'feature': FeatureHandler(),
        'trivia': TriviaHandler(),
        'slideshow': SlideshowHandler(),
        'trailer': TrailerHandler(),
        'video': VideoBumperHandler(),
        'audioformat': AudioFormatHandler(),
        'action': ActionHandler(),
        'command': commandHandler
    }

    def process(self):
        util.DEBUG_LOG('Processing sequence...')
        util.DEBUG_LOG('Feature count: {0}'.format(len(self.featureQueue)))
        util.DEBUG_LOG('Ratings: {0}'.format(', '.join([str(r) for r in self.ratings])))
        util.DEBUG_LOG('Genres: {0}'.format(repr(self.genres)))

        if self.featureQueue:
            util.DEBUG_LOG('\n\n' + '\n\n'.join([str(f) for f in self.featureQueue]) + '\n.')
        else:
            util.DEBUG_LOG('NO FEATURES QUEUED')

        self.playables = []
        pos = 0
        while pos < len(self.sequence):
            sItem = self.sequence[pos]

            if not sItem.enabled:
                util.DEBUG_LOG('[{0}] ({1}) DISABLED'.format(sItem.typeChar, repr(sItem.display())))
                pos += 1
                continue

            handler = self.handlers.get(sItem._type)

            if handler:
                if sItem._type == 'command':
                    offset = handler(self, sItem)
                    if type(offset) == int:
                        pos += offset
                        if offset:
                            continue
                    elif offset is not None:  # Add a check to ensure offset is not None
                        offset.setFrom(pos)
                        self.playables.append(offset)
                else:
                    playables = handler(self, sItem)
                    for p in playables:
                        if hasattr(p, 'setFrom'):
                            p.setFrom(pos)
                        self.playables.append(p)

            pos += 1
        self.playables.append(None)  # Keeps it from being empty until AFTER the last item
        self.end = len(self.playables) - 1

        util.DEBUG_LOG('Sequence processing finished')

    def loadSequence(self, sequence_path):
        self.sequence = sequence.loadSequence(sequence_path)

        if util.DEBUG:  # Dump some info
            util.DEBUG_LOG('')
            util.DEBUG_LOG('[- Non-Module Defaults -]')

            for sett in (
                'trivia.music', 'trivia.musicVolume', 'trivia.musicFadeIn', 'trivia.musicFadeOut',
                'trailer.preferUnwatched', 'trailer.ratingMax', 'rating.system.default'
            ):
                util.DEBUG_LOG('{0}: {1}'.format(sett, repr(util.getSettingDefault(sett))))

            util.DEBUG_LOG('')

            for si in self.sequence:
                util.DEBUG_LOG('[- {0} -]'.format(si._type))
                for e in si._elements:
                    util.DEBUG_LOG('{0}: {1}'.format(e['attr'], repr(si.getLive(e['attr']))))

                util.DEBUG_LOG('')

    def next(self):
        if self.atEnd():
            return None

        self.pos += 1
        playable = self.playables[self.pos]

        if playable and playable.type == 'ACTION':
            self._lastAction = playable

        return playable

    def prev(self):
        if self.pos > 0:
            self.pos -= 1

        playable = self.playables[self.pos]

        while playable.type == 'ACTION' and self.pos > 0:
            self.pos -= 1
            playable = self.playables[self.pos]

        return playable

    def upNext(self):
        if self.atEnd():
            return None

        pos = self.pos + 1
        playable = self.playables[pos]
        while not self.atEnd(pos) and playable and playable.type in ('ACTION', 'COMMAND', 'GOTO'):
            pos += 1
            playable = self.playables[pos]
        else:
            return playable

        return None

    def nextFeature(self):
        for i in range(self.pos + 1, len(self.playables) - 1):
            p = self.playables[i]
            if p.type == 'FEATURE':
                return p
        return None

    def lastAction(self):
        return self._lastAction
        
    def seekToFirstPlayableAtOffset(self, offset):
        pos = self.playables[self.pos]['from']
        pos += offset
        if pos < 0:
            pos = 0
        if pos > len(self.sequence) - 1:
            return None
        
        i = 0
        for p in self.playables:
            if p['from'] >= pos:
                self.pos = i - 1 # Position before the item that we want to go next as function next() will be called
                if self.pos < 0:
                    self.pos = 0
                return p
            i += 1
                
        return None