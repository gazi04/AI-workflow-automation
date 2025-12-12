# -----------------------------------------------------------------------------
# Development Environment Dockerfile
# -----------------------------------------------------------------------------

# Use a standard Node.js image with a stable LTS version for the base
FROM node:lts-slim

# Set the working directory inside the container
WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock/pnpm-lock.yaml)
# We copy this first to leverage Docker's build cache: if dependencies haven't 
# changed, this step (and the install step) won't run again, speeding up rebuilds.
# NOTE: Assuming your frontend project uses 'package.json' for dependency management.
COPY package*.json ./

# Install dependencies
# Using 'npm ci' for clean installs when a lock file is present
RUN npm install

# Expose the port Vite is configured to run on (as specified in docker-compose.yml)
EXPOSE 5173

# Define the command to run the development server.
# Using --host 0.0.0.0 is crucial so the server is accessible from the host network.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
# NOTE: This assumes your package.json has a 'dev' script defined for running Vite.
