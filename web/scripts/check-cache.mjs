import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
const handlers = {};
vm.runInNewContext(fs.readFileSync(new URL('../public/sw.js', import.meta.url),'utf8'), {
 self: {location: {origin:'https://pawse.example'}, addEventListener:(n,f)=>handlers[n]=f}, URL,
 fetch: () => new Promise(()=>{}),
});
for (const path of ['/api/v1/voice/status','/api/v1/care/requests/private','/api/v1/demo/mimi','/app/?live=1']) {
 let intercepted=false;
 handlers.fetch({request:{method:'GET',url:`https://pawse.example${path}`},respondWith:()=>{intercepted=true;}});
 assert.equal(intercepted,false, `Never cache private/API/query requests: ${path}`);
}
console.log('check-cache: private and query requests bypass cache');
