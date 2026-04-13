import requests
import datetime
import re

BROWSER_UA = 'Mozilla/5.0 (compatible, MSIE 11, Windows NT 6.3; Trident/7.0; rv:11.0) like Gecko'
USER_AGENT = BROWSER_UA
RATINGS = {'NOT YET RATED': 'NR', 'NOTYETRATED': 'NR', 'G': 'G', 'PG': 'PG', 'PG13': 'PG-13', 'R': 'R', 'NC17': 'NC-17'}

class Scraper(object):
    def __init__(self, url):
        self.url = url
        self.movies = self.fetch_movies()

    def fetch_movies(self):
        try:
            response = requests.get(self.url)
            response.raise_for_status()  # This will raise an exception for HTTP error codes
            return response.json()
        except requests.RequestException as e:
            return []

    def get_movies(self, limit=0):
        extracted_movies = []
        for movie in self.movies[:limit or None]:
            try:
                release_date = datetime.datetime.strptime(movie["releasedate"], "%Y-%m-%d")
                genres = re.split(',\s*', movie.get("genres", ""))

                movie_details = {
                    "title": movie["title"],
                    "movie_id": movie["url"].split("https://www.imdb.com/video/")[1].rstrip("/"),
                    "location": movie["url"],
                    "poster": movie["thumb"],
                    "genre": ", ".join(genres),
                    "rating": "MPAA:" + movie["rating"],
                    "releasedate": movie["releasedate"],
                    "releasedatetime": release_date,
                }
                extracted_movies.append(movie_details)
            except KeyError as e:
                print(f"Missing data in movie: {e}")
                continue

        return extracted_movies