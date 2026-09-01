const express=require('express');
const http=require('http');
const WebSocket=require('ws');
const path=require('path');
const fs=require('fs');

const app=express();
const server=http.createServer(app);
const wss=new WebSocket.Server({server});
const PORT=process.env.PORT||3000;

app.use(express.json({limit:'5mb'}));
app.use(express.static(path.join(__dirname,'public')));

// База данных в памяти
let users=new Map(); // username -> {ws, lastSeen, avatar}
let messages=[]; // общие сообщения
let privateMessages=new Map(); // "user1_user2" -> [messages]
let bannedNames=new Set();

// Загрузка из файла при старте
const DATA_FILE=path.join(__dirname,'data.json');
function loadData(){
try{
if(fs.existsSync(DATA_FILE)){
const d=JSON.parse(fs.readFileSync(DATA_FILE,'utf8'));
messages=d.messages||[];
privateMessages=new Map(Object.entries(d.privateMessages||{}));
bannedNames=new Set(d.bannedNames||[]);
console.log('📂 Загружено',messages.length,'сообщений');
}
}catch(e){console.error('Load error:',e)}
}
function saveData(){
try{
fs.writeFileSync(DATA_FILE,JSON.stringify({
messages:messages.slice(-500),
privateMessages:Object.fromEntries(privateMessages),
bannedNames:[...bannedNames]
}));
}catch(e){console.error('Save error:',e)}
}
loadData();
setInterval(saveData,30000);

// Генерация аватара (цвет по имени)
function getAvatarColor(name){
let hash=0;
for(let i=0;i<name.length;i++)hash=name.charCodeAt(i)+((hash<<5)-hash);
const colors=['#FF6B6B','#4ECDC4','#45B7D1','#96CEB4','#FFEAA7','#DDA0DD','#98D8C8','#F7DC6F','#BB8FCE','#85C1E9','#F1948A','#82E0AA','#F8C471','#AED6F1','#D7BDE2'];
return colors[Math.abs(hash)%colors.length];
}

function isValidUsername(name){
return /^[a-zA-Z0-9_]{3,20}$/.test(name);
}

wss.on('connection',(ws)=>{
ws.id=Date.now()+Math.random();
ws.username=null;
ws.typingTimeout=null;
console.log('[+] Подключение',ws.id);

ws.on('message',(raw)=>{
try{
const msg=JSON.parse(raw);

if(msg.type==='check_username'){
const name=msg.username;
if(!isValidUsername(name)){
ws.send(JSON.stringify({type:'username_error',msg:'Ник должен быть 3-20 символов (a-z, 0-9, _)'}));
}else if(users.has(name)){
ws.send(JSON.stringify({type:'username_error',msg:'Этот ник уже занят'}));
}else if(bannedNames.has(name)){
ws.send(JSON.stringify({type:'username_error',msg:'Этот ник заблокирован'}));
}else{
ws.send(JSON.stringify({type:'username_ok'}));
}
return;
}

if(msg.type==='login'){
const name=msg.username;
if(!isValidUsername(name)){
ws.send(JSON.stringify({type:'error',msg:'Невалидный ник'}));
return;
}
if(users.has(name)){
ws.send(JSON.stringify({type:'error',msg:'Ник уже используется'}));
return;
}
ws.username=name;
users.set(name,{ws,joinedAt:Date.now(),avatar:getAvatarColor(name)});
ws.send(JSON.stringify({
type:'welcome',
username:name,
avatar:getAvatarColor(name),
users:[...users.keys()],
messages:messages.slice(-100)
}));
broadcast({type:'user_joined',username:name,avatar:getAvatarColor(name),users:[...users.keys()]});
console.log('[LOGIN]',name);
return;
}

if(!ws.username)return;

if(msg.type==='message'){
const text=(msg.text||'').trim().slice(0,1000);
if(!text)return;
const m={
id:Date.now(),
username:ws.username,
avatar:getAvatarColor(ws.username),
text:text,
time:Date.now(),
type:'public'
};
messages.push(m);
if(messages.length>500)messages.shift();
broadcast({type:'message',message:m});
return;
}

if(msg.type==='private_message'){
const to=msg.to;
const text=(msg.text||'').trim().slice(0,1000);
if(!to||!text)return;
if(!users.has(to)){
ws.send(JSON.stringify({type:'error',msg:'Пользователь не в сети'}));
return;
}
const key=[ws.username,to].sort().join('_');
const m={
id:Date.now(),
from:ws.username,
to:to,
avatar:getAvatarColor(ws.username),
text:text,
time:Date.now()
};
if(!privateMessages.has(key))privateMessages.set(key,[]);
privateMessages.get(key).push(m);
if(privateMessages.get(key).length>200)privateMessages.get(key).shift();
const target=users.get(to);
if(target&&target.ws.readyState===WebSocket.OPEN){
target.ws.send(JSON.stringify({type:'private_message',message:m}));
}
ws.send(JSON.stringify({type:'private_message',message:m}));
return;
}

if(msg.type==='get_private_history'){
const with=msg.with;
if(!with)return;
const key=[ws.username,with].sort().join('_');
const hist=privateMessages.get(key)||[];
ws.send(JSON.stringify({type:'private_history',with:with,messages:hist}));
return;
}

if(msg.type==='delete_message'){
const id=msg.id;
const idx=messages.findIndex(m=>m.id===id&&m.username===ws.username);
if(idx>=0&&(Date.now()-messages[idx].time)<300000){
messages.splice(idx,1);
broadcast({type:'message_deleted',id:id});
}
return;
}

if(msg.type==='typing'){
broadcast({type:'typing',username:ws.username},ws.username);
clearTimeout(ws.typingTimeout);
ws.typingTimeout=setTimeout(()=>{
broadcast({type:'stop_typing',username:ws.username});
},2000);
return;
}

if(msg.type==='image'){
if(!msg.data||msg.data.length>300000){
ws.send(JSON.stringify({type:'error',msg:'Картинка слишком большая'}));
return;
}
const m={
id:Date.now(),
username:ws.username,
avatar:getAvatarColor(ws.username),
image:msg.data,
time:Date.now(),
type:'public'
};
messages.push(m);
if(messages.length>500)messages.shift();
broadcast({type:'message',message:m});
return;
}

}catch(e){console.error('[ERR]',e)}
});

ws.on('close',()=>{
if(ws.username){
users.delete(ws.username);
broadcast({type:'user_left',username:ws.username,users:[...users.keys()]});
console.log('[-]',ws.username,'вышел');
}
});

ws.on('error',(e)=>console.error('[WS-ERR]',e.message));
});

function broadcast(msg,exclude=null){
const d=JSON.stringify(msg);
users.forEach((u,name)=>{
if(name!==exclude&&u.ws.readyState===WebSocket.OPEN){
try{u.ws.send(d)}catch(e){}
}
});
}

app.get('/health',(req,res)=>res.send('ok'));

server.listen(PORT,'0.0.0.0',()=>{
console.log('🚀 Messenger on port',PORT);
console.log('📁 Public:',path.join(__dirname,'public'));
});
