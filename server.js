const WebSocket=require('ws');
const http=require('http');
const fs=require('fs');
const path=require('path');

const PORT=process.env.PORT||3000;

const server=http.createServer((req,res)=>{
if(req.url==='/'||req.url==='/index.html'){
const filePath=path.join(__dirname,'index.html');
fs.readFile(filePath,(err,data)=>{
if(err){
console.error('❌ Cannot find index.html');
res.writeHead(500);
res.end('Error: index.html not found');
return;
}
res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});
res.end(data);
});
}else if(req.url==='/health'){
res.writeHead(200);
res.end('ok');
}else{
res.writeHead(404);
res.end('Not found');
}
});

const wss=new WebSocket.Server({server});
const servers={1:{players:new Map(),max:10},2:{players:new Map(),max:10}};
let nextId=1;

function broadcast(sid,msg,exId){
if(!sid||!servers[sid])return;
const d=JSON.stringify(msg);
servers[sid].players.forEach((p,pid)=>{
if(pid!==exId&&p.readyState===WebSocket.OPEN){
try{p.send(d)}catch(e){}
}
});
}

function sendStatus(){
const s1=servers[1].players.size;
const s2=servers[2].players.size;
const msg=JSON.stringify({type:'status',s1,s2});
wss.clients.forEach(ws=>{
if(ws.readyState===WebSocket.OPEN){
try{ws.send(msg)}catch(e){}
}
});
}

wss.on('connection',(ws)=>{
ws.id=nextId++;
ws.serverId=null;
ws.isAlive=true;
console.log('[+] Player',ws.id,'connected');

ws.on('pong',()=>{ws.isAlive=true});

ws.on('message',(raw)=>{
try{
const msg=JSON.parse(raw);
if(msg.type==='join'){
const sid=parseInt(msg.serverId);
if(!servers[sid]){
ws.send(JSON.stringify({type:'error',msg:'Invalid server'}));
return;
}
if(servers[sid].players.size>=servers[sid].max){
ws.send(JSON.stringify({type:'error',msg:'Server full'}));
return;
}
ws.serverId=sid;
servers[sid].players.set(ws.id,ws);
broadcast(sid,{type:'player_joined',id:ws.id},ws.id);
ws.send(JSON.stringify({type:'welcome',id:ws.id,serverId:sid,count:servers[sid].players.size,players:[]}));
console.log('[JOIN] P'+ws.id+'-> S'+sid);
sendStatus();
}
}catch(e){
console.error('[ERR]',e);
}
});

ws.on('close',()=>{
if(ws.serverId&&servers[ws.serverId].players.has(ws.id)){
const sid=ws.serverId;
servers[sid].players.delete(ws.id);
broadcast(sid,{type:'player_left',id:ws.id});
console.log('[-] P'+ws.id+'left');
sendStatus();
}
});

ws.on('error',(e)=>console.error('[WS-ERR]',e.message));
});

setInterval(()=>{
wss.clients.forEach(ws=>{
if(ws.isAlive===false)return ws.terminate();
ws.isAlive=false;
try{ws.ping()}catch(e){}
});
sendStatus();
},15000);

server.listen(PORT,'0.0.0.0',()=>{
console.log('🚀 Server on port',PORT);
console.log('📁 Looking for index.html in:',__dirname);
});
