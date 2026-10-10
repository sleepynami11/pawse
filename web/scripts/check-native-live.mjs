import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createGeminiLiveAgent} from '../src/agents/geminiLiveAgent.js';
import {pcm16Base64,decodePCM,createNativeAudio} from '../src/agents/nativeAudio.js';
import {micLevel} from '../src/hooks/useMicLevel.js';
assert.equal(micLevel(new Float32Array(512)),0);assert.equal(micLevel(new Float32Array(512).fill(1)),1);
assert.ok(micLevel(new Float32Array(512).fill(.05))>.3,'normal speech moves the meter');
const decoded=decodePCM(pcm16Base64(new Float32Array([-1,0,.5,1])));
assert.equal(decoded.length,4);assert.ok(Math.abs(decoded[2]-.5)<.001);assert.ok(decoded[0]<-.99);
assert.throws(()=>decodePCM(btoa('x')), /Invalid/);
for(const rate of [16000,44100,48000]){
 let Processor,frames=[];
 vm.runInNewContext(fs.readFileSync(new URL('../src/audio/pcm-worklet.js',import.meta.url),'utf8'),{
  AudioWorkletProcessor:class {constructor(){this.port={postMessage:x=>frames.push(x)}}},sampleRate:rate,Float32Array,registerProcessor:(name,type)=>Processor=type,
 });
 const processor=new Processor();
 processor.process([[new Float32Array(rate).fill(.25)]]);
 assert.equal(frames.length,50,`${rate} -> exactly 50 frames per second`);
 assert.equal(frames[0].length,320);assert.ok(Math.abs(frames[0][0]-.25)<1e-5);
}
let callbacks, sent=[], tools=[], played=[], requests=[], closed=0, flushed=0, audioClosed=0, factoryOptions;
let onFrame;
const fakeSession={sendRealtimeInput:p=>sent.push(p),sendToolResponse:p=>tools.push(p),close:()=>closed++};
const fakeAudio={setMuted(){},attach:async()=>{},flush:()=>flushed++,close:async()=>{audioClosed++;},play:async(data,rate)=>played.push({data,rate})};
const options={lang:'hi',shareWithGemini:true,audioFactory:(frame)=>{onFrame=frame;return fakeAudio;},clientFactory:opts=>{factoryOptions=opts;return {live:{connect:async opts=>{callbacks=opts.callbacks;return fakeSession;}}}}};
globalThis.fetch=async(url,init)=>{
 const body=JSON.parse(init.body);requests.push({url,body});
 return {ok:true,json:async()=>url.endsWith('tokens')?{token:'test-token',model:'test-live',api_version:'v1alpha'}:{response:{status:'ok'},ui:{care:{assessment:{urgency:'emergency',summary:'Contact a vet now',questions:[]}},trace:[]}}};
};

