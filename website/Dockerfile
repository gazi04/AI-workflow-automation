FROM node:22-slim AS development

WORKDIR /app

# Copy dependency files
COPY package*.json ./

# Install all dependencies (including dev dependencies)
RUN npm ci

# Copy source code
COPY . .

# Development command with hot reload
CMD ["npm", "run", "dev"]
