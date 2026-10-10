// Weighted resampling into 20 ms, 16 kHz mono frames. Never sends browser audio back to speakers.
class PawsePCM extends AudioWorkletProcessor {
  constructor(){super();this.frame=new Float32Array(320);this.n=0;this.sum=0;this.weight=0;}
  process(inputs){
    const channels=inputs[0]; if(!channels?.length) return true;
    const ratio=sampleRate/16000;
    for(let i=0;i<channels[0].length;i++){
      let value=0;for(const c of channels)value+=c[i]/channels.length;
      let left=1;
      while(left>1e-8){
        const part=Math.min(left,ratio-this.weight);this.sum+=value*part;this.weight+=part;left-=part;
        if(this.weight>=ratio-1e-8){
          this.frame[this.n++]=this.sum/ratio;this.sum=0;this.weight=0;
          if(this.n===320){this.port.postMessage(this.frame);this.frame=new Float32Array(320);this.n=0;}
        }
      }
    }
    return true;
  }
}
registerProcessor('pawse-pcm',PawsePCM);
