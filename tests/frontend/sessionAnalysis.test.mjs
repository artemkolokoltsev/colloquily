import test from 'node:test';
import assert from 'node:assert/strict';
import { analyseSession } from '../../frontend/src/features/sessionAnalysis.ts';
const attempt = (id, status, score) => ({id, question_text:`Question ${id}`, evaluation:{status,score}});
test('session analysis separates ungraded and skipped answers from valid zero scores', () => {
  const result = analyseSession({sessions:[{subject_id:1,attempts:[attempt(1,'evaluated',0),attempt(2,'evaluated',4),attempt(3,'skipped',0),attempt(4,'pending',0),attempt(5,'needs_review',0),attempt(6,'internal_error',0)]}]});
  assert.equal(result.mean,2);
  assert.equal(result.graded.length,2);
  assert.equal(result.skipped,1);
  assert.equal(result.ungraded,3);
  assert.deepEqual(result.improvements.map(item=>item.id),[1]);
});
test('empty sessions and invalid scores never produce invented grades', () => {
  assert.equal(analyseSession({sessions:[]}).mean,null);
  assert.equal(analyseSession({sessions:[{attempts:[attempt(1,'evaluated',NaN),attempt(2,'evaluated',8)]}]}).mean,null);
});
test('improvement suggestions prioritize weakest evaluated answers across subjects', () => {
  const result=analyseSession({sessions:[{subject_id:1,attempts:[attempt(1,'evaluated',3),attempt(2,'evaluated',2)]},{subject_id:2,attempts:[attempt(3,'evaluated',1),attempt(4,'evaluated',0)]}]});
  assert.deepEqual(result.improvements.map(item=>item.id),[4,3,2]);
  assert.equal(result.improvements[0].subjectId,2);
});
