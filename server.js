const WebSocket = require('ws');
const http = require('http');
const path = require('path');
const fs = require('fs');

const PORT = process.env.PORT || 3000;

const server = http.createServer((req, res) => {
    if (req.url === '/' || req.url === '/index.html') {
        const fp = path.join(__dirname, 'public', 'index.html');
        fs.readFile(fp, (err, data) => {
            if (err) { res.writeHead(500); res.end('error'); return; }
            res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
            res.end(data);
        });
    } else if (req.url === '/health') {
        res.writeHead(200);
        res.end('ok - drone server alive');
    } else {
        res.writeHead(404);
        res.end('not found');
    }
});

const wss = new WebSocket.Server({ server });

const servers = {
    1: { players: new Map(), max: 10 },
    2: { players: new Map(), max: 10 }
};
let nextId = 1;

function broadcast(sid, msg, exId) {
    if (!sid || !servers[sid]) return;
    const d = JSON.stringify(msg);
    servers[sid].players.forEach((p, pid) => {
        if (pid !== exId && p.readyState === WebSocket.OPEN) {
            try { p.send(d); } catch (e) {}
        }
    });
}

function sendStatusToAll() {
    const s1 = servers[1].players.size;
    const s2 = servers[2].players.size;
    const msg = JSON.stringify({ type: 'status', s1, s2 });
    wss.clients.forEach(ws => {
        if (ws.readyState === WebSocket.OPEN) {
            try { ws.send(msg); } catch (e) {}
        }
    });
}

wss.on('connection', (ws) => {
    ws.id = nextId++;
    ws.serverId = null;
    ws.pos = { x: 0, y: 0, z: 0, ry: 0 };
    ws.isDrone = false;
    ws.dronePos = null;
    ws.isAlive = true;
    ws.lastMove = 0;

    console.log(`[+] Player ${ws.id} connected`);

    ws.on('pong', () => { ws.isAlive = true; });

    ws.on('message', (raw) => {
        try {
            const msg = JSON.parse(raw);

            const now = Date.now();
            if ((msg.type === 'move' || msg.type === 'drone_move') && now - ws.lastMove < 60) return;
            ws.lastMove = now;

            if (msg.type === 'join') {
                const sid = parseInt(msg.serverId);
                if (!servers[sid]) return;
                if (servers[sid].players.size >= servers[sid].max) {
                    ws.send(JSON.stringify({ type: 'error', msg: 'Server is full' }));
                    return;
                }
                ws.serverId = sid;
                const off = (Math.random() - 0.5) * 6;
                ws.pos = { x: off, y: 0, z: off, ry: 0 };

                servers[sid].players.set(ws.id, ws);

                broadcast(sid, {
                    type: 'player_joined',
                    id: ws.id,
                    x: ws.pos.x, y: ws.pos.y, z: ws.pos.z, ry: ws.pos.ry,
                    isDrone: false
                }, ws.id);

                const ex = [];
                servers[sid].players.forEach((p, pid) => {
                    if (pid !== ws.id) {
                        ex.push({
                            id: pid,
                            x: p.pos.x, y: p.pos.y, z: p.pos.z, ry: p.pos.ry,
                            isDrone: p.isDrone,
                            dronePos: p.dronePos
                        });
                    }
                });
                ws.send(JSON.stringify({
                    type: 'welcome',
                    id: ws.id,
                    serverId: sid,
                    count: servers[sid].players.size,
                    players: ex
                }));

                console.log(`[JOIN] P${ws.id} -> Server #${sid} (${servers[sid].players.size}/10)`);
                sendStatusToAll();
            }
            else if (!ws.serverId) return;

            else if (msg.type === 'move') {
                ws.pos = { x: msg.x, y: msg.y, z: msg.z, ry: msg.ry };
                broadcast(ws.serverId, {
                    type: 'player_move', id: ws.id,
                    x: msg.x, y: msg.y, z: msg.z, ry: msg.ry
                }, ws.id);
            }
            else if (msg.type === 'drone_enter') {
                ws.isDrone = true;
                ws.dronePos = { x: msg.x, y: msg.y, z: msg.z, ry: msg.ry };
                broadcast(ws.serverId, {
                    type: 'player_drone_enter', id: ws.id,
                    x: msg.x, y: msg.y, z: msg.z, ry: msg.ry
                }, ws.id);
            }
            else if (msg.type === 'drone_move') {
                ws.dronePos = { x: msg.x, y: msg.y, z: msg.z, ry: msg.ry };
                broadcast(ws.serverId, {
                    type: 'player_drone_move', id: ws.id,
                    x: msg.x, y: msg.y, z: msg.z, ry: msg.ry
                }, ws.id);
            }
            else if (msg.type === 'drone_exit') {
                ws.isDrone = false;
                ws.dronePos = null;
                broadcast(ws.serverId, {
                    type: 'player_drone_exit', id: ws.id,
                    x: ws.pos.x, y: ws.pos.y, z: ws.pos.z, ry: ws.pos.ry
                }, ws.id);
            }
            else if (msg.type === 'drone_explode') {
                broadcast(ws.serverId, {
                    type: 'player_drone_explode', id: ws.id,
                    x: msg.x, y: msg.y, z: msg.z
                }, ws.id);
            }
            else if (msg.type === 'chat') {
                broadcast(ws.serverId, { type: 'chat', id: ws.id, text: String(msg.text).slice(0, 100) });
            }
        } catch (e) {
            console.error('[ERR]', e.message);
        }
    });

    ws.on('close', () => {
        if (ws.serverId && servers[ws.serverId].players.has(ws.id)) {
            const sid = ws.serverId;
            servers[sid].players.delete(ws.id);
            broadcast(sid, { type: 'player_left', id: ws.id });
            console.log(`[-] P${ws.id} left Server #${sid}`);
            sendStatusToAll();
        }
    });

    ws.on('error', (e) => console.error('[WS-ERR]', e.message));
});

setInterval(() => {
    wss.clients.forEach((ws) => {
        if (ws.isAlive === false) return ws.terminate();
        ws.isAlive = false;
        try { ws.ping(); } catch (e) {}
    });
    sendStatusToAll();
}, 15000);

server.listen(PORT, '0.0.0.0', () => {
    console.log(`🚀 Drone server on port ${PORT} (Render-ready)`);
});
