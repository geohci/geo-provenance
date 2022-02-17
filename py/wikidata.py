"""
Attempts to look up the locations associated with URLs using information from Wikidata.

Uses a precomputed mapping from domain to coordinate to country extracted from the Wikidata project.
This mapping is stored in data/wikidata.tsv and can be rebuilt by running this Python module.

Author: Shilad Sen
Adapted by: Isaac Johnson

"""
import csv
import json
import os
import requests

from shapely.geometry import shape, Point

from gputils import *

WIKIDATA_HEADER = ['domain', 'lat', 'lon', 'country']

class WikidataProvider:
    """
    Resolves a URL to a country using information from the Wikidata project.
    Uses a precomputed mapping from domain to lat/long coordinate stored in data/wikidata.json.
    These coordinates are geocoded to country on the fly using OpenStreetMap's nominatom API.
    Results are cached so that domains are only geocoded once.
    """
    def __init__(self, cache_path=None):
        if not cache_path: cache_path = get_data_path('wikidata.tsv')
        if not os.path.isfile(cache_path):
            raise GPException('wikidata results not available...')

        warn('reading wikidata results...')
        self.domains = {}
        with open(cache_path, 'r') as fin:
            tsvreader = csv.reader(fin, delimiter='\t')
            assert next(tsvreader) == WIKIDATA_HEADER
            expected_num_columns = len(WIKIDATA_HEADER)
            domain_idx = WIKIDATA_HEADER.index('domain')
            country_idx = WIKIDATA_HEADER.index('country')
            for line in tsvreader:
                if len(line) == expected_num_columns:
                    domain = line[domain_idx]
                    country = line[country_idx]
                    self.domains[domain] = country
                else:
                    warn('invalid wikidata line: %s' % repr(line))
        warn(f'finished reading {len(self.domains)} wikidata entries')

    def get(self, url):
        domain = url2registereddomain(url)
        if not domain:
            return None
        country = self.domains.get(domain)
        if country:
            return country
        else:
            return None

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
    assert(provider.get('http://www.ac.gov.br') == 'Brazil')
    assert(provider.get('https://www.ac.gov.br') == 'Brazil')
    assert(provider.get('https://www.ibm.com/foo/bar') == 'United States')


def test_coord_to_country():
    region_shapes = get_region_data(region_qids_tsv=os.path.join(DATA_DIR, 'countries', 'base_regions_qids.tsv'),
                                    region_geoms_geojson=os.path.join(DATA_DIR, 'countries', 'ne_10m_admin_0_map_units.geojson'),
                                    aggregation_tsv=os.path.join(DATA_DIR, 'countries', 'country_aggregation.tsv'))
    assert(coord_to_country(region_shapes, 25.269722, 55.309444) == 'ae')

def rebuild():
    """Rebuild cache of URLs -> coordinates from Wikidata.

    """
    region_shapes = get_region_data(region_qids_tsv=os.path.join(DATA_DIR, 'countries', 'base_regions_qids.tsv'),
                                    region_geoms_geojson=os.path.join(DATA_DIR, 'countries', 'ne_10m_admin_0_map_units.geojson'),
                                    aggregation_tsv=os.path.join(DATA_DIR, 'countries', 'country_aggregation.tsv'))

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

    r = requests.get("https://query.wikidata.org/sparql",
                     params={'format': 'json', 'query': website_query},
                     headers={'User-Agent': 'isaac@wikimedia.org; geoprovenance'})
    results = r.json()
    all_data = results['results']['bindings']
    seen = set()

    with open(DATA_DIR + '/wikidata.tsv', 'w') as fout:
        tsvwriter = csv.writer(fout, delimiter='\t')
        tsvwriter.writerow(WIKIDATA_HEADER)
        for website in all_data:
            try:
                url = website['websiteurl']['value']
                domain = url2registereddomain(url)
                if domain in seen:
                    continue
                elif not domain:
                    warn(f'blank domain from {url}')
                    continue
                seen.add(domain)

                coords = website['coords']['value']
                lon, lat = coords.replace("Point", "")[1:-1].split()  # ex: Point(14.4690742 50.0674744)
                country = None
                try:
                    country = coord_to_country(region_shapes, float(lon), float(lat))
                except Exception:
                    # NOTE: may want to suppress this -- there's a lot of headquarters locations that are place QIDs
                    # such as the QID for Paris instead of coordinates in Paris
                    # TODO: maybe fix this in the SPARQL query?
                    warn(f'invalid coordinates: {coords}')

                if country is not None:
                    tsvwriter.writerow([domain, lat, lon, country])
            except Exception:
                warn(f'invalid sparql result: {website}')

def coord_to_country(region_shapes, lon, lat):
    """Determine which region contains a lat-lon coordinate.

    Depends on shapely library and region_shapes object, which contains a dictionary
    mapping QIDs to shapely geometry objects.
    """
    try:
        pt = Point(lon, lat)
        for region_name, region_shape in region_shapes:
            if region_shape.contains(pt):
                return region_name
    except Exception:
        warn(f'error geolocating: ({lat}, {lon})')
    warn(f'did not find: ({lat}, {lon})')
    return None

def get_aggregation_logic(aggregates_tsv):
    """Mapping of regions -> regions not directly associated with them.

    e.g., Sahrawi Arab Democratic Republic (Q40362) -> Western Sahara (Q6250)
    """
    expected_header = ['Aggregation', 'From', 'QID To', 'QID From']
    aggregation = {}
    with open(aggregates_tsv, 'r') as fin:
        tsvreader = csv.reader(fin, delimiter='\t')
        assert next(tsvreader) == expected_header
        for line in tsvreader:
            try:
                qid_to = line[2]
                qid_from = line[3]
                if qid_from:
                    aggregation[qid_from] = qid_to
            except Exception:
                warn(f"Skipped: {line}")
    return aggregation

def get_region_data(region_qids_tsv, region_geoms_geojson, aggregation_tsv):
    # load in base regions
    qid_to_region = {}
    with open(region_qids_tsv, 'r') as fin:
        tsvreader = csv.reader(fin, delimiter='\t')
        assert next(tsvreader) == ['Region', 'QID']
        for line in tsvreader:
            region = line[0]
            qid = line[1]
            qid_to_region[qid] = region
    warn(f"Loaded {len(qid_to_region)} base regions.")
    # load in additional regions that should be mapped to a more canonical region name
    aggregation = get_aggregation_logic(aggregation_tsv)
    for qid_from in aggregation:
        qid_to = aggregation[qid_from]
        if qid_to in qid_to_region:
            qid_to_region[qid_from] = qid_to_region[qid_to]
        else:
            warn(f"-- Skipping aggregation for {qid_from} to {qid_to}")
    warn(f"Now {len(qid_to_region)} region pairs after adding aggregations.")

    # load in geometries for the regions identified via Wikidata
    with open(region_geoms_geojson, 'r') as fin:
        regions = json.load(fin)['features']
    region_shapes = []
    skipped = []
    for c in regions:
        qid = c['properties']['WIKIDATAID']
        if qid in qid_to_region:
            region_shapes.append((qid_to_region[qid], shape(c['geometry'])))
        else:
            skipped.append('{0} ({1})'.format(c['properties']['NAME'], qid))
    warn(f"Loaded {len(region_shapes)} region geometries. Skipped {len(skipped)}: {skipped}")

    return region_shapes

if __name__ == '__main__':
    rebuild()
