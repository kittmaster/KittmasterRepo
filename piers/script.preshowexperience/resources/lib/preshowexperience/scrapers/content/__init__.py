import xml
from . import scraper
from .. import _scrapers
from ... import util
from ... import ratings
from .... import preshowutil

preshowutil.ratingParser()

class Trailer(_scrapers.Trailer):
    def __init__(self, data):
        _scrapers.Trailer.__init__(self, data)
        self._genres = []
        self.parseNFO(self.data.get('nfo'))

    def parseNFO(self, path):
        if not path:
            return

        try:
            with util.vfs.File(path, 'r') as f:
                data = f.read()
                root = xml.etree.ElementTree.fromstring(data)

            for genre in root.findall('genre'):
                self._genres.append(genre.text)

            mpaa = root.find("mpaa")
            if mpaa is not None:
                self._rating = ratings.getRating(mpaa.text)
        except:
            util.ERROR()

    @property
    def ID(self):
        return 'content:{0}'.format(self.data['ID'])

    @property
    def title(self):
        return self.data.get('title', 'ERROR_NO_TITLE')

    @property
    def genres(self):
        return self._genres

    def getStaticURL(self):
        return self.data.get('url')

    def getPlayableURL(self, res='1080p'):
        return self.getStaticURL()

class ContentTrailerScraper(_scrapers.Scraper):
    def getTrailers(self):
        return [Trailer(t) for t in scraper.getTrailers()]