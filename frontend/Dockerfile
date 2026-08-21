FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# VITE_API_BASE stays unset: the bundle issues same-origin requests and the
# nginx proxy below forwards them to the backend (no CORS needed).
RUN npm run build

FROM nginx:1.27-alpine

# The nginx image runs envsubst on /etc/nginx/templates/*.template into
# /etc/nginx/conf.d at container start, substituting only variables present
# in the environment — nginx's own $variables pass through untouched.
COPY nginx-templates/ /etc/nginx/templates/
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
