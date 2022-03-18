# Geo-provenance

This is an update to the original [geo-provenance](https://github.com/shilad/geo-provenance) repository.
It makes some functionality fixes -- upgrade to Python3; update Wikidata endpoints -- but it also has a slightly different purpose. 
The original code was aimed at broad-scale distributional analyses -- e.g., how many references in English Wikipedia are from India?
This fork is aimed at individual accuracy and simplicity, so I have favored higher precision over recall and dropped some features that are more expensive to generate.

Summary:
* I dropped the page language feature. This had high coverage (96%) but low accuracy (61%) and introduces a lot of overhead for the crawling of webpages.
* I retained the WHOIS feature even though it's also high cost because of the existing cache and high accuracy (80%)
* I retained the Wikidata feature because of the high accuracy (93%) and simplicity of making a single SPARQL query (actually two)
* I retained the URL features (milgov and tld) because of their high accuracy (>90%) and simplicity
* I updated the country list to match the ones I was using for [other analyses](https://github.com/geohci/wiki-region-groundtruth)
* I switched to full country names as the underlying country "vocab" to align with other analyses and include regions without ISO-2 codes
* I switched in local point-to-country inference for Nominatim to reduce external dependency / save high volume of API calls
* I updated the pythonwhois library (mainly fixing regexes by explicitly making `r"..." strings`) per https://github.com/joepie91/python-whois/issues
* I added manual aliases for countries that aren't in original ISO2 code vocab and USA for United States
* I removed `cs` for Czech Republic as a manual alias because it matches against `.cs` (shows up in emails as with computer science departments)
* I updated tests etc. in the various Python files to match the above changes (which can be run via `pytest -vv <filename>`)
* I restructured the data folder to account for updated data -- it can be populated based on the original via `gputils.py` and running the new wikidata.py script
* Updated geonames.txt with current version as of 18 March 2022: https://download.geonames.org/export/dump/countryInfo.txt

TODOs:
* Train new model and update model coefficients

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
http://www.timeout.com/dublin/	United Kingdom	0.8390	{'United Kingdom' : 0.8390, 'England' : 0.0522, 'United States of America' : 0.0012, 'France' : 0.0009, 'Russia' : 0.0006, 'Germany' : 0.0006, 'Sweden' : 0.0005, 'Italy' : 0.0005, 'Poland' : 0.0005, 'Spain' : 0.0005}
```

run_inferrer.py outputs the following four tab-separated fields: 

1. The URL itself.
2. The most probable country.
3. The estimated probability the most probable country is correct (in this case, about 83%).
4. The top 10 candidate countries, along with their associated probabilities, in JSON format.

If you run the program from somewhere outside of the `py` directory, you can specify the data directory, from the command line:

```bash
$ python run_inferrer.py path/to/data/dir
```

### Incorporating the module into your own Python program.

```python
import gputils
import gpinfer

# necessary iff not run from the "py" directory
gputils.set_data_dir('/path/to/data')

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
