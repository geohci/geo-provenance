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

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
print(sys.path)

from urltoregion.gputils import *

WIKIDATA_HEADER = ['domain', 'lat', 'lon', 'country']
PUBLISHER_HEADER = ['publisher', 'country']

class WikidataProvider:
    """
    Resolves a URL to a country using information from the Wikidata project.
    Uses a precomputed mapping from domain to lat/long coordinate stored in data/wikidata.json.
    These coordinates are geocoded to country on the fly using OpenStreetMap's nominatom API.
    Results are cached so that domains are only geocoded once.
    """
    def __init__(self, cache_path=None):
        if not cache_path: cache_path = get_data_path('wikidata_countries.tsv', dirtype='model')
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
                    warn(f'invalid wikidata line: {line}')
        warn(f'finished reading {len(self.domains)} wikidata entries')

        # a few known data quality issues -- largely arising from duplicates of URL domains
        # TODO: better approach that doesn't include domains with high ambiguity?
        self.domains['ibm.com'] = 'United States of America'
        self.domains['nytimes.com'] = 'United States of America'


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
    region_shapes = get_region_data(region_qids_tsv=get_data_path('base_regions_qids.tsv', dirtype='country'),
                                    region_geoms_geojson=get_data_path('ne_10m_admin_0_map_units.geojson', dirtype='country'),
                                    aggregation_tsv=get_data_path('country_aggregation.tsv', dirtype='country'))
    assert(coord_to_country(region_shapes, 55.309444, 25.269722) == 'United Arab Emirates')

def rebuild():
    """Rebuild cache of URLs -> coordinates from Wikidata.

    """
    region_shapes = get_region_data(region_qids_tsv=get_data_path('base_regions_qids.tsv', dirtype='country'),
                                    region_geoms_geojson=get_data_path('ne_10m_admin_0_map_units.geojson', dirtype='country'),
                                    aggregation_tsv=get_data_path('country_aggregation.tsv', dirtype='country'))

    # single query too large so can break into http and https as a rough split
    # and then append query2 results to query1. Clause like the following (after FILTER(BOUND(?coords))) works:
    # FILTER(STRSTARTS(STR(?websiteurl), 'http:'))
    # Also, only 5 URLs that don't start with http(s) (due to capitalization)
    # To check, replace STRSTARTS FILTER with `FILTER(!STRSTARTS(STR(?websiteurl), 'http'))`
    # Close to 1M URLs and 510,037 retained as of 17 March 2022 in total
    website_query = """
    # All items with an official website and either coordinates or a headquarters location
    SELECT
    ?websiteurl ?coords
    WHERE
    {
      # items with a website
      ?item wdt:P856 ?websiteurl .
      # and coordinate location or headquarters or country
      OPTIONAL { ?item wdt:P625 ?coords . }
      OPTIONAL { ?item wdt:P159 ?hq . 
                 ?hq wdt:P625 ?coords .}
      FILTER(BOUND(?coords)).
    }
    """

    # TODO: challenge that many multinational companies have multiple domain names and only the first is used so e.g.,
    # ibm.com/sweden -> Sweden becomes the gold data for IBM
    print("Querying WDQS...")
    r = requests.get("https://query.wikidata.org/sparql",
                     params={'format': 'json', 'query': website_query},
                     headers={'User-Agent': 'isaac@wikimedia.org; geoprovenance'})
    results = r.json()
    all_data = results['results']['bindings']
    print(f"{len(all_data)} URLs retrieved.")
    seen = set()
    written = 0
    not_found = 0
    no_domain = 0
    invalid_coords = 0
    invalid_sparql = 0
    already_seen = 0

    print("Processing results...")
    with open(get_data_path('wikidata_countries.tsv', dirtype='model'), 'w') as fout:
        tsvwriter = csv.writer(fout, delimiter='\t')
        tsvwriter.writerow(WIKIDATA_HEADER)
        for i, website in enumerate(all_data, start=1):
            if i % 50000 == 0:
                print((f"{i} URLs processed. "
                       f"{already_seen} skipped as duplicates. "
                       f"{written} written. "
                       f"{no_domain} no domain after parsing URL. "
                       f"{not_found} had coordinates but no country found. "
                       f"{invalid_coords} had invalid coordinates. "
                       f"{invalid_sparql} had invalid sparql."))
            try:
                url = website['websiteurl']['value']
                domain = url2registereddomain(url)
                if domain in seen:
                    already_seen += 1
                    continue
                elif not domain:
                    no_domain += 1
                    continue
                seen.add(domain)

                coords = website['coords']['value']
                lon, lat = coords.replace("Point", "")[1:-1].split()  # ex: Point(14.4690742 50.0674744)
                try:
                    country = coord_to_country(region_shapes, float(lon), float(lat))
                except Exception:
                    invalid_coords += 1
                    continue

                if country is not None:
                    tsvwriter.writerow([domain, lat, lon, country])
                    written += 1
                else:
                    not_found += 1
            except Exception:
                invalid_sparql += 1

    print((f"Complete! {i} URLs processed. "
           f"{already_seen} skipped as duplicates. "
           f"{written} written. "
           f"{no_domain} no domain after parsing URL. "
           f"{not_found} had coordinates but no country found. "
           f"{invalid_coords} had invalid coordinates. "
           f"{invalid_sparql} had invalid sparql."))

