"""
Attempts to look up the locations associated with URLs using information from Wikidata.

Uses a precomputed mapping from domain to coordinate extracted from the Wikidata project.
This mapping is stored in data/wikidata.json and can be rebuilt by running this Python module.

Author: Shilad Sen

"""
import json
import os
import traceback

from shapely.geometry import shape, Point

from gputils import *

class WikidataProvider:
    """
    Resolves a URL to a country using information from the Wikidata project.
    Uses a precomputed mapping from domain to lat/long coordinate stored in data/wikidata.json.
    These coordinates are geocoded to country on the fly using OpenStreetMap's nominatom API.
    Results are cached so that domains are only geocoded once.
    """
    def __init__(self, cache_path=None):
        if not cache_path: cache_path = get_feature_data_path('wikidata')
        if not os.path.isfile(cache_path):
            raise GPException('wikidata results not available...')
        self.cache_path = cache_path

        warn('reading wikidata results...')
        n = 0
        self.domains = {}
        for line in gp_open(self.cache_path):
            tokens = line.split('\t')
            if len(tokens) == 2:
                domain = tokens[0].strip()
                iso = tokens[1].strip()
                if not iso: iso = None
                self.domains[domain] = iso
                n += 1
            else:
                warn('invalid wikidata line: %s' % repr(line))
        warn('finished reading %d wikidata entries' % n)

        f = open(get_data_path('wikidata.json'))
        self.domain_coords = json.load(f)
        f.close()

    def get(self, url):
        domain = url2registereddomain(url)
        if not domain:
            return None
        r = self.domains.get(domain)
        if r:
            return r
        elif domain in self.domain_coords:
            coords = self.domain_coords[domain]
            cc = coord_to_country(coords)
            self.domains[domain] = cc
            self.add_cache_line(domain + u'\t' + (cc if cc else ''))
            return cc
        else:
            return None

    def add_cache_line(self, line):
        f = gp_open(self.cache_path, 'a')
        f.write(line + u'\n')
        f.close()

    def load_region_data(self, region_geoms_geojson):
        with open(region_geoms_geojson, 'r') as fin:
            regions = json.load(fin)['features']
        region_shapes = {}
        for c in regions:
            country_code = c['properties']['ISO_A2']
            region_shapes[country_code] = shape(c['geometry'])
        return region_shapes

class WikidataFeature:
    def __init__(self, provider=None):
        if not provider: provider = WikidataProvider()
        self.provider = provider
        self.name = 'wikidata'

    def infer(self, url):
        r = self.provider.get(url)
        if r:
            return (0.99, { r : 1.0 })
        else:
            return (0, {})

def test_wikidata():
    provider = WikidataProvider()
    assert(not provider.get('foo'))
    assert(provider.get('http://www.ac.gov.br') == 'br')
    assert(provider.get('https://www.ac.gov.br') == 'br')
    assert(provider.get('https://www.ibm.com/foo/bar') == 'us')


def test_coord_to_country():
    assert(coord_to_country("25.269722|55.309444|0.000000|0") == 'ae')


def coord_to_country(wikidata_coord):
    parts = wikidata_coord.split('|')
    lat = float(parts[0])
    lng = float(parts[1])

    url = 'http://nominatim.openstreetmap.org/reverse?format=json&lat=%.4f&lon=%.4f' % (lat, lng)
    f = urllib.request.urlopen(url)
    js = json.load(f)
    if js and js['address'] and js['address']['country_code']:
        return js['address']['country_code']
    else:
        return None

def rebuild():
    """Rebuild cache of URLs -> coordinates from Wikidata.

    """
    from SPARQLWrapper import SPARQLWrapper, JSON

    website_query = """
    # All items with an official website and either coordinates or a headquarters location
    SELECT
      ?websiteurl ?coords
    WHERE
    {
      # items with a website
      ?item wdt:P856 ?websiteurl .
      # and coordinate location or headquarters or country
      OPTIONAL { ?item wdt:P159 ?coords . }
      OPTIONAL { ?item wdt:P625 ?coords . }
      FILTER(BOUND(?coords)).
    }
    """
    # 734,702 results as of 16 February 2022

    sparql = SPARQLWrapper("https://query.wikidata.org/sparql",
                           agent='https://github.com/shilad/geo-provenance')
    sparql.setQuery(website_query)
    sparql.setReturnFormat(JSON)
    results = sparql.queryAndConvert()
    all_data = results['results']['bindings']

    wikidata_coords = {}
    for website in all_data:
        try:
            url = website['websiteurl']['value']
            coords = website['coords']['value']
            lon_lat = coords.replace("Point", "")[1:-1].split()  # ex: Point(14.4690742 50.0674744)
            domain = url2registereddomain(url)
            try:
                # ensure valid numeric and convert to <lat>|<lon> representation
                wikidata_coords[domain] = '|'.join([str(float(lon_lat[1])), str(float(lon_lat[0]))])
            except Exception:
                warn('invalid coordinates: %s' % coords)
        except Exception:
            warn('invalid sparql result: %s' % str(website))
            traceback.print_exc()

    with open(DATA_DIR + '/wikidata.json', 'w') as fout:
        json.dump(wikidata_coords, fout)

if __name__ == '__main__':
    rebuild()
