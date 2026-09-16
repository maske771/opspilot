FROM node:22-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY app ./app

ENV NODE_ENV=production
EXPOSE 3000

RUN npm run build

CMD ["npm", "run", "start"]
