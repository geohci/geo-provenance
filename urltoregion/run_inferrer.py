#!/usr/bin/python
#
# Reads URLs from stdin and writes inferred countries to stdout.
# The result is a json-formatted dictionary of country-code -> probability pairs.
#


import sys
import time
import traceback

from urltoregion.gputils import *
from urltoregion.gpinfer import LogisticInferrer


def main(inferrer, input, output):
    format = lambda x: '%.4f' % x
    for line in input:
        url = line.split()[0]
        if not url:
            continue
        try:
            (conf, dist) = inferrer.infer(url)
            if dist:
                items = list(dist.items())
                items.sort(key=lambda x: x[1], reverse=True)
                (maxcountry, maxp) = items[0]
                json = '{'
                for (i, (c, p)) in enumerate(items[:10]):
                    if i != 0:
                        json += ', '
                    json += "'%s' : %s" % (c, format(p))
                json += '}'
                output.write(url + '\t' + maxcountry + '\t' + format(maxp) + '\t' + json + '\n')
                output.flush()
            else:
                output.write(url + '\tunknown\t0.0\t{}\n')
                output.flush()
        except Exception:
            warn('url %s failed: ' % url)
            traceback.print_exc()
        time.sleep(10)

if __name__ == '__main__':
    if len(sys.argv) == 2:
        set_data_dir(sys.argv[2])
    elif len(sys.argv) != 1:
        warn('usage: %s [data_dir]')
        sys.exit(1)

    inferrer = LogisticInferrer()

    main(inferrer, sys.stdin, sys.stdout)