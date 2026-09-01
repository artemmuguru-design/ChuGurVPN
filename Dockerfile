FROM node:18-alpine
WORKDIR /app
COPY . .
RUN npm install ws
EXPOSE 3000
CMD ["node", "server.js"]
