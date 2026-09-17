# ==========================================
# BUILD STAGE
# ==========================================

FROM node:22-alpine AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY . .

# Vite environment variable
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Build React application
RUN npm run build


# ==========================================
# STATIC SERVER STAGE
# ==========================================

FROM node:22-alpine

RUN npm install --global serve@14.2.4

WORKDIR /app
COPY --from=build /app/dist ./dist

EXPOSE 80

CMD ["serve", "-s", "dist", "-l", "80"]
