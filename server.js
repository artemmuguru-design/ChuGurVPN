const WebSocket=require('ws');
const http=require('http');
const PORT=process.env.PORT||3000;
const server=http.createServer((req,res)=>{res.writeHead(200);res.end('ok - drone server alive')});
const wss=new WebSocket.Server({server});
const servers={1:{players:new Map(),max:10},2:{players:new Map(),max:10}};
let nextId=1;
wss.on('connection',(ws,req)=>{
ws.id=nextId++;ws.serverId=null;ws.pos={x:0,y:0,z:0,ry:0};ws.isDrone=false;ws.dronePos=null;ws.isAlive=true;
console.log('[+] Player '+ws.id+' connected');
ws.on('pong',()=>{ws.isAlive=true});
ws.on('message',(raw)=>{
try{const msg=JSON.parse(raw);
if(msg.type==='join'){const sid=msg.serverId;if(!servers[sid])return;if(servers[sid].players.size>=servers[sid].max){ws.send(JSON.stringify({type:'error',msg:'Full'}));return}ws.serverId=sid;servers[sid].players.set(ws.id,ws);broadcast(sid,{type:'player_joined',id:ws.id,x:0,y:0,z:0,ry:0});const ex=[];servers[sid].players.forEach((p,pid)=>{if(pid!==ws.id)ex.push({id:pid,x:p.pos.x,y:p.pos.y,z:p.pos.z,ry:p.pos.ry,isDrone:p.isDrone,dronePos:p.dronePos})});ws.send(JSON.stringify({type:'welcome',id:ws.id,serverId:sid,count:servers[sid].players.size,players:ex}));console.log('[JOIN] P'+ws.id+' S'+sid+' ('+servers[sid].players.size+'/10)')}
else if(msg.type==='move'){ws.pos={x:msg.x,y:msg.y,z:msg.z,ry:msg.ry};broadcast(ws.serverId,{type:'player_move',id:ws.id,x:msg.x,y:msg.y,z:msg.z,ry:msg.ry},ws.id)}
else if(msg.type==='drone_enter'){ws.isDrone=true;ws.dronePos={x:msg.x,y:msg.y,z:msg.z,ry:msg.ry};broadcast(ws.serverId,{type:'player_drone_enter',id:ws.id,x:msg.x,y:msg.y,z:msg.z,ry:msg.ry},ws.id)}
else if(msg.type==='drone_move'){ws.dronePos={x:msg.x,y:msg.y,z:msg.z,ry:msg.ry};broadcast(ws.serverId,{type:'player_drone_move',id:ws.id,x:msg.x,y:msg.y,z:msg.z,ry:msg.ry},ws.id)}
else if(msg.type==='drone_exit'){ws.isDrone=false;ws.dronePos=null;broadcast(ws.serverId,{type:'player_drone_exit',id:ws.id,x:ws.pos.x,y:ws.pos.y,z:ws.pos.z,ry:ws.pos.ry},ws.id)}
else if(msg.type==='drone_explode'){broadcast(ws.serverId,{type:'player_drone_explode',id:ws.id,x:msg.x,y:msg.y,z:msg.z},ws.id)}
else if(msg.type==='chat'){broadcast(ws.serverId,{type:'chat',id:ws.id,text:msg.text})}
}catch(e){console.error('[ERR]',e)}});
ws.on('close',()=>{if(ws.serverId&&servers[ws.serverId].players.has(ws.id)){servers[ws.serverId].players.delete(ws.id);broadcast(ws.serverId,{type:'player_left',id:ws.id});console.log('[-] P'+ws.id+' left')}});
ws.on('error',(e)=>{console.error('[WS-ERR]',e.message)})});
function broadcast(sid,msg,exId){if(!sid||!servers[sid])return;const d=JSON.stringify(msg);servers[sid].players.forEach((p,pid)=>{if(pid!==exId&&p.readyState===WebSocket.OPEN)try{p.send(d)}catch(e){}})}
setInterval(()=>{wss.clients.forEach((ws)=>{if(ws.isAlive===false)return ws.terminate();ws.isAlive=false;try{ws.ping()}catch(e){}});const s1=servers[1].players.size,s2=servers[2].players.size;broadcast(1,{type:'status',s1,s2});broadcast(2,{type:'status',s1,s2})},25000);
server.listen(PORT,()=>{console.log('NEW VERSION - Server on port '+PORT)});
