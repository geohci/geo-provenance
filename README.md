# Geo-provenance

This is an update to the original [geo-provenance](https://github.com/shilad/geo-provenance) repository.
It makes some functionality fixes -- upgrade to Python3; update Wikidata endpoints -- but it also has a slightly different purpose. 
The original code was aimed at broad-scale distributional analyses -- e.g., how many references in English Wikipedia are from India?
This fork is aimed at individual accuracy and simplicity, so I have favored higher precision over recall and dropped some features that are more expensive to generate.

Summary:
* I dropped the page language feature. This had high coverage (96%) but low accuracy (61%) and introduces a lot of overhead for the crawling of webpages.
* I retained the WHOIS feature even though it's also high cost because of the existing cache and high accuracy (80%)
* I retained the Wikidata feature because of the high accuracy (93%) and simplicity of making a single SPARQL query
* I retained the URL features (milgov and tld) because of their high accuracy (>90%) and simplicity
* I updated the country list to match the ones I was using for [other analyses](https://github.com/geohci/wiki-region-groundtruth)
* Switched to full country names as the underlying country "vocab" to align with other analyses and include regions without ISO-2 codes
* Switched in local point-to-country inference for Nominatim to reduce external dependency / save high volume of API calls

### Installing necessary Python modules:

```bash
pip install shapely
pip install tldextract
```

If you want to run the evaluator, which rebuilds the logistic regression (not necessary to use the pre-built model), you'll also need to install `sklearn`.

### Running the command-line program.

The `py` directory contains the `run_inferrer.py` program, which reads URLs from standard input and writes information about them to standard output. For example, if you ran the following from the shell from within the `py` directory:

```bash
$ echo 'http://www.timeout.com/dublin/' | python ./run_inferrer.py
```

You would see the following output:

```text
http://www.timeout.com/dublin/  gb      0.8259  {'gb' : 0.8259, 'us' : 0.0628, 'fr' : 0.0008, 'ca' : 0.0006, 'ru' : 0.0006, 'in' : 0.0005, 'de' : 0.0005, 'se' : 0.0005, 'it' : 0.0005, 'pl' : 0.0005}
```

run_inferrer.py outputs the following four tab-separated fields: 

1. The URL itself.
2. The most probable country.
3. The estimated probability the most probable country is correct (in this case, about 83%).
4. The top 10 candidate countries, along with their associated probabilities, in JSON format.

If you run the program from somewhere outside of the `py` directory, or would like to use a larger pre-built feature cache (see information below), you can specify the feature directory, or both the features and data directories, from the command line:

```bash
$ python run_inferrer.py path/to/features/dir
$ python run_inferrer.py path/to/features/dir path/to/data/dir
```

### Incorporating the module into your own Python program.

```python
import gputils
import gpinfer

# necessary iff not run from the "py" directory
gputils.set_data_dir('/path/to/data')

# necessary iff not run from the "py" directory or alternate feature caches are used (see below)
gputils.set_feature_dir('/path/to/feature')

inferrer = gpinfer.LogisticInferrer()

# conf is a number between 0 and 1.0 indicating confidence
# dist is a dict with keys country codes and values predicted probability
(conf, dist) = inferrer.infer('http://www.timeout.com/dublin/')
```

### Incorporating larger pre-built caches for speed

A larger feature cache is available at https://www.dropbox.com/s/hq5ogzrd2jobwwh/geo-provenance-features.zip?dl=0. To use this feature cache, download and extract the zip file. You'll then need to point the module at the feature directory by either specifying the appropriate argument to the run_inferrer.py program, or by calling `gp_utils.set_feature_dir` with the appropriate absolute pathname.

This cache contains information about all 7.5M URLs analyzed in our CHI paper.

### The GeoProv198 Dataset

The logistic regression classification model used in this package is trained using a gold standard dataset that maps urls to countries. This dataset is available in the [data](https://github.com/shilad/geo-provenance/blob/master/data/geoprov198.tsv) directory and its collection methodology is described in the citation above.

### Questions or suggestions?

Open an issue on this repo, send a pull request, or email Isaac at isaac@wikimedia.org.

### Credits

* See: https://github.com/shilad/geo-provenance
