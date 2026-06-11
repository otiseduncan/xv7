FROM nginx:alpine

# Nginx official image renders templates in /etc/nginx/templates via envsubst.
COPY docker/frontend/default.conf.template /etc/nginx/templates/default.conf.template

# Serve static frontend assets.
COPY public/ /usr/share/nginx/html/

EXPOSE 80
