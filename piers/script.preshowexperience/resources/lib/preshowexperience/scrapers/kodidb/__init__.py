from . import scraper
from resources.lib import preshowutil
from ... import util
from ... import ratings
from .. import _scrapers


class Trailer(_scrapers.Trailer):
    def __init__(self, data):
        _scrapers.Trailer.__init__(self, data)
        if not self.data.get('rating'):
            self.data['rating'] = 'NR'

    @property
    def ID(self):
        return 'kodiDB:{0}'.format(self.data['ID'])

    @property
    def title(self):
        return self.data['title']

    @property
    def genres(self):
        return self.data.get('genres', [])

    @property
    def rating(self):
        if not getattr(self, '_rating', None):
            ratingString = self.data.get('rating')
            if ratingString:
                self._rating = ratings.getRating(preshowutil.ratingParser().getActualRatingFromMPAA(ratingString))
            else:
                self._rating = None
        return self._rating

    @rating.setter
    def rating(self, val):
        self['rating'] = val

    @property
    def release(self):
        return self.data['release']

    @property
    def watched(self):
        return self.data['watched']

    def getStaticURL(self):
        return self.data['url']

    def getPlayableURL(self, res='720p'):
        return self.data['url']


class KodiDBTrailerScraper(_scrapers.Scraper):
    @staticmethod
    def getPlayableURL(ID, res=720, url=None):
        return url

    def getTrailers(self):
        return [Trailer(t) for t in scraper.getTrailers()]
