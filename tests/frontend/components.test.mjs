import test from 'node:test';
import assert from 'node:assert/strict';
import { tablePage } from '../../frontend/src/components/tablePage.ts';
import { sourcePage } from '../../frontend/src/components/sourcePage.ts';

const questions = Array.from({ length: 23 }, (_, i) => ({ id: i + 1, topic: i < 11 ? 'Alpha' : 'Beta' }));
test('library and review pagination preserves boundaries', () => {
  assert.deepEqual(tablePage(questions, 2).rows.map(q => q.id), [11,12,13,14,15,16,17,18,19,20]);
  assert.deepEqual(tablePage(questions, 3).rows.map(q => q.id), [21,22,23]);
});
test('filtered libraries clamp pages without dropping results', () => {
  const filtered = questions.filter(q => q.topic === 'Beta');
  const result = tablePage(filtered, 99);
  assert.equal(result.page, 2);
  assert.equal(result.pages, 2);
  assert.deepEqual(result.rows.map(q => q.id), [22,23]);
});
test('empty and invalid page selections are safe', () => {
  assert.deepEqual(tablePage([], 99), { pages: 1, page: 1, start: 0, rows: [] });
  assert.equal(tablePage(questions, -4).page, 1);
  assert.throws(() => tablePage(questions, 1, 0), RangeError);
});
test('source viewer resolves explicit PDF page and German metadata', () => {
  assert.equal(sourcePage({source_location:'page 37, lines 4-9'}),37);
  assert.equal(sourcePage({source_start:12,source_location:'page 3'}),12);
  assert.equal(sourcePage({source_location:'Seite 23'}),23);
  assert.equal(sourcePage({source_location:'appendix'}),undefined);
  assert.equal(sourcePage({source_start:-1,source_location:'page 0'}),undefined);
});
