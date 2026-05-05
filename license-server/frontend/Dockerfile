FROM node:20-alpine AS build

WORKDIR /app
COPY package.json yarn.lock* ./
RUN yarn install --frozen-lockfile || yarn install

ARG REACT_APP_BACKEND_URL=https://license.stream-vault.eu
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

COPY . .
RUN yarn build

FROM nginx:1.27-alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY <<EOF /etc/nginx/conf.d/default.conf
server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;
  location / {
    try_files \$uri \$uri/ /index.html;
  }
  location ~* \.(js|css|png|jpg|jpeg|gif|svg|woff2?)$ {
    expires 30d;
    add_header Cache-Control "public, max-age=2592000";
  }
}
EOF
EXPOSE 80
