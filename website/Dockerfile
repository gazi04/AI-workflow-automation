FROM oven/bun:1.1-alpine AS base

WORKDIR /app

COPY package.json bun.lockb* ./

RUN bun install --frozen-lockfile

FROM base AS development

COPY . .

RUN bun run prepare

ENV NODE_ENV=development
EXPOSE 5173

CMD ["bun", "run", "dev", "--", "--host", "0.0.0.0"]
