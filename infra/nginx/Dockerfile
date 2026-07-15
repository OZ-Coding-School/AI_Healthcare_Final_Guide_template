FROM nginx:latest

# 기본 설정 제거
RUN rm /etc/nginx/conf.d/default.conf

# nginx 설정 복사
COPY default.conf /etc/nginx/conf.d/default.conf

CMD ["nginx", "-g", "daemon off;"]
