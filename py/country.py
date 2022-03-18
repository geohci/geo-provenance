import collections
from gputils import *


class Country:
    def __init__(self, iso, tld, name=None):
        self.iso = iso
        self.name = name or iso2_to_country(self.iso)
        self.tld = tld
        self.prior = None  # Prior probability of the country generating a webpage

    def __str__(self):
        return self.name

    def __repr__(self):
        return (
            '{Country %s iso=%s, tld=%s, prior=%s}' %
            (self.name, self.iso, self.tld, self.prior)
        )

def read_countries(path_geonames=None, path_prior=None, path_manual=None):
    if not path_geonames: path_geonames = get_data_path('geonames.txt', dirtype='resources')
    if not path_prior: path_prior = get_data_path('priors_countries.tsv', dirtype='model')
    if not path_manual: path_manual = get_data_path('manual_geonames.tsv', dirtype='resources')
    countries = {}

    # read in geonames data
    f = gp_open(path_geonames)
    for line in f:
        if line.startswith('#'):
            continue
        row_tokens = line.strip().split('\t')
        c = Country(iso=row_tokens[0].lower(), tld = row_tokens[9][1:].lower())  # tld: ".uk" -> "uk"
        if c.name:
            countries[c.name] = c

    # read in manual data
    f = gp_open(path_manual)
    assert next(f).strip().split("\t") == ['name', 'tld', 'iso']
    for line in f:
        row_tokens = line.strip().split('\t')
        name = row_tokens[0]
        try:
            iso = row_tokens[2].lower()
        except IndexError:
            iso = None
        try:
            tld = row_tokens[1][1:].lower()
        except IndexError:
            tld = None
        c = Country(name=row_tokens[0], iso=iso, tld=tld)  # tld: ".uk" -> "uk"
        if c.name:
            countries[c.name] = c

    # read prior dataset
    priors = collections.defaultdict(float)
    for line in open(path_prior):
        tokens = line.strip().split('\t')
        c = tokens[0]
        prior = float(tokens[1])
        priors[c] = prior

    # normalize priors to sum to 1
    total = 1.0 * sum(priors.values())
    for c in priors: priors[c] /= total

    # allocate another 1% for smoothing across all countries, renormalize
    k = 0.01 / len(countries)
    for c in countries:
        countries[c].prior = (priors.get(c, 0) + k) / 1.01

    return countries.values()