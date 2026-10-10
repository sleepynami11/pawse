import { GoogleGenAI } from '@google/genai';
import { VOICE_AGENT_URL } from '../config.js';
import { mapCareResult } from './liveVoiceAgent.js';
import { createNativeAudio } from './nativeAudio.js';
import { loadInsuranceProfile, saveInsuranceProfile } from './insuranceProfile.js';
import { getLocation } from './location.js';

// Injectable transport/audio factories keep protocol tests offline and deterministic.
export function createGeminiLiveAgent({lang='en',shareWithGemini=false,
  clientFactory=options=>new GoogleGenAI(options), audioFactory=createNativeAudio, locate=getLocation}={}) {
  const listeners=new Set(), pending=new Set(), toolIds=new Set(), cancelledTools=new Set();
  let started=false, ended=false, session=null, audio=null, media=null, muted=true, outputMuted=false, timer=null;
  let audioEpoch=0;
  // Asked once at start; the server searches around central Zurich when this resolves null.
  let located=Promise.resolve(null);
  let inputText='',outputText='', userOpen=false, playback=Promise.resolve();
  // The owner's words stream in as a partial caption; the first sign of Pawse answering seals them.
  const sealUser=()=>{if(userOpen){userOpen=false;emit({type:'transcript',role:'user',text:inputText,partial:false});}};
  const emit=e=>{if(!ended||e.type==='ended') for(const fn of listeners){try{fn(e);}catch{}}};
  const error=message=>emit({type:'error',message});
  async function post(path,body){
    const ctl=new AbortController();pending.add(ctl);const timeout=setTimeout(()=>ctl.abort(),55000);
    try{
      const r=await fetch(`${VOICE_AGENT_URL || ''}/api/v1/live/${path}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:ctl.signal});
      if(!r.ok){const j=await r.json().catch(()=>({}));throw Error(typeof j.detail==='string'?j.detail:`Live request failed (${r.status})`);}
      return await r.json();
    }finally{clearTimeout(timeout);pending.delete(ctl);}
  }
  function end(){
    if(ended)return;ended=true;clearTimeout(timer);
    for(const c of pending)c.abort();pending.clear();
    try{session?.close();}catch{}session=null;
    media?.getTracks().forEach(t=>t.stop());media=null;
    audio?.close().catch(()=>{});emit({type:'ended'});
  }
  function send(payload){if(!ended&&session)session.sendRealtimeInput(payload);}
  async function tool(call){
    if(!call.id||toolIds.has(call.id)||ended)return;
    toolIds.add(call.id);
    if(toolIds.size>100){error('Session tool limit reached. Start a new session.');end();return;}
    emit({type:'tool_status',name:call.name,state:'running'});
    let response;
    try{
      const location=call.name==='assess_and_find_vets'?await located:null;
      const result=await post('tool-calls',{id:call.id,name:call.name,args:call.args||{},share_with_gemini:true,context:{language:lang,share_location:!!location,...(location?{location}:{}),insurance:loadInsuranceProfile()}});
      response=result.response;
      if(ended||cancelledTools.has(call.id))return;
      const ui=result.ui;
      if(ui?.action==='save_insurance_profile')saveInsuranceProfile(ui);
      if(ui?.care){emit({type:'agents',trace:ui.trace||[],actions:[]});emit(mapCareResult(ui.care,lang));}
      else if(ui)emit({type:'tool_result',name:call.name,ui});
    }catch(e){response={error:'tool_unavailable',detail:e.message};}
    if(!ended&&!cancelledTools.has(call.id)&&session){
      session.sendToolResponse({functionResponses:[{id:call.id,name:call.name,response}]});
      emit({type:'tool_status',name:call.name,state:response?.error?'unavailable':'complete'});
    }
  }
  function message(msg){
    if(ended)return;
    try{
      for(const id of msg.toolCallCancellation?.ids||[])cancelledTools.add(id);
      const c=msg.serverContent;
      if(c?.interrupted){audioEpoch++;audio.flush();sealUser();inputText='';outputText='';}
      if(c?.inputTranscription?.text){inputText+=c.inputTranscription.text;userOpen=true;emit({type:'transcript',role:'user',text:inputText,partial:true});}
      if(c?.outputTranscription?.text){sealUser();outputText+=c.outputTranscription.text;emit({type:'transcript',role:'ai',text:outputText});}
      for(const part of c?.modelTurn?.parts||[]){
        const data=part.inlineData;
        if(data?.data&&data.mimeType?.startsWith('audio/pcm')){
          const rate=Number(/rate=(\d+)/.exec(data.mimeType)?.[1]||24000);
          const epoch=audioEpoch;
          playback=playback.then(()=>{if(!ended && epoch===audioEpoch)return audio.play(data.data,rate);}).catch(()=>{error('Native audio playback failed. Restart the session.');end();});
        }
      }
      if(c?.turnComplete){sealUser();inputText='';outputText='';emit({type:'listening',on:!muted});}
      if(msg.toolCall)sealUser();
      for(const call of msg.toolCall?.functionCalls||[]) void tool(call).catch(()=>error('Tool response could not be delivered.'));
      if(msg.goAway){error('Live session is ending. Start a new conversation.');end();}
    }catch{error('Live response could not be processed.');end();}
  }
  return {
    wantsAudio:true,on(fn){listeners.add(fn);return()=>listeners.delete(fn);},
    async start(){
      if(started||ended)return;
      if(!shareWithGemini){error('Confirm sharing with Gemini before starting.');return;}
      started=true;
      located=Promise.resolve(locate()).catch(()=>null);
      try{
        audio=audioFactory(frame=>{if(!muted&&session&&!ended)send({audio:{data:frame,mimeType:'audio/pcm;rate=16000'}});}, speaking=>emit({type:'speaking',who:speaking?'ai':'none'}));
        audio.setMuted(outputMuted);
        const token=await post('tokens',{language:lang,share_with_gemini:true});if(ended)return;
        const ai=clientFactory({apiKey:token.token,httpOptions:{apiVersion:token.api_version}});
        const connected=await ai.live.connect({model:token.model,config:{responseModalities:['AUDIO']},callbacks:{onmessage:message,onerror:()=>{error('Gemini Live connection failed. Restart or use text fallback.');end();},onclose:()=>{if(!ended){error('Gemini Live disconnected. Start a new session.');end();}}}});
        if(ended){connected.close();return;}session=connected;
        timer=setTimeout(()=>{error('Session time limit reached. Start a new conversation.');end();},8*60*1000);
        if(media&&!muted)await audio.attach(media);
        emit({type:'listening',on:!muted});
        send({text:'Introduce yourself briefly as Pawse, an AI cat-care assistant, and ask how you can help. Do not invent a concern.'});
      }catch(e){if(!ended){error(e.message?.includes('key')?'Live audio could not start. Check server configuration.':e.message||'Live audio could not start.');end();}}
    },
    end,
    sendText(text){if(!session){error('Wait for the Live connection, then try again.');return;}const s=String(text||'').trim();if(!s||s.length>4000)return;audio.flush();userOpen=false;inputText='';outputText='';send({text:s});emit({type:'transcript',role:'user',text:s});},
    async sendImage(file){
      if(!session||ended)return;
      if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>3000000){error('Use JPEG, PNG or WebP up to 3 MB.');return;}
      const bytes=new Uint8Array(await file.arrayBuffer());let data='';for(let i=0;i<bytes.length;i+=8192)data+=String.fromCharCode(...bytes.subarray(i,i+8192));
      if(!ended){send({video:{data:btoa(data),mimeType:file.type}});emit({type:'image_received'});}
    },
    attachMedia({audio:stream}={}){media=stream;if(audio&&session)audio.attach(muted?null:media).catch(()=>error('Microphone streaming failed. You can still type.'));},
    setMicMuted(value){muted=!!value;if(session){if(muted)send({audioStreamEnd:true});audio.attach(muted?null:media).catch(()=>error('Microphone unavailable. You can still type.'));}emit({type:'listening',on:!!session&&!muted});},
    setOutputMuted(value){outputMuted=!!value;audio?.setMuted(outputMuted);},
  };
}
