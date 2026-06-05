FROM node:20.19-alpine AS build
WORKDIR /app

# Copy package manifests first to utilize caching
COPY package.json package-lock.json ./

# Run npm ci with cache mounting to preserve package downloads
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

# Copy code and configs afterwards
COPY tsconfig.json tsconfig.node.json vite.config.ts index.html ./
COPY src ./src
COPY public ./public

# Build the application
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
