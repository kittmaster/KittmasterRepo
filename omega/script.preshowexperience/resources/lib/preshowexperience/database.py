import time
import datetime
import xbmc
import xbmcgui
import xbmcvfs
import os
import shutil
import re

try:
    datetime.datetime.strptime('0', '%H')
except TypeError:
    # Fix for datetime issues with XBMC/Kodi
    class new_datetime(datetime.datetime):
        @classmethod
        def strptime(cls, dstring, dformat):
            return datetime.datetime(*(time.strptime(dstring, dformat)[0:6]))

    # To fix an issue with threading ad strptime
    import _strptime # pylint: disable=W0611

    datetime.datetime = new_datetime

from peewee import *
from peewee import peewee
from . import util
from resources.lib import kodiutil
from . import content

DATABASE_VERSION = 0.2

fn = peewee.fn
DB = None
Settings = None
Song = None
Trivia = None
Slideshow = None                
AudioFormatBumpers = None
RatingsBumpers = None
VideoBumpers = None
RatingSystem = None
Rating = None
Trailers = None

def session(func):
    def inner(*args, **kwargs):
        try:
            DB.connect(reuse_if_open=True)
            with DB.atomic():
                return func(*args, **kwargs)
        finally:
            DB.close()
    return inner

def connect():
    DB.connect(reuse_if_open=True)

def close():
    DB.close()

def dummyCallback(*args, **kwargs):
    pass

def checkDBVersion(DB):
    setting = None
    try:
        setting = Settings.get(Settings.setting == 'dbversion')
        if float(setting.detail) < DATABASE_VERSION:
            raise ValueError("Database version is outdated")
    except (Settings.DoesNotExist, ValueError):
        if xbmcgui.Dialog().ok('PreShow Experience Update', 'Your database version is outdated and needs to be updated. This will require you to rescan your content.  If you see this message multiple times, please go into your PreShow settings and click "Reset content database.'):
            dbPath = DB.database
            DB.close()
            if setting:
                util.LOG('Migrating database from version {0} to {1}'.format(float(setting.detail), DATABASE_VERSION))
            dbDir = util.STORAGE_PATH
            watched_db_path = util.pathJoin(dbDir, 'watched.db')
            if util.vfs.exists(watched_db_path):
                util.LOG('Removing watched.db')
                xbmcvfs.delete(watched_db_path)
            tmdb_path = util.pathJoin(dbDir, 'tmdb.last')
            if util.vfs.exists(tmdb_path):
                xbmcvfs.delete(tmdb_path)
            imdb_path = util.pathJoin(dbDir, 'imdb.last')
            if util.vfs.exists(imdb_path):
                xbmcvfs.delete(imdb_path)
            tempseq_path = util.pathJoin(dbDir, 'temp.pseseq')
            if util.vfs.exists(tempseq_path):
                xbmcvfs.delete(tempseq_path)                
            
            os.remove(dbPath)

            # New code to update and rename sequence files
            from resources.lib import kodiutil
            contentPath = kodiutil.getPathSetting('content.path')
            if contentPath:
                updateAndRenameSequenceFiles(util.pathJoin(contentPath, 'Sequences'))

def updateAndRenameSequenceFiles(directory):
    # Loop through all files in the directory
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)

        # Ensure it's a file with .seq or .pseseq extension
        if os.path.isfile(file_path):
            try:
                if filename.endswith('.pseseq'):
                    # Change extension from .pseseq to .seq
                    new_filename = filename[:-7] + '.seq'
                    new_file_path = os.path.join(directory, new_filename)
                    os.rename(file_path, new_file_path)
                    file_path = new_file_path  # Update the file path for content modification

                
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()

                # Only replace if the specific text is found
                if ', "play3D": true' in content:
                    new_content = content.replace(', "play3D": true', '')

                    # Write the new content back to the file
                    with open(file_path, 'w', encoding='utf-8') as file:
                        file.write(new_content)

            except UnicodeDecodeError:
                print(f"Skipping file {file_path} due to encoding error.")
            except Exception as e:
                print(f"An error occurred while processing file {file_path}: {e}")

    print("Text removal and renaming completed.")
    
