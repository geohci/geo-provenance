import os
import re
import sys
import time
import traceback

from flask import Flask, request, jsonify
from flask_cors import CORS
import mwapi
import mwparserfromhell as mw
import tldextract
from urllib.parse import urlparse
import yaml

__dir__ = os.path.dirname(__file__)
sys.path.append(__dir__)

from urltoregion import LogisticInferrer, url2registereddomain

app = Flask(__name__)

INFERRER = LogisticInferrer()
PUBLISHERS = {}
# generic platforms for hosting content that don't have much geographic meaning
DOMAIN_SKIP_LIST = {'youtube.com',
                    'google.com',  # Google Books mainly
                    'facebook.com'}

WIKIPEDIA_LANGUAGE_CODES = ['aa', 'ab', 'ace', 'ady', 'af', 'ak', 'als', 'am', 'an', 'ang', 'ar', 'arc', 'ary', 'arz', 'as', 'ast', 'atj', 'av', 'avk', 'awa', 'ay', 'az', 'azb', 'ba', 'ban', 'bar', 'bat-smg', 'bcl', 'be', 'be-x-old', 'bg', 'bh', 'bi', 'bjn', 'bm', 'bn', 'bo', 'bpy', 'br', 'bs', 'bug', 'bxr', 'ca', 'cbk-zam', 'cdo', 'ce', 'ceb', 'ch', 'cho', 'chr', 'chy', 'ckb', 'co', 'cr', 'crh', 'cs', 'csb', 'cu', 'cv', 'cy', 'da', 'de', 'din', 'diq', 'dsb', 'dty', 'dv', 'dz', 'ee', 'el', 'eml', 'en', 'eo', 'es', 'et', 'eu', 'ext', 'fa', 'ff', 'fi', 'fiu-vro', 'fj', 'fo', 'fr', 'frp', 'frr', 'fur', 'fy', 'ga', 'gag', 'gan', 'gcr', 'gd', 'gl', 'glk', 'gn', 'gom', 'gor', 'got', 'gu', 'gv', 'ha', 'hak', 'haw', 'he', 'hi', 'hif', 'ho', 'hr', 'hsb', 'ht', 'hu', 'hy', 'hyw', 'hz', 'ia', 'id', 'ie', 'ig', 'ii', 'ik', 'ilo', 'inh', 'io', 'is', 'it', 'iu', 'ja', 'jam', 'jbo', 'jv', 'ka', 'kaa', 'kab', 'kbd', 'kbp', 'kg', 'ki', 'kj', 'kk', 'kl', 'km', 'kn', 'ko', 'koi', 'kr', 'krc', 'ks', 'ksh', 'ku', 'kv', 'kw', 'ky', 'la', 'lad', 'lb', 'lbe', 'lez', 'lfn', 'lg', 'li', 'lij', 'lld', 'lmo', 'ln', 'lo', 'lrc', 'lt', 'ltg', 'lv', 'mai', 'map-bms', 'mdf', 'mg', 'mh', 'mhr', 'mi', 'min', 'mk', 'ml', 'mn', 'mnw', 'mr', 'mrj', 'ms', 'mt', 'mus', 'mwl', 'my', 'myv', 'mzn', 'na', 'nah', 'nap', 'nds', 'nds-nl', 'ne', 'new', 'ng', 'nl', 'nn', 'no', 'nov', 'nqo', 'nrm', 'nso', 'nv', 'ny', 'oc', 'olo', 'om', 'or', 'os', 'pa', 'pag', 'pam', 'pap', 'pcd', 'pdc', 'pfl', 'pi', 'pih', 'pl', 'pms', 'pnb', 'pnt', 'ps', 'pt', 'qu', 'rm', 'rmy', 'rn', 'ro', 'roa-rup', 'roa-tara', 'ru', 'rue', 'rw', 'sa', 'sah', 'sat', 'sc', 'scn', 'sco', 'sd', 'se', 'sg', 'sh', 'shn', 'si', 'simple', 'sk', 'sl', 'sm', 'smn', 'sn', 'so', 'sq', 'sr', 'srn', 'ss', 'st', 'stq', 'su', 'sv', 'sw', 'szl', 'szy', 'ta', 'tcy', 'te', 'tet', 'tg', 'th', 'ti', 'tk', 'tl', 'tn', 'to', 'tpi', 'tr', 'ts', 'tt', 'tum', 'tw', 'ty', 'tyv', 'udm', 'ug', 'uk', 'ur', 'uz', 've', 'vec', 'vep', 'vi', 'vls', 'vo', 'wa', 'war', 'wo', 'wuu', 'xal', 'xh', 'xmf', 'yi', 'yo', 'za', 'zea', 'zh', 'zh-classical', 'zh-min-nan', 'zh-yue', 'zu']

