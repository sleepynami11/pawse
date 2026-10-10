export function pcm16Base64(samples) {
  const bytes = new Uint8Array(samples.length * 2), view = new DataView(bytes.buffer);
  for (let i=0;i<samples.length;i++) view.setInt16(i*2, Math.round(Math.max(-1,Math.min(1,samples[i]))*32767), true);
  let s=''; for (let i=0;i<bytes.length;i+=8192) s+=String.fromCharCode(...bytes.subarray(i,i+8192));
  return btoa(s);
}
export function decodePCM(data) {
  const raw=atob(data); if (raw.length%2) throw Error('Invalid PCM frame');
  const bytes=Uint8Array.from(raw,c=>c.charCodeAt(0)), view=new DataView(bytes.buffer), out=new Float32Array(bytes.length/2);
  for(let i=0;i<out.length;i++) out[i]=view.getInt16(i*2,true)/32768;
  return out;
}
export function createNativeAudio(onFrame, onSpeaking) {
  const AC=globalThis.AudioContext || globalThis.webkitAudioContext;
  if (!AC) throw Error('Native audio is unavailable in this browser.');
  const output=new AC({sampleRate:24000});
  output.resume().catch(()=>{});
  let input=null, source=null, worklet=null, stream=null, closed=false, muted=false, inputGeneration=0, attachRequest=0;
  let epoch=0; let next=0; const playing=new Set();
  function flush() { epoch++; for(const s of playing) {try{s.stop();}catch{}} playing.clear();next=0;onSpeaking(false); }
  async function detach() {
    inputGeneration++;
    if(worklet) {worklet.port.onmessage=null;worklet.disconnect();worklet=null;}
    source?.disconnect();source=null;
    stream?.getTracks().forEach(t=>t.stop());stream=null;
    if(input) {const c=input;input=null;await c.close().catch(()=>{});}
  }
  return {
    async attach(media) {
      if(media===stream) return;
      const request=++attachRequest;
      await detach(); if(!media||closed||request!==attachRequest) return;
      const generation=++inputGeneration;
      stream=media; input=new AC({sampleRate:16000}); const ctx=input;
      await ctx.audioWorklet.addModule(new URL('../audio/pcm-worklet.js', import.meta.url));
      if(closed||generation!==inputGeneration) return;
      await ctx.resume();
      if(closed||generation!==inputGeneration) return;
      source=ctx.createMediaStreamSource(media);worklet=new AudioWorkletNode(ctx,'pawse-pcm');
      worklet.port.onmessage=e=>{if(!closed) onFrame(pcm16Base64(e.data));};
      source.connect(worklet); worklet.connect(ctx.destination); // processor outputs silence
    },
    async play(data, rate=24000) {
      if(closed||muted) return;
      if(!Number.isFinite(rate)||rate<8000||rate>48000) throw Error('Invalid audio rate');
      const samples=decodePCM(data);
      if(!samples.length) return;
      if(Math.max(next,output.currentTime)+samples.length/rate-output.currentTime>15) throw Error('Audio playback cannot keep up. Restart the session.');
      const generation=epoch;await output.resume(); if(closed||muted||generation!==epoch) return;
      const buffer=output.createBuffer(1,samples.length,rate);buffer.copyToChannel(samples,0);
      const node=output.createBufferSource();node.buffer=buffer;node.connect(output.destination);
      node.onended=()=>{playing.delete(node);node.disconnect();if(!playing.size) onSpeaking(false);};
      playing.add(node);onSpeaking(true);next=Math.max(next,output.currentTime);node.start(next);next+=buffer.duration;
    },
    flush,
    setMuted(value){muted=value;if(value)flush();},
    async close(){closed=true;flush();await detach();await output.close().catch(()=>{});},
  };
}
