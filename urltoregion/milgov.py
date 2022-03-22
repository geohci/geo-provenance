from urltoregion.gputils import *

class MilGovFeature:
    def __init__(self):
        self.name = 'mil'

    def infer(self, url):
        host = url2host(url)
        if host.endswith('.mil') or host.endswith('.gov'):
            return (1.0, { 'United States of America' : 1.0 })
        else:
            return (0, {})

def test_milgov():
    f = MilGovFeature()
    assert(f.infer('http://foo.bbc.com/bar') == (0, {}))
    assert(f.infer('https://whitehouse.gov/blah/de') == (1.0, { 'United States of America' : 1.0}))