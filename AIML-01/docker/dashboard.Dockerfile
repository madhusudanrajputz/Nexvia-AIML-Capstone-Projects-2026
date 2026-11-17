FROM node:22-alpine

WORKDIR /app

COPY dashboard/package.json ./
RUN npm install --no-audit --no-fund

COPY dashboard/ ./
RUN rm -rf node_modules/.cache .next
RUN npm run build

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

EXPOSE 3000

CMD ["npm", "run", "start", "--", "-H", "0.0.0.0"]
