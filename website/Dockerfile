# syntax=docker/dockerfile:1

# Node, not Bun: Vite 7 requires Node 20.19+/22.12+, and Bun 1.1 reports itself
# as Node 22.6.0, which trips Vite's version guard on every boot.
FROM node:24-alpine AS deps

WORKDIR /app

# Manifests only, so this layer stays cached until dependencies actually change.
COPY package.json package-lock.json ./

# npm ci installs exactly what package-lock.json pins — the lockfile that is
# actually committed to the repo. The previous `COPY package.json bun.lockb* ./`
# never matched the bun.lock on disk, so every build resolved dependencies afresh.
# The cache mount keeps downloaded tarballs across rebuilds.
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

# Record which lockfile this node_modules was built from. The entrypoint compares
# against it to detect a stale volume.
RUN cp package-lock.json node_modules/.lock-stamp

FROM node:24-alpine AS development

WORKDIR /app

ENV NODE_ENV=development
# Vite's dev server keeps the whole module graph in the V8 heap. Without a cap V8
# sizes the heap off host RAM and simply never collects, which is why this
# container sat near 1 GB.
ENV NODE_OPTIONS=--max-old-space-size=640

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Generate .svelte-kit/tsconfig.json and friends at build time rather than on
# first request.
RUN npx svelte-kit sync

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
