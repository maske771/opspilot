FROM node:22-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install

COPY app ./app
COPY public ./public
COPY next.config.mjs ./

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NODE_ENV=production
ENV NODE_OPTIONS=--max-old-space-size=512

RUN npm run build

FROM node:22-alpine

WORKDIR /app
ENV NODE_ENV=production
EXPOSE 3000

COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public

CMD ["node", "server.js"]
