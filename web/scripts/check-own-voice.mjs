import assert from 'node:assert/strict';
import {prepareGermanPreview} from '../src/agents/ownVoice.js';
let calls=[], updates=[], stages=[];
const args={profile:{},sample:'synthetic',language:'en',onProfile:p=>updates.push(p),onStage:s=>stages.push(s),wait:async()=>{},api:async(path)=>{calls.push(path);return path==='clone'?{source_id:'s'}:path==='localizations'?{source_id:'s',candidate_pending:true}:path==='localizations/current'?{source_id:'s',candidate_pending:true,candidate_ready:true}:new Blob(['wav']);}};
assert.ok(await prepareGermanPreview(args) instanceof Blob);
assert.deepEqual(calls,['clone','localizations','localizations/current','preview']);assert.equal(updates.length,3);
calls=[];await prepareGermanPreview({...args,profile:{source_id:'s',german_voice_id:'g'}});assert.deepEqual(calls,['preview']);
calls=[];await assert.rejects(()=>prepareGermanPreview({...args,profile:{source_id:'s',candidate_pending:true},api:async p=>{calls.push(p);return {source_id:'s',candidate_pending:true};}}),/still preparing/);assert.equal(calls.length,20);assert.ok(calls.every(p=>p==='localizations/current'));
console.log('check-own-voice: staged clone/localize/preview, resume and bounded polling OK');
