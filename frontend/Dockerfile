# Frontend production Dockerfile (multi-stage: build → static serve).
# Build context = ./frontend (whether via Railway Root Directory or compose).
# At build time, VITE_API_BASE_URL is baked into the JS bundle. Set it via
# Railway service variable to your backend's public URL.

FROM node:20-alpine AS build
WORKDIR /app

# Build-time env. Default = "" (relative to current origin, useful in
# compose-dev with the Vite proxy). In Railway, set VITE_API_BASE_URL to
# something like https://api.personalize.lakeb2b.com.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

# ── Runner: tiny static server on $PORT ──────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app
ENV PORT=5173 NODE_ENV=production
RUN npm install -g serve@14
COPY --from=build /app/dist ./dist
EXPOSE 5173

# `serve -s dist` rewrites all 404s to /index.html — required for client routing.
CMD ["sh", "-c", "serve -s dist -l ${PORT:-5173}"]
