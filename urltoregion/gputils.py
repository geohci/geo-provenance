import codecs
import os
import sys
import tldextract
import urllib.request

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

GENERIC_TLDS = set('ad,as,bz,cc,cd,co,dj,fm,io,la,me,ms,nu,sc,sr,su,tv,tk,ws'.split(','))
ISO2_TO_COUNTRY = {}

def get_data_path(filename, dirtype='', original=False):
    directory = DATA_DIR
    if dirtype == 'gold':
        directory = os.path.join(DATA_DIR, 'goldfeatures')
    elif dirtype == 'country':
        directory = os.path.join(DATA_DIR, 'countries')
    elif dirtype == 'resources':
        directory = os.path.join(DATA_DIR, 'resources')
    elif dirtype == 'model':
        directory = os.path.join(DATA_DIR, 'fullmodel')

    if original:
        return os.path.join(directory, 'original', filename)
    else:
        return os.path.join(directory,  filename)

def set_data_dir(path):
    global DATA_DIR
    DATA_DIR = path

def url2registereddomain(url):
    host = url2host(url)
    parts = tldextract.extract(host)
    return parts.registered_domain

def url2tld(url):
    host = url2host(url)
    return host.split('.')[-1]

def warn(message):
    sys.stderr.write(message + '\n')

def read_gold(path=None):
    if not path: path = get_data_path('geoprov198_countries.tsv', dirtype='gold')
    f = gp_open(path)
    gold = [
        (l.split('\t')[0].strip(), l.split('\t')[1].strip())
        for l in f
    ]
    f.close()
    return list(gold)

def iso2_to_country(iso2):
    if not ISO2_TO_COUNTRY:
        # one manual one because weirdly some of the original whois data uses 'uk' instead of 'gb'
        ISO2_TO_COUNTRY['uk'] = 'United Kingdom'
        warn(f'Loading in ISO-2 -> country mapping.')
        with open(get_data_path('iso2_countries.tsv', dirtype='country'), 'r') as fin:
            for line in fin:
                iso2, country = line.strip().split('\t')
                ISO2_TO_COUNTRY[iso2] = country
    return ISO2_TO_COUNTRY.get(iso2, '')

