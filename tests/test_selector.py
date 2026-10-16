"""CPU behavior checks of the packaged selector, not production inference."""
import copy
import unittest
from ki_ocr.best_effort import select

class SelectorTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [dict(id='native', scale=1, h=8, support=3),
            dict(id='up-a', scale=1.5, h=12, support=3, V=100, P=100,
                 context=32768, reserve=8192, resource_admitted=True),
            dict(id='up-b', scale=2, h=13, support=3, V=200, P=200,
                 context=32768, reserve=8192, resource_admitted=True)]
        self.kw = dict(T=12, L=11, original_h=8, original_support=3,
                       supported_domain=True, protected=False, max_scale=2)
    def pick(self, candidates=None, **kw):
        return select(candidates or self.candidates, **(self.kw | kw))
    def test_reachable_minimum_actual_V(self):
        self.assertEqual(self.pick()['selected_id'], 'up-a')
    def test_strict_original_threshold(self):
        self.assertEqual(self.pick(original_h=10.5)['selected_id'], 'native')
        self.assertEqual(self.pick(original_h=10.49)['selected_id'], 'up-a')
    def test_protected_and_unsupported(self):
        self.assertEqual(self.pick(protected=True)['selected_id'], 'native')
        self.assertEqual(self.pick(supported_domain=False)['selected_id'], 'native')
    def test_insufficient_original_support(self):
        self.assertEqual(self.pick(original_support=2)['selected_id'], 'native')
    def test_best_effort_keeps_unmet_status(self):
        z = self.pick(T=14)
        self.assertEqual(z['selected_id'], 'up-b')
        self.assertFalse(z['target_reached'])
        self.assertTrue(z['best_effort_applied'])
    def test_budget_rejects_highest_post_h(self):
        cs = copy.deepcopy(self.candidates)
        cs[2]['P'] = 30000
        self.assertEqual(self.pick(cs, T=14)['selected_id'], 'up-a')
    def test_missing_admission_is_error(self):
        cs = copy.deepcopy(self.candidates)
        del cs[1]['P']
        with self.assertRaises(ValueError):
            self.pick(cs)
    def test_numeric_scale_tie_order(self):
        cs = copy.deepcopy(self.candidates)
        cs[2]['V'] = cs[1]['V']
        self.assertEqual(self.pick(cs)['selected_id'], 'up-a')

if __name__ == '__main__':
    unittest.main()
