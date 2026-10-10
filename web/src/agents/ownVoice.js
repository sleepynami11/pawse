// One source clone and one German candidate per run; poll only the read endpoint.
export async function prepareGermanPreview({api, profile, sample, language, signal, onProfile, onStage, wait=delay}) {
  let p=profile;
  if(!p.source_id){
    onStage('Uploading your recording and cloning your voice…');
    p=await api('clone',{audio:{data:sample},sample_language:language,own_voice_consent:true,share_with_gradium:true},false,signal);
    onProfile(p);
  }
  if(!p.german_voice_id&&!p.candidate_pending){
    onStage('Your source voice is saved. Creating its German version…');
    p=await api('localizations',{share_with_gradium:true},false,signal);onProfile(p);
  }
  for(let i=0;!p.german_voice_id&&!p.candidate_ready&&i<20;i++){
    onStage('Gradium is preparing your German voice. Checking readiness…');
    await wait(3000,signal);
    p=await api('localizations/current',null,false,signal);onProfile(p);
  }
  if(!p.german_voice_id&&!p.candidate_ready)throw Error('Your German voice is still preparing. Click Continue to check again; do not record another sample.');
  onStage('Generating your German audio preview…');
  const audio=await api('preview',{share_with_gradium:true},true,signal);
  onStage('German preview ready. Press Play, then approve it if it sounds like you.');
  return audio;
}
function delay(ms,signal){return new Promise((resolve,reject)=>{
  if(signal?.aborted)return reject(new DOMException('Aborted','AbortError'));
  const abort=()=>{clearTimeout(timer);reject(new DOMException('Aborted','AbortError'));};
  const timer=setTimeout(()=>{signal?.removeEventListener('abort',abort);resolve();},ms);
  signal?.addEventListener('abort',abort,{once:true});
});}
