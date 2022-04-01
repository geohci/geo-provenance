import gzip
import os

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
print(sys.path)

from urltoregion import LogisticInferrer

def load_publishers():
    expected_header = ['publisher', 'country']
    publishers = {}
    with open(os.path.join(os.path.dirname(__file__), '../fullmodel/wikidata_publisher_countries.tsv'), 'r') as fin:
        assert next(fin).strip().split('\t') == expected_header
        for line in fin:
            line = line.strip().split('\t')
            publisher = line[0]
            country = line[1]
            publishers[publisher.strip().lower()] = country
    print(f"Loaded {len(publishers)} publishers.")
    return publishers

def main():
    publishers = load_publishers()
    inferrer = LogisticInferrer()
    expected_header = ['page_id', 'url', 'publisher']
    url_only = 0
    pub_only = 0
    both = 0
    neither = 0
    cite_count = 0
    url_counts = {}
    pub_counts =  {}
    pub_only_counts = {}
    url_only_counts = {}
    with gzip.open('./enwiki-2022-01-citations.tsv.gz', 'rt') as fin:
        assert next(fin).strip().split('\t') == expected_header
        for line in fin:
            line = line.strip().split('\t')
            cite_count += 1
            try:
                pid = int(line[0])
            except Exception:
                pid = None
                print(f"Invalid page ID: {line}")
            try:
                url = line[1]
                url = url if url != '""' else None
            except Exception:
                url = None
                print(f"Invalid url: {line}")
            try:
                pub = line[2]
                pub = pub if pub != '""' else None
            except Exception:
                pub = None
                print(f"Invalid pub: {line}")
            if not url and not pub:
                neither += 1
            elif not url:
                pub_only += 1
                pub_only_counts[pub] = pub_only_counts.get(pub, 0) + 1
            elif not pub:
                url_only += 1
                url_only_counts[url] = url_only_counts.get(url, 0) + 1
            else:
                both += 1

            if url:
                url_counts[url] = url_counts.get(url, 0) + 1
            if pub:
                pub_counts[pub] = pub_counts.get(pub, 0) + 1

            if cite_count % 500000 == 0:
                print((f'{cite_count} templates. '
                       f'{both} ({both / cite_count:0.2f}) with URLs + publishers. '
                       f'{neither} ({neither / cite_count:0.2f}) with neither. '
                       f'{url_only} ({url_only / cite_count:0.2f}) with just a URL. '
                       f'{pub_only} ({pub_only / cite_count:0.2f}) with just a publisher.'))

    print((f'{cite_count} templates. '
           f'{both} ({both / cite_count:0.2f}) with URLs + publishers. '
           f'{neither} ({neither / cite_count:0.2f}) with neither. '
           f'{url_only} ({url_only / cite_count:0.2f}) with just a URL. '
           f'{pub_only} ({pub_only / cite_count:0.2f}) with just a publisher.'))

    print(f"\n{len(url_counts)} unique URL domains.")
    count_urls_with_country = 0
    sum_urls_with_country = 0
    sum_total_urls = 0
    with open('./enwiki-2022-01-url-aggregates.tsv', 'w') as fout_url:
        fout_url.write(f'url\tcount\tcount_only\tcountry\n')
        for i, url in enumerate(sorted(url_counts, key=url_counts.get, reverse=True), start=1):
            try:
                conf, dist = inferrer.infer(url)
                country = max(dist, key=dist.get)
                prob = dist[country]
                if prob < 0.5:
                    country = ''
            except Exception:
                country = ''
            fout_url.write(f'{url}\t{url_counts[url]}\t{url_only_counts.get(url, 0)}\t{country}\n')
            if country:
                count_urls_with_country += 1
                sum_urls_with_country += url_counts[url]
            sum_total_urls += url_counts[url]
            if i % 50000 == 0:
                print((f"{i} URLs processed. "
                       f"{count_urls_with_country} ({count_urls_with_country / i:.2f}) unique URLs with countries. "
                       f"{sum_urls_with_country} ({sum_urls_with_country / sum_total_urls:.2f}) total URLs with countries."))
        print((f"{i} URLs processed. "
               f"{count_urls_with_country} ({100 * count_urls_with_country / i:.1f}%) unique URLs with countries. "
               f"{sum_urls_with_country} ({100 * sum_urls_with_country / sum_total_urls:.1f}%) total URLs with countries."))

    print(f"\n{len(pub_counts)} unique publishers.")
    count_pubs_with_country = 0
    sum_pubs_with_country = 0
    sum_total_pubs = 0
    with open('./enwiki-2022-01-pub-aggregates.tsv', 'w') as fout_pub:
        fout_pub.write(f'publisher\tcount\tcount_only\tcountry\n')
        for i,pub in enumerate(sorted(pub_counts, key=pub_counts.get, reverse=True), start=1):
            country = publishers.get(pub, '')
            fout_pub.write(f'{pub}\t{pub_counts[pub]}\t{pub_only_counts.get(pub, 0)}\t{country}\n')
            if country:
                count_pubs_with_country += 1
                sum_pubs_with_country += pub_counts[pub]
            sum_total_pubs += pub_counts[pub]
    print((f"{count_pubs_with_country} ({100 * count_pubs_with_country / i:.1f}%) unique pubs with countries. "
           f"{sum_pubs_with_country} ({100 * sum_pubs_with_country / sum_total_pubs:.1f}%) total pubs with countries."))

if __name__ == "__main__":
    main()