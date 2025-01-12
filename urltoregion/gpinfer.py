#!/usr/bin/python -O

import collections
import math

from urltoregion.gputils import *
from urltoregion.country import read_countries
from urltoregion.milgov import MilGovFeature
from urltoregion.gpwhois import FreetextWhoisFeature, ParsedWhoisFeature
from urltoregion.wikidata import WikidataFeature
from urltoregion.tld import TldFeature



class PriorFeature:
    def __init__(self, countries=None):
        if not countries: countries = read_countries()
        self.name = 'prior'
        self.prior = {}
        for c in countries:
            self.prior[c.name] = c.prior
        if len(self.prior) == 0:
            raise Exception('no country priors!')

    def infer(self, url):
        return (0.2, dict(self.prior))


def logit(p):
    return math.log(p) - math.log(1 - p)

def prob2sigmoid(p, conf):
    conf = conf - 0.0001 # avoid infinities
    return logit(p * conf + (1.0 - conf) / 2)

def logistic(x):
    return 1.0 / (1 + math.exp(-x))

class LogisticInferrer:
    def __init__(self, features=None, intercept=None, coefficients=None):
        self.name = 'logistic'
        self.reg = None
        if not features:
            self.features = [
                PriorFeature(),
                ParsedWhoisFeature(),
                FreetextWhoisFeature(),
                MilGovFeature(),
                WikidataFeature(),
                TldFeature()
            ]
            self.intercept = -7.23
            self.coefficients = [3.30, 6.56, 2.53, 7.00, 4.05, 7.00]
        else:
            if not intercept or not coefficients:
                raise GPException("if features are specified, intercept and coefficients must be too.")
            self.features = features
            self.intercept = intercept
            self.coefficients = coefficients
        self.countries = read_countries()

    def get_feature(self, name):
        for f in self.features:
            if f.name == name:
                return f
        return None

    def make_rows(self, url_info):
        rows = collections.defaultdict(list)

        for f in self.features:
            (conf, dist) = f.infer(url_info)
            if dist:
                for c in self.countries:
                    rows[c.name].append(dist.get(c.name, 0.0))
            else:
                for c in self.countries:
                    rows[c.name].append(1.0 / len(self.countries))

        return rows


    def train(self, data):
        from sklearn.linear_model import LogisticRegression

        Y = []  # 1 or 0
        X = []  # feature vectors

        for (urlinfo, actual) in data:
            rows = self.make_rows(urlinfo)
            for c in self.countries:
                Y.append(1 if c.name == actual else 0)
                X.append(rows[c.name])

        self.reg = LogisticRegression()
        self.reg.fit(X, Y)
        # Y2 = reg.pre(X)
        #
        # fit_reg = LogisticRegression()
        # fit_reg.fit(Y2, Y)

        self.intercept = self.reg.intercept_[0]
        self.coefficients = self.reg.coef_[0]

    def get_equation(self):
        eq = '%.2f' % self.reg.intercept_
        for (i, f) in enumerate(self.features):
            eq += ' + %.2f * %s' % (self.reg.coef_[0][i], f.name)
        return eq

    def infer(self, url_info):
        result = {}

        for c in self.countries:
            result[c.name] = self.intercept
        for (i, f) in enumerate(self.features):
            (conf, dist) = f.infer(url_info)
            if conf > 0 and dist:
                for c in dist:
                    result[c] += self.coefficients[i] * dist[c]
            else:
                for c in result:
                    result[c] += self.coefficients[i] * 1.0 / len(result)

        # the raising to 1.2nd power approximately calibrates
        # output probabilities to 85% for correct and 66% for incorrect,
        # but does not affect evaluation accuracy
        for (c, score) in result.items():
            result[c] = logistic(score) ** 1.2

        total = sum(result.values())
        for (c, prob) in result.items():
            result[c] = result[c] / total

        return (1.0, result)


if __name__ == '__main__':
    inferrer = LogisticInferrer()
    inferrer.train(read_gold())