const denied=createGeminiLiveAgent({...options,shareWithGemini:false});await denied.start();assert.equal(requests.length,0);denied.end();
const agent=createGeminiLiveAgent(options), events=[];agent.on(e=>events.push(e));await agent.start();
assert.equal(factoryOptions.apiKey,'test-token');assert.equal(requests[0].body.language,'hi');
agent.setMicMuted(false);onFrame('AA==');assert.equal(sent.at(-1).audio.mimeType,'audio/pcm;rate=16000');
agent.setMicMuted(true);const count=sent.length;onFrame('AA==');assert.equal(sent.length,count);assert.equal(sent.at(-1).audioStreamEnd,true);
callbacks.onmessage({serverContent:{inputTranscription:{text:'hello'},outputTranscription:{text:'reply'},modelTurn:{parts:[{inlineData:{data:'AAA=',mimeType:'audio/pcm;rate=24000'}},{inlineData:{data:'AAA=',mimeType:'audio/pcm;rate=24000'}}]}}});
await new Promise(r=>setTimeout(r,0));assert.equal(played.length,2);assert.ok(events.some(e=>e.role==='user'&&e.text==='hello'));assert.ok(events.some(e=>e.role==='ai'));
// The owner's words stream in as partial captions and are sealed once Pawse answers.
const mark=events.length;
callbacks.onmessage({serverContent:{inputTranscription:{text:'my cat '}}});
callbacks.onmessage({serverContent:{inputTranscription:{text:'is limping'}}});
let mine=events.slice(mark).filter(e=>e.type==='transcript'&&e.role==='user');
assert.deepEqual(mine.map(e=>[e.text,e.partial]),[['hellomy cat ',true],['hellomy cat is limping',true]]);
callbacks.onmessage({serverContent:{turnComplete:true}});
mine=events.slice(mark).filter(e=>e.type==='transcript'&&e.role==='user');
assert.deepEqual([mine.at(-1).text,mine.at(-1).partial],['hellomy cat is limping',false]);
callbacks.onmessage({serverContent:{inputTranscription:{text:'since today'}}});
callbacks.onmessage({serverContent:{outputTranscription:{text:'I see'}}});
mine=events.slice(mark).filter(e=>e.type==='transcript'&&e.role==='user');
assert.deepEqual(mine.slice(-2).map(e=>[e.text,e.partial]),[['since today',true],['since today',false]]);
callbacks.onmessage({serverContent:{turnComplete:true}});
callbacks.onmessage({serverContent:{interrupted:true}});assert.ok(flushed);
const call={id:'call1',name:'assess_and_find_vets',args:{concern:'test'}};
callbacks.onmessage({toolCall:{functionCalls:[call,call]}});
await new Promise(r=>setTimeout(r,0));assert.equal(tools.length,1);assert.equal(tools[0].functionResponses[0].id,'call1');assert.ok(events.some(e=>e.type==='triage'&&e.level==='red'));
assert.equal(requests.at(-1).body.context.share_location,false);
agent.end();agent.end();assert.equal(closed,1);assert.equal(audioClosed,1);assert.equal(events.filter(e=>e.type==='ended').length,1);
const requestCount=requests.length;callbacks.onmessage({toolCall:{functionCalls:[{...call,id:'late'}]}});assert.equal(requests.length,requestCount);
// A location the browser grants goes with the clinic search; without one the server uses central Zurich.
const located=createGeminiLiveAgent({...options,locate:async()=>({lat:47.5,lng:8.7})});await located.start();
callbacks.onmessage({toolCall:{functionCalls:[{...call,id:'call-loc'}]}});await new Promise(r=>setTimeout(r,0));
assert.equal(requests.at(-1).body.context.share_location,true);assert.deepEqual(requests.at(-1).body.context.location,{lat:47.5,lng:8.7});
located.end();
globalThis.fetch=async()=>({ok:false,status:503,json:async()=>({detail:'Live unavailable'})});
const fail=createGeminiLiveAgent(options), errors=[];fail.on(e=>errors.push(e));await fail.start();assert.ok(errors.some(e=>e.type==='error'));assert.equal(errors.filter(e=>e.type==='ended').length,1);
console.log('check-native-live: consent, PCM/resampling, all audio parts, transcripts, interruption, tool round trip, mute/end and token errors OK');

// Rapid media replacement must never attach a stale stream or leave a context open.
const contexts=[], attached=[];
globalThis.AudioContext=class {
 constructor(){this.audioWorklet={addModule:async()=>{}};this.destination={};this.closed=false;contexts.push(this);}
 async resume(){} async close(){this.closed=true;}
 createMediaStreamSource(media){attached.push(media.id);return {connect(){},disconnect(){}};}
};
globalThis.AudioWorkletNode=class {constructor(){this.port={};}connect(){}disconnect(){}};
const media=id=>({id,getTracks:()=>[{stop(){}}]});
const native=createNativeAudio(()=>{},()=>{});
await Promise.all([native.attach(media('stale')),native.attach(media('current'))]);
assert.deepEqual(attached,['current']);await native.close();assert.ok(contexts.every(x=>x.closed));
