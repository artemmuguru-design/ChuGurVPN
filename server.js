const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const path = require('path');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

const PORT = process.env.PORT || 3000;

app.use(express.static(path.join(__dirname, 'public')));

let messages = [];
let users = new Map();

wss.on('connection', (ws) => {
    ws.id = Date.now();
    ws.username = null;

    ws.on('message', (raw) => {
        try {
            const msg = JSON.parse(raw);

            if (msg.type === 'login') {
                ws.username = msg.username;
                users.set(ws.id, ws);
                
                // Отправляем историю сообщений
                ws.send(JSON.stringify({
                    type: 'history',
                    messages: messages.slice(-50)
                }));

                // Уведомляем всех о новом пользователе
                broadcast({
                    type: 'user_joined',
                    username: ws.username,
                    users: Array.from(users.values()).map(u => u.username)
                });

                console.log(`[+] ${ws.username} joined`);
            }
            else if (msg.type === 'message' && ws.username) {
                const message = {
                    id: Date.now(),
                    username: ws.username,
                    text: msg.text,
                    time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
                };
                
                messages.push(message);
                if (messages.length > 100) messages.shift();

                broadcast({
                    type: 'message',
                    message: message
                });
            }
        } catch (e) {
            console.error('[ERR]', e);
        }
    });

    ws.on('close', () => {
        if (ws.username) {
            users.delete(ws.id);
            broadcast({
                type: 'user_left',
                username: ws.username,
                users: Array.from(users.values()).map(u => u.username)
            });
            console.log(`[-] ${ws.username} left`);
        }
    });

    ws.on('error', (e) => console.error('[WS-ERR]', e.message));
});

function broadcast(msg, excludeId = null) {
    const data = JSON.stringify(msg);
    users.forEach((ws, id) => {
        if (id !== excludeId && ws.readyState === WebSocket.OPEN) {
            try { ws.send(data); } catch (e) {}
        }
    });
}

server.listen(PORT, '0.0.0.0', () => {
    console.log(`🚀 Messenger server on port ${PORT}`);
});