def update_goldfeatures():
    from country import read_countries

    print("Converting geoip gold data -> countries")
    with open(get_data_path('geoip.tsv', dirtype='gold', original=True), 'r') as fin:
        with open(get_data_path('geoip_countries.tsv', dirtype='gold', original=False), 'w') as fout:
            for line in fin:
                # ats.aq	us
                domain, iso2 = line.strip().split("\t")
                country = iso2_to_country(iso2)
                fout.write(f'{domain}\t{country}\n')

    print("Converting wikidata gold data -> countries")
    with open(get_data_path('wikidata.tsv', dirtype='gold', original=True), 'r') as fin:
        with open(get_data_path('wikidata_countries.tsv', dirtype='gold', original=False), 'w') as fout:
            for line in fin:
                # example: google.com	us
                domain, iso2 = line.strip().split("\t")
                country = iso2_to_country(iso2)
                fout.write(f'{domain}\t{country}\n')

    print("Converting whois gold data -> countries")
    with open(get_data_path('whois.tsv', dirtype='gold', original=True), 'r') as fin:
        with open(get_data_path('whois_countries.tsv', dirtype='gold', original=False), 'w') as fout:
            for line in fin:
                # example: norfolk.gov.uk	uk|1,nf|1
                try:
                    domain, predictions = line.strip().split("\t")
                except ValueError:
                    domain = line.strip()
                    predictions = ''
                country_predictions = []
                for p in predictions.split(','):
                    if p:
                        iso2, confidence = p.split('|')
                        country = iso2_to_country(iso2)
                        country_predictions.append((country, confidence))
                fout.write(f'{domain}\t{";".join(["|".join(p) for p in country_predictions])}\n')

    if os.path.exists(get_data_path('whois.tsv', dirtype='model', original=True)):
        print("Converting whois full data -> countries")
        with open(get_data_path('whois.tsv', dirtype='model', original=True), 'r') as fin:
            with open(get_data_path('whois_countries.tsv', dirtype='model', original=False), 'w') as fout:
                for line in fin:
                    # example: norfolk.gov.uk	uk|1,nf|1
                    try:
                        domain, predictions = line.strip().split("\t")
                    except ValueError:
                        domain = line.strip()
                        predictions = ''
                    country_predictions = []
                    for p in predictions.split(','):
                        if p:
                            iso2, confidence = p.split('|')
                            country = iso2_to_country(iso2)
                            country_predictions.append((country, confidence))
                    fout.write(f'{domain}\t{";".join(["|".join(p) for p in country_predictions])}\n')
    else:
        print("Skipping whois full data (could not find)")

    print("Converting geoprov gold data -> countries")
    with open(get_data_path('geoprov198.tsv', dirtype='gold', original=True), 'r') as fin:
        with open(get_data_path('geoprov198_countries.tsv', dirtype='gold', original=False), 'w') as fout:
            for line in fin:
                # example: http://www.ats.aq/devAS/info_measures_listitem.aspx?lang=e&id=46	aq
                url, iso2 = line.strip().split("\t")
                country = iso2_to_country(iso2)
                fout.write(f'{url}\t{country}\n')

    print("Converting alias gold data -> countries.")
    with open(get_data_path('manual_aliases.tsv', dirtype='resources', original=True), 'r') as fin:
        with open(get_data_path('manual_aliases_countries.tsv', dirtype='resources', original=False), 'w') as fout:
            for line in fin:
                # example: balgeriya	bg
                alias, iso2 = line.strip().split("\t")
                if alias == 'cs':  # too generic; remove
                    continue
                country = iso2_to_country(iso2)
                fout.write(f'{alias}\t{country}\n')
            with open(get_data_path('additional_aliases.tsv', dirtype='resources'), 'r') as fin:
                for line in fin:
                    alias, country = line.strip().split('\t')
                    fout.write(f'{alias}\t{country}\n')

    countries_found = set()
    print("Converting prior data -> countries.")
    with open(get_data_path('priors.tsv', dirtype='model', original=True), 'r') as fin:
        with open(get_data_path('priors_countries.tsv', dirtype='model', original=False), 'w') as fout:
            for line in fin:
                # example: us	0.26005
                iso2, prior = line.strip().split("\t")
                country = iso2_to_country(iso2)
                if country:
                    fout.write(f'{country}\t{prior}\n')
                    countries_found.add(country)
            for c in read_countries():
                if c.name not in countries_found:
                    fout.write(f'{c}\t0.00000\n')

# The encoded reader from io is faster but only available in Python >= 2.6
try:
    import io
    enc_open = io.open
except Exception:
    enc_open = codecs.open


class GPException(Exception):
    pass

def gp_open(path, mode='r', encoding='utf-8'):
    return enc_open(path, mode, encoding=encoding)

def url2host(url):
    if not url.startswith('http:') and not url.startswith('https:'):
        url = 'http://' + url
    return urllib.request.urlparse(url).netloc


def test_url2host():
    assert(url2host('www.ibm.com/foo/bar') == 'www.ibm.com')
    assert(url2host('http://www.ibm.com/foo/bar') == 'www.ibm.com')
    assert(url2host('https://www.ibm.com/foo/bar') == 'www.ibm.com')

def test_url2tld():
    assert(url2tld('http://www.ibm.com/foo/bar') == 'com')

def test_url2registereddomain():
    assert(url2registereddomain('http://www.ibm.com/foo/bar') == 'ibm.com')
    assert(url2registereddomain('http://foo.bbc.co.uk/foo/bar') == 'bbc.co.uk')

if __name__ == "__main__":
    update_goldfeatures()