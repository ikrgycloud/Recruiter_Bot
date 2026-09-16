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
# NGINX STAGE
# ==========================================

FROM nginx:alpine

# Remove default nginx configuration
RUN rm -f /etc/nginx/conf.d/default.conf

# Copy our SPA nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy React production build
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