# load in app user-agent or any other app config
app.config.update(
    yaml.safe_load(open(os.path.join(__dir__, 'api', 'flask_config.yaml'))))

# Enable CORS for API endpoints
cors = CORS(app, resources={r'/api/*': {'origins': '*'}})

@app.route('/api/v1/geo-provenance', methods=['GET'])
def geoprovenance():
    lang, page_title, error = validate_api_args()
    if error:
        return jsonify({"error": error})
    else:
        wikitext = get_wikitext(lang, page_title)
        results = []
        metadata = {'num_ref_tags':count_ref_tags(wikitext)}
        region_summary = {}
        domains = {}
        publishers = set()
        start = time.time()
        do_process = True
        try:
            for ref, extracted_data in get_references(wikitext):
                res = {'template':ref}
                res.update(extracted_data)
                country = None
                processed = False
                try:
                    if 'publisher' in extracted_data:
                        pub = extracted_data['publisher'].lower()
                        country = PUBLISHERS.get(pub)
                        processed = True
                        publishers.add(pub)
                    if 'url' in extracted_data and country is None:
                        url = extracted_data['url']
                        domain = url2registereddomain(url)
                        if domain and do_process:
                            country = domains.get(domain, url_to_region(url))
                            domains[domain] = country
                            processed = True
                except Exception:
                    res['error'] = True
                finally:
                    res['country'] = country
                    results.append(res)
                    if country:
                        region_summary[country] = region_summary.get(country, 0) + 1
                    else:
                        region_summary['no_country'] = region_summary.get('no_country', 0) + 1
                    if not processed:
                        region_summary['n/a'] = region_summary.get('n/a', 0) + 1
                    if time.time() - start > 40:
                        do_process = False  # taking too long, stop processing domains and skip to the end
        except:  # if processing fails, still return what you have
            traceback.print_exc()
            pass
        finally:
            metadata['num_cite_templates'] = len(results)
            metadata['num_unique_domains'] = len(domains)
            metadata['num_unique_publishers'] = len(publishers)
            if not do_process:
                metadata['process_timed_out'] = True
            return jsonify({'article':f'https://{lang}.wikipedia.org/wiki/{page_title}',
                            'sources':results,
                            'metadata':metadata,
                            'region_summary':[(c, region_summary[c]) for c in sorted(
                                region_summary, key=region_summary.get, reverse=True)]})

def get_wikitext(lang, title):
    """Gather set of up to `limit` outlinks for an article."""
    session = mwapi.Session(f'https://{lang}.wikipedia.org', user_agent=app.config['CUSTOM_UA'])

    # generate list of all outlinks (to namespace 0) from the article and their associated Wikidata IDs
    result = session.get(
        action="parse",
        page=title,
        redirects='',
        prop='wikitext',
        format='json',
        formatversion=2
    )
    try:
        return result['parse']['wikitext']
    except Exception:
        traceback.print_exc()
        return ''

def citation_only(template):
    tn = template.name.strip().lower()
    return ((tn.startswith('cite') or tn.startswith('citation'))
            and not tn.startswith('citation needed')
            and not tn.startswith('cite needed'))

def count_ref_tags(wikitext):
    ref_singleton = re.compile(r'<ref(\s[^/>]*)?/>', re.M | re.I)
    ref_tag = re.compile(r'<ref(\s[^/>]*)?>[\s\S]*?</ref>', re.M | re.I)
    wikitext = re.sub(r'<!--.*?-->', '', wikitext, flags=re.DOTALL).lower()
    return len(ref_singleton.findall(wikitext)) + len(ref_tag.findall(wikitext))

