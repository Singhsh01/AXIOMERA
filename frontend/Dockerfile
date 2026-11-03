# Build and run outside /app: Next.js standalone output breaks when the build directory
# is named like a route segment of the project (this app has an /app route).
FROM node:22-alpine AS deps
WORKDIR /srv/web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /srv/web
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /srv/web/node_modules ./node_modules
COPY . .
ARG ORKESTR_API_URL=http://api:8000
ENV ORKESTR_API_URL=$ORKESTR_API_URL
RUN npm run build

FROM node:22-alpine
WORKDIR /srv/web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
# --chown: source files may arrive with owner-only permissions (e.g. 0600/0700); the server runs as `node`.
COPY --from=build --chown=node:node /srv/web/.next/standalone ./
COPY --from=build --chown=node:node /srv/web/.next/static ./.next/static
COPY --from=build --chown=node:node /srv/web/public ./public
RUN chmod -R u+rwX,go+rX /srv/web
USER node
EXPOSE 3000
CMD ["node", "server.js"]
