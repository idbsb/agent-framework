"""Exact skill+polarity micro metrics and explicit labelled-field exact match."""
POLARITIES = {'affirmed', 'negated', 'planned', 'other_person', 'uncertain'}


def _index(rows):
    result = {}
    for row in rows:
        key = row.get('id')
        if not isinstance(key, str) or not key or key in result:
            raise ValueError('Evaluation IDs must be unique nonempty strings')
        skills = set()
        for s in row.get('skills', []):
            if s.get('polarity') not in POLARITIES or not isinstance(s.get('skill'), str) or not s['skill']:
                raise ValueError('Each skill needs a canonical name/ID and an explicit valid polarity')
            skills.add((s['skill'], s['polarity']))
        fields = row.get('fields', {})
        if not isinstance(fields, dict):
            raise ValueError('fields must be an object; absent means unlabelled, null means labelled unknown')
        result[key] = dict(skills=skills, fields=fields)
    return result


def _metrics(tp, fp, fn):
    return dict(tp=tp, fp=fp, fn=fn, precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None, f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)


def evaluate(gold, predictions):
    gold, predictions = _index(gold), _index(predictions)
    totals, positive, fields, errors = [0, 0, 0], [0, 0, 0], {}, []
    exact = 0
    for key in sorted(gold.keys() | predictions.keys()):
        expected, actual = gold.get(key, {}), predictions.get(key, {})
        a, b = expected.get('skills', set()), actual.get('skills', set())
        for output, left, right in [(totals, a, b), (positive, {s for s in a if s[1] == 'affirmed'}, {s for s in b if s[1] == 'affirmed'})]:
            for i, n in enumerate((len(left & right), len(right-left), len(left-right))):
                output[i] += n
        exact += key in gold and key in predictions and a == b
        wrong_fields = {}
        for field, value in expected.get('fields', {}).items():
            count = fields.setdefault(field, dict(correct=0, total=0))
            count['total'] += 1
            present = field in actual.get('fields', {})
            correct = present and actual['fields'][field] == value
            count['correct'] += correct
            if not correct:
                wrong_fields[field] = dict(gold=value, prediction=actual.get('fields', {}).get(field), prediction_present=present)
        if a != b or wrong_fields or key not in gold or key not in predictions:
            render = lambda values: [dict(skill=s, polarity=p) for s, p in sorted(values)]
            errors.append(dict(id=key, false_positive=render(b-a), false_negative=render(a-b), field_errors=wrong_fields,
                               gold_present=key in gold, prediction_present=key in predictions))
    return dict(skills=_metrics(*totals), affirmed_skills=_metrics(*positive),
                fields={k: dict(**v, exact_match=v['correct']/v['total']) for k, v in fields.items()},
                skill_set_exact_match=exact/len(gold) if gold else None, gold_count=len(gold), prediction_count=len(predictions), errors=errors,
                notice='Synthetic regression result != Real-world accuracy; provenance and independent labelling require team verification.',
                undefined_policy='zero denominator -> null, not 100%; missing predictions are retained as errors')
