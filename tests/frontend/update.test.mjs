import test from 'node:test';
import assert from 'node:assert/strict';
import { UpdateController } from '../../frontend/src/updateController.ts';
function fixture(overrides = {}, artifactOverrides = {}) {
  const events = [];
  const artifact = {version: '0.1.7', download: async progress => { events.push('download'); progress({event:'Started',data:{contentLength:100}}); progress({event:'Progress',data:{chunkLength:100}}); progress({event:'Finished'}); }, install: async () => { events.push('install'); }, close: async () => {}, ...artifactOverrides};
  const controller = new UpdateController({check: async () => {events.push('check'); return artifact;}, safe: async () => true, begin: async () => {events.push('backup');}, cancel: async () => {events.push('cancel');}, relaunch: async () => {events.push('restart');}, ...overrides});
  return {controller, events, artifact};
}
test('checks are deduplicated and downloaded artifacts are retained', async () => {
  const {controller, events} = fixture();
  await Promise.all([controller.check(), controller.check()]);
  await controller.download(); await controller.check();
  assert.deepEqual(events, ['check','download']); assert.equal(controller.state.progress,100);
});
test('verified download precedes backup, installation and restart', async () => {
  const {controller,events} = fixture(); await controller.check(); await controller.install();
  assert.deepEqual(events,['check','download','backup','install','restart']);
});
test('signature/download failure cannot reserve workspace or install', async () => {
  const {controller,events} = fixture({}, {download: async () => {throw Error('bad signature');}});
  await controller.check(); await assert.rejects(controller.install(), /bad signature/);
  assert.deepEqual(events,['check']); assert.equal(controller.downloaded,false);
});
test('busy workspace postpones installation', async () => {
  const {controller,events} = fixture({safe: async () => false}); await controller.check(); await controller.install();
  assert.deepEqual(events,['check','download']); assert.equal(controller.state.phase,'ready');
});
test('server can reject a race before backup without installing', async () => {
  const {controller,events} = fixture({begin: async () => {throw Error('busy');}}); await controller.check(); await assert.rejects(controller.install());
  assert.deepEqual(events,['check','download','cancel']);
});
test('restart failure unlocks workspace; retry does not reinstall', async () => {
  let fail = true;
  const {controller,events} = fixture({relaunch: async () => {if (fail) throw Error('restart');}});
  await controller.check(); await assert.rejects(controller.install()); fail=false; await controller.install();
  assert.deepEqual(events,['check','download','backup','install','cancel','backup']);
});
test('offline checks can retry and never claim current', async () => {
  let offline = true;
  const {controller} = fixture({check: async () => {if(offline) throw Error('offline'); return null;}});
  await assert.rejects(controller.check()); assert.equal(controller.state.phase,'error');
  offline = false; await controller.check(); assert.equal(controller.state.phase,'current');
});