def get_publishers():
    """Build cache of Publishers -> Countries from Wikidata."""
    from urltoregion.gpinfer import LogisticInferrer as LR

    region_shapes = get_region_data(region_qids_tsv=get_data_path('base_regions_qids.tsv', dirtype='country'),
                                    region_geoms_geojson=get_data_path('ne_10m_admin_0_map_units.geojson', dirtype='country'),
                                    aggregation_tsv=get_data_path('country_aggregation.tsv', dirtype='country'))

    qid_to_country = get_qid_to_region(region_qids_tsv=get_data_path('base_regions_qids.tsv', dirtype='country'),
                                       aggregation_tsv=get_data_path('country_aggregation.tsv', dirtype='country'))

    inferrer = LR()

    #
    website_query = """
    # All items with an official website and either coordinates or a headquarters location
    SELECT
    ?itemLabel ?coords ?country ?websiteurl
    WHERE
    {
      # publishers
      ?item wdt:P31/wdt:P279* wd:Q2085381 .  # Instance-of/subclass of Publisher
      # and country or coordinate location or headquarters
      OPTIONAL { ?item wdt:P856 ?websiteurl . }
      OPTIONAL { ?item wdt:P17 ?country . }
      OPTIONAL { ?item wdt:P625 ?coords . }
      OPTIONAL { ?item wdt:P159 ?hq . 
                ?hq wdt:P625 ?coords .}
      FILTER(BOUND(?coords) || BOUND(?country) || BOUND(?websiteurl)).
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
    }
    """

    print("Querying WDQS...")
    r = requests.get("https://query.wikidata.org/sparql",
                     params={'format': 'json', 'query': website_query},
                     headers={'User-Agent': 'isaac@wikimedia.org; geoprovenance'})
    results = r.json()
    all_data = results['results']['bindings']
    print(f"{len(all_data)} publishers retrieved.")
    seen = set()
    written = 0
    not_found = 0
    no_pub = 0
    invalid_coords = 0
    invalid_country = 0
    invalid_sparql = 0
    already_seen = 0

    print("Processing results...")
    with open(get_data_path('wikidata_publisher_countries_INT.tsv', dirtype='model'), 'w') as fout:
        tsvwriter = csv.writer(fout, delimiter='\t')
        tsvwriter.writerow(PUBLISHER_HEADER)
        for i, publisher in enumerate(all_data, start=1):
            if i % 5000 == 0:
                print((f"{i} publishers processed. "
                       f"{already_seen} skipped as duplicates. "
                       f"{written} written. "
                       f"{no_pub} missing a publisher. "
                       f"{not_found} had coordinates but no country found. "
                       f"{invalid_coords} had invalid coordinates. "
                       f"{invalid_sparql} had invalid sparql."))
            try:
                pub = publisher['itemLabel']['value']
                if pub in seen:
                    already_seen += 1  # still retain -- unfortunately names are not unique
                elif not pub:
                    no_pub += 1
                    continue
                seen.add(pub)

                country = ''
                if 'country' in publisher:
                    try:
                        country_qid = publisher['country']['value'].replace('http://www.wikidata.org/entity/', '')
                        country = qid_to_country[country_qid]
                    except Exception:
                        invalid_country += 1

                if not country and 'coords' in publisher:
                    try:
                        coords = publisher['coords']['value']
                        lon, lat = coords.replace("Point", "")[1:-1].split()  # ex: Point(14.4690742 50.0674744)
                        country = coord_to_country(region_shapes, float(lon), float(lat))
                    except Exception:
                        invalid_coords += 1
                        continue

                if 'websiteurl' in publisher and not country:
                    url = publisher['websiteurl']['value']
                    domain = url2registereddomain(url)
                    conf, dist = inferrer.infer(url)
                    top_cand = max(dist, key=dist.get)
                    if dist[top_cand] > 0.5:
                        country = top_cand
                        print(f'inferred {country} from {url} ({domain})')

                if country:
                    tsvwriter.writerow([pub, country])
                    written += 1
                else:
                    not_found += 1
            except Exception:
                import traceback
                traceback.print_exc()
                invalid_sparql += 1

    print((f"Complete! {i} publishers processed. "
           f"{already_seen} skipped as duplicates. "
           f"{written} written. "
           f"{no_pub} missing a publisher. "
           f"{not_found} had coordinates but no country found. "
           f"{invalid_coords} had invalid coordinates. "
           f"{invalid_sparql} had invalid sparql."))

    print("Cleaning up results")
    to_remove = set()
    results = {}
    with open(get_data_path('wikidata_publisher_countries_INT.tsv', dirtype='model'), 'r') as fout:
        tsvreader = csv.reader(fout, delimiter='\t')
        assert next(tsvreader) == PUBLISHER_HEADER
        for line in tsvreader:
            publisher = line[0]
            country = line[1]
            if publisher in results and results[publisher] != country:
                to_remove.add(publisher)
            else:
                results[publisher] = country

    with open(get_data_path('wikidata_publisher_countries.tsv', dirtype='model'), 'w') as fout:
        tsvwriter = csv.writer(fout, delimiter='\t')
        tsvwriter.writerow(PUBLISHER_HEADER)
        for publisher, country in results.items():
            if publisher not in to_remove:
                tsvwriter.writerow([publisher, country])

def get_qid_to_region(region_qids_tsv, aggregation_tsv):
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

    return qid_to_region

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
    #warn(f'did not find: ({lat}, {lon})')
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
    qid_to_region = get_qid_to_region(region_qids_tsv, aggregation_tsv)

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
    #rebuild()
    get_publishers()
