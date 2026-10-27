import test from 'node:test';
import assert from 'node:assert/strict';
import { evaluationPresentation } from '../../frontend/src/components/evaluationPresentation.ts';
test('reference points and example answer do not repeat feedback already shown', () => {
  const text='Graph kernels compare graphs using feature similarities.';
  const view=evaluationPresentation({missing:[{text},{text}],correct:[],incorrect:[],expected_core_points:[{text}],better_oral_answer:text});
  assert.deepEqual(view.missing,[text]);
  assert.deepEqual(view.expected,[]);
  assert.equal(view.modelAnswer,'');
});
test('deduplication preserves distinct content including negation', () => {
  const view=evaluationPresentation({correct:[{text:'The mapping is invariant.'}],missing:[{text:'The mapping is not invariant.'}],expected_core_points:[{text:'A new supporting fact.'}],better_oral_answer:'A longer explanation.'});
  assert.equal(view.correct.length,1); assert.equal(view.missing.length,1); assert.equal(view.expected.length,1); assert.ok(view.modelAnswer);
});

test('feedback deduplication preserves mathematical signs and comparisons', () => {
  const view=evaluationPresentation({correct:[{text:'The value is -1.'},{text:'x < y.'}],missing:[{text:'The value is 1.'},{text:'x > y.'}]});
  assert.equal(view.correct.length,2); assert.equal(view.missing.length,2);
});
