# Vite dev server for `docker compose up` (see ../docker-compose.yml). Source is bind-mounted at runtime.
FROM node:22-slim
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--port", "5173", "--strictPort"]