def get_references(wikitext):
    """Extract list of citation templates from wikitext for an article via simple regex.

    Known issues:
    * misses unstructured references -- i.e. using ref tags but not citation templates
    * misses footnote templates like harv or sfn
    """
    try:
        cite_templates = []
        # with raw regex very hard to detect nested templates -- e.g., citation within an infobox
        for template in mw.parse(wikitext).ifilter_templates(matches=citation_only):
            extracted_data = {}
            try:
                url = None
                wikicode = mw.parse(template)
                # extract publisher info
                for param in wikicode.filter_templates()[0].params:
                    if param.name.strip().lower() == 'publisher':
                        extracted_data['publisher'] = param.value.strip_code().strip()
                        break
                # extract URL
                potential_urls = [str(u) for u in wikicode.filter_external_links()]
                if potential_urls:
                    # only one -- use it
                    if len(potential_urls) == 1:
                        url = potential_urls[0]
                    # multiple
                    else:
                        url = None
                        # look for official url parameter
                        for param in wikicode.filter_templates()[0].params:
                            if param.name.strip().lower() == 'url':
                                url = str(param.value).strip()
                                break
                        # multiple but no official URL -- take the first one in template
                        if url is None:
                            url = potential_urls[0]
                    # some final post-processing
                    # if internet archive link, seek to extract original URL out of it
                    tld = tldextract.extract(url)
                    if tld.domain == 'archive':
                        path = urlparse(url).path
                        start_of_archived_url = path.find('http')
                        if start_of_archived_url != -1:
                            url = path[start_of_archived_url:]
                    # common content platforms without much geographic meaning
                    elif url2registereddomain(url) in DOMAIN_SKIP_LIST:
                        url = None
                if url:
                    extracted_data['url'] = url
            except Exception:
                continue
            finally:
               yield (str(template), extracted_data)
        return cite_templates
    except Exception:
        traceback.print_exc()

def url_to_region(url):
    # conf is a number between 0 and 1.0 indicating confidence
    # dist is a dict with keys country codes and values predicted probability
    conf, dist = INFERRER.infer(url)
    #print(url, [(c, f'{dist[c]:0.3f}') for c in sorted(dist, key=dist.get, reverse=True)][:5])
    country = max(dist, key=dist.get)
    prob = dist[country]
    if prob > 0.5:
        return country
    else:
        return None

def get_canonical_page_title(title, lang):
    """Resolve redirects / normalization -- used to verify that an input page_title exists"""
    session = mwapi.Session('https://{0}.wikipedia.org'.format(lang), user_agent=app.config['CUSTOM_UA'])

    result = session.get(
        action="query",
        prop="info",
        inprop='',
        redirects='',
        titles=title,
        format='json',
        formatversion=2
    )
    if 'missing' in result['query']['pages'][0]:
        return None
    else:
        return result['query']['pages'][0]['title'].replace(' ', '_')

def validate_lang(lang):
    return lang in WIKIPEDIA_LANGUAGE_CODES

def validate_api_args():
    """Validate API arguments for language-agnostic model."""
    error = None
    lang = None
    page_title = None
    if request.args.get('title') and request.args.get('lang'):
        lang = request.args['lang']
        page_title = get_canonical_page_title(request.args['title'], lang)
        if page_title is None:
            error = 'no matching article for <a href="https://{0}.wikipedia.org/wiki/{1}">https://{0}.wikipedia.org/wiki/{1}</a>'.format(lang, request.args['title'])
    elif request.args.get('lang'):
        error = 'missing an article title -- e.g., "2005_World_Series" for <a href="https://en.wikipedia.org/wiki/2005_World_Series">https://en.wikipedia.org/wiki/2005_World_Series</a>'
    elif request.args.get('title'):
        error = 'missing a language -- e.g., "en" for English'
    else:
        error = 'missing language -- e.g., "en" for English -- and title -- e.g., "2005_World_Series" for <a href="https://en.wikipedia.org/wiki/2005_World_Series">https://en.wikipedia.org/wiki/2005_World_Series</a>'

    return lang, page_title, error

def load_publishers():
    expected_header = ['publisher', 'country']
    with open(os.path.join(__dir__, 'urltoregion/data/fullmodel/wikidata_publisher_countries.tsv'), 'r') as fin:
        assert next(fin).strip().split('\t') == expected_header
        for line in fin:
            line = line.strip().split('\t')
            publisher = line[0]
            country = line[1]
            PUBLISHERS[publisher.strip().lower()] = country
    print(f"Loaded {len(PUBLISHERS)} publishers.")


application = app
load_publishers()

if __name__ == '__main__':
    application.run()