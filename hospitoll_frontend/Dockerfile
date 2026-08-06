# Frontend Dockerfile - Multi-stage build
FROM node:20-alpine AS builder

WORKDIR /app
ENV BROWSERSLIST_IGNORE_OLD_DATA=1

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --no-audit --no-fund

# Copy source
COPY . .

# Build
RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Install serve to run static build
RUN npm install -g serve --no-fund --no-audit

# Copy built app from builder
COPY --from=builder /app/dist ./dist

# Create non-root user
RUN adduser -D appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/ || exit 1

# Expose port
EXPOSE 3000

# Run app
CMD ["serve", "-s", "dist", "-l", "3000"]
