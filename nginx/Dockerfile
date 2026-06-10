FROM nginx:1.27-alpine

RUN apk add --no-cache inotify-tools certbot certbot-nginx

RUN mkdir -p /var/www/certbot /etc/letsencrypt

COPY default.conf /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
