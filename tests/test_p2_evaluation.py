"""Synthetic regression result != Real-world accuracy."""
import copy
import unittest
from fixtures.p2_synthetic.synthetic_fixture import GOLD, PREDICTION
from evaluation.metrics import evaluate


class EvaluationTest(unittest.TestCase):
    def test_c01_precision(self):
        self.assertEqual(evaluate(GOLD, PREDICTION)['skills']['precision'], .5)

    def test_c02_recall(self):
        self.assertEqual(evaluate(GOLD, PREDICTION)['skills']['recall'], .5)

    def test_c03_f1(self):
        self.assertEqual(evaluate(GOLD, PREDICTION)['skills']['f1'], .5)

    def test_c04_empty_prediction(self):
        value = evaluate(GOLD, [])['skills']
        self.assertIsNone(value['precision'])
        self.assertEqual(value['recall'], 0)
        self.assertEqual(value['fn'], 2)

    def test_c05_empty_gold(self):
        value = evaluate([], PREDICTION)['skills']
        self.assertIsNone(value['recall'])
        self.assertEqual(value['fp'], 2)
        self.assertIsNone(evaluate([], [])['skills']['f1'])

    def test_c06_polarity_not_confused(self):
        value = evaluate(GOLD, PREDICTION)
        self.assertEqual(value['skills']['tp'], 1)
        self.assertEqual(value['affirmed_skills']['tp'], 1)
        self.assertEqual(value['affirmed_skills']['fp'], 1)

    def test_c07_errors(self):
        value = evaluate(GOLD, PREDICTION)
        self.assertEqual(len(value['errors'][0]['false_positive']), 1)
        self.assertEqual(value['errors'][0]['false_negative'][0]['polarity'], 'negated')

    def test_fields_unknown_not_half_credit(self):
        result = evaluate(GOLD, PREDICTION)
        self.assertEqual(result['fields']['education']['exact_match'], 1)
        self.assertEqual(result['fields']['experience']['exact_match'], 0)

    def test_missing_null_prediction_not_counted_correct(self):
        self.assertEqual(evaluate(GOLD, [])['fields']['experience']['exact_match'], 0)

    def test_no_duplicate_ids_or_unknown_polarities(self):
        with self.assertRaises(ValueError):
            evaluate(GOLD + GOLD, PREDICTION)
        bad = copy.deepcopy(GOLD)
        bad[0]['skills'][0]['polarity'] = 'maybe_fake'
        with self.assertRaises(ValueError):
            evaluate(bad, [])

    def test_empty_unlabelled_fields_not_inflated(self):
        self.assertEqual(evaluate([{'id': 'SYNTHETIC-EMPTY'}], [])['fields'], {})
