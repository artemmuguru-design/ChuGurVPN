const express=require('express');
const http=require('http');
const WebSocket=require('ws');
const path=require('path');

const app=express();
const server=http.createServer(app);
const wss=new WebSocket.Server({server});

const PORT=process.env.PORT||3000;

app.use(express.static(path.join(__dirname,'public')));

let messages=[];
let users=new Map();

wss.on('connection',(ws)=>{
ws.id=Date.now();
ws.username=null;
console.log('[+] Новое подключение, id:',ws.id);

ws.on('message',(raw)=>{
try{
const msg=JSON.parse(raw);
console.log('[MSG]',msg.type,'от',ws.username||'аноним',':',msg);

if(msg.type==='login'){
ws.username=msg.username;
users.set(ws.id,ws);
console.log('[LOGIN]',ws.username,'вошёл');

ws.send(JSON.stringify({
type:'history',
messages:messages.slice(-50)
}));

broadcast({
type:'user_joined',
username:ws.username,
users:Array.from(users.values()).map(u=>u.username)
});
}
else if(msg.type==='message'){
if(!ws.username){
console.log('[!] Сообщение без логина, игнорирую');
return;
}
const message={
id:Date.now(),
username:ws.username,
text:msg.text,
time:new Date().toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'})
};

messages.push(message);
if(messages.length>100)messages.shift();

console.log('[MESSAGE]',ws.username+':',msg.text);

broadcast({
type:'message',
message:message
});
}
}catch(e){
console.error('[ERR]',e);
}
});

ws.on('close',()=>{
if(ws.username){
users.delete(ws.id);
console.log('[-]',ws.username,'вышел');
broadcast({
type:'user_left',
username:ws.username,
users:Array.from(users.values()).map(u=>u.username)
});
}
});

ws.on('error',(e)=>console.error('[WS-ERR]',e.message));
});

function broadcast(msg,excludeId=null){
const data=JSON.stringify(msg);
users.forEach((ws,id)=>{
if(id!==excludeId&&ws.readyState===WebSocket.OPEN){
try{ws.send(data)}catch(e){}
}
});
}

server.listen(PORT,'0.0.0.0',()=>{
console.log('🚀 Messenger server on port',PORT);
console.log(' Public folder:',path.join(__dirname,'public'));
});
