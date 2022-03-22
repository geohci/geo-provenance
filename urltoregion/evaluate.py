from urltoregion.gputils import *
from urltoregion.gpinfer import LogisticInferrer

def evaluate(gold):
    folds = 7
    subsets = list([[] for i in range(folds)])
    for (i, d) in enumerate(gold):
        subsets[i % folds].append(d)

    correct = 0
    total = 0
    missed_ps = []
    correct_ps = []
    for i in range(folds):
        print(f"Fold {i} / {folds}")
        test = subsets[i]
        train = sum(subsets[0:i] + subsets[i+1:], [])
        inf = LogisticInferrer()
        inf.train(train)
        for (url, actual) in test:
            total += 1
            (conf, dist) = inf.infer(url)
            if not dist:
                warn(f'no prediction for {url}')
                continue
            maxp = max(dist.values())
            bestc = [c for c in dist if dist[c] == maxp][0]
            if bestc == actual:
                correct_ps.append(maxp)
                correct += 1
            else:
                missed_ps.append(maxp)
                print(f'missed {url} - guessed {bestc} was {actual}')

    inf = LogisticInferrer()
    inf.train(gold)

    print('\n\nmodel results:')
    print(f'{correct} of {total} correct {100 * correct / total:.2f}%')
    print(f'calibration: correct mean probability is: {sum(correct_ps) / len(correct_ps):.3f}')
    print(f'calibration: incorrect mean probability is: {sum(missed_ps) / len(missed_ps):.3f}')
    print(f'final model: {inf.get_equation()}')

if __name__ == '__main__':
    gold = read_gold()
    evaluate(gold)