def initialize(path=None, callback=None):
    callback = callback or dummyCallback
    callback(None, 'Creating/updating database...')

    global DB, Settings, Song, Trivia, PreShowTrivia, Slideshow
    global AudioFormatBumpers, RatingsBumpers, VideoBumpers, RatingSystem, Rating, Trailers

    dbDir = path or util.STORAGE_PATH
    if not util.vfs.exists(dbDir):
        util.vfs.mkdirs(dbDir)

    dbPath = util.pathJoin(dbDir, 'content.db')
    dbExists = util.vfs.exists(dbPath)

    DB = peewee.SqliteDatabase(dbPath)
    DB.connect()

    class Settings(peewee.Model):
        id = peewee.AutoField()
        setting = peewee.CharField(unique=True)
        detail = peewee.CharField()

        class Meta:
            database = DB

    Settings.create_table(fail_silently=True)

    if dbExists:  # Only check version if we had a DB, otherwise we're creating it fresh
        checkDBVersion(DB)
    else:
        Settings.create(setting='dbversion', detail=str(DATABASE_VERSION))

    ###########################################################################################
    # Content
    ###########################################################################################
    class ContentBase(peewee.Model):
        name = peewee.CharField()
        movieid = peewee.CharField(null=True)
        accessed = peewee.DateTimeField(default=datetime.date(2024, 1, 1))
        pack = peewee.CharField(null=True)
        rating = peewee.CharField(null=True)
        genre = peewee.CharField(null=True)
        year = peewee.CharField(null=True)
        holiday = peewee.CharField(null=True) 
        tags = peewee.CharField(null=True) 
        
        class Meta:
            database = DB

    callback(' - Music')

    class Song(ContentBase):
        path = peewee.CharField(unique=True)
        duration = peewee.FloatField(default=0)

    Song.create_table(fail_silently=True)

    callback(' - Trivia')

    class Trivia(ContentBase):
        TID = peewee.CharField(unique=True)
        type = peewee.CharField()
        questionPath = peewee.CharField(unique=True, null=True)
        cluePath0 = peewee.CharField(unique=True, null=True)
        cluePath1 = peewee.CharField(unique=True, null=True)
        cluePath2 = peewee.CharField(unique=True, null=True)
        cluePath3 = peewee.CharField(unique=True, null=True)
        cluePath4 = peewee.CharField(unique=True, null=True)
        cluePath5 = peewee.CharField(unique=True, null=True)
        cluePath6 = peewee.CharField(unique=True, null=True)
        cluePath7 = peewee.CharField(unique=True, null=True)
        cluePath8 = peewee.CharField(unique=True, null=True)
        cluePath9 = peewee.CharField(unique=True, null=True)
        answerPath = peewee.CharField(unique=True, null=True)

    Trivia.create_table(fail_silently=True)
	
    callback(' - PreShow Trivia')

    class PreShowTrivia(ContentBase):
        TID = peewee.CharField(unique=True)
        type = peewee.CharField()
        setting = peewee.CharField()
        question = peewee.CharField(null=True)
        answer1 = peewee.CharField(null=True)
        answer2 = peewee.CharField(null=True)
        answer3 = peewee.CharField(null=True)
        answer4 = peewee.CharField(null=True)
        correct = peewee.CharField(null=True)
        image1 = peewee.CharField(null=True)
        image2 = peewee.CharField(null=True)
        image3 = peewee.CharField(null=True)
        image4 = peewee.CharField(null=True)
        extra0 = peewee.CharField(null=True)
        extra1 = peewee.CharField(null=True)
        extra2 = peewee.CharField(null=True)
        extra3 = peewee.CharField(null=True)
        extra4 = peewee.CharField(null=True)
        extra5 = peewee.CharField(null=True)
        extra6 = peewee.CharField(null=True)
        extra7 = peewee.CharField(null=True)
        extra8 = peewee.CharField(null=True)
        extra9 = peewee.CharField(null=True)
	
    PreShowTrivia.create_table(fail_silently=True)	

    callback(' - Slideshow')
    
    class Slideshow(ContentBase):
        type = peewee.CharField()
        TID = peewee.CharField(unique=True)
        slidePath = peewee.CharField(unique=True, null=True)
        watched = peewee.IntegerField(default=0)     

    Slideshow.create_table(fail_silently=True)
    
    callback(' - AudioFormatBumpers')
                              
    class BumperBase(ContentBase):
        isImage = peewee.BooleanField(default=False)
        isYoutube = peewee.BooleanField(default=False)
        path = peewee.CharField(unique=True)

    class AudioFormatBumpers(BumperBase):
        format = peewee.CharField()      

    AudioFormatBumpers.create_table(fail_silently=True)

    callback(' - RatingsBumpers')

    class RatingsBumpers(BumperBase):
        system = peewee.CharField(default='MPAA')
        style = peewee.CharField(default='Classic')

    RatingsBumpers.create_table(fail_silently=True)

    callback(' - VideoBumpers')

    class VideoBumpers(BumperBase):
        type = peewee.CharField()

    VideoBumpers.create_table(fail_silently=True)

    ###########################################################################################
    # Ratings
    ###########################################################################################
    class RatingSystem(peewee.Model):
        name = peewee.CharField()
        context = peewee.CharField(null=True)
        regEx = peewee.CharField()
        regions = peewee.CharField(null=True)

        class Meta:
            database = DB

    RatingSystem.create_table(fail_silently=True)

    class Rating(peewee.Model):
        name = peewee.CharField(unique=True)
        internal = peewee.CharField()
        value = peewee.IntegerField(default=0)
        system = peewee.CharField()

        class Meta:
            database = DB

    Rating.create_table(fail_silently=True)

    ###########################################################################################
    # Trailers Database
    ###########################################################################################
    class TrailerBase(peewee.Model):
        WID = peewee.CharField(unique=True)
        watched = peewee.BooleanField(default=False)
        date = peewee.DateTimeField(default=datetime.date(2024, 1, 1))

        class Meta:
            database = DB

    class Trailers(TrailerBase):
        source = peewee.CharField()
        rating = peewee.CharField(null=True)
        genres = peewee.CharField(null=True)
        title = peewee.CharField()
        release = peewee.DateTimeField(default=datetime.date(2024, 1, 1))
        url = peewee.CharField(null=True)
        userAgent = peewee.CharField(null=True)
        thumb = peewee.CharField(null=True)
        broken = peewee.BooleanField(default=False)
        verified = peewee.BooleanField(default=True)
        youtubelink = peewee.CharField(default=False)
        downloadLink = peewee.CharField(null=True)

    Trailers.create_table(fail_silently=True)

    callback(' - Trailers')
    callback(None, 'Database created')

    DB.close()
