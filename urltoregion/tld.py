from urltoregion.gputils import *
from urltoregion.country import read_countries

class TldFeature:
    def __init__(self, countries=None):
        if not countries: countries = read_countries()
        self.name = 'tld'
        self.tld_countries = dict([(c.tld, c) for c in countries if c.tld is not None])

    def infer(self, url):
        tld = url2tld(url)
        if tld not in GENERIC_TLDS and tld in self.tld_countries:
            name = self.tld_countries[tld].name
            return (0.95, { name : 1.0 })
        else:
            return (0, {})

def test_tld():
    f = TldFeature()
    assert(f.infer('http://bbc.com/foo/bar') == (0, {}))
    assert(f.infer('http://bbc.co.uk/foo') == (0.95, { 'United Kingdom' : 1.0}))
    assert(f.infer('bbc.co.uk') == (0.95, { 'United Kingdom' : 1.0}))
    assert(f.infer('presidence.dj') == (0, {}))  # generic TLD
