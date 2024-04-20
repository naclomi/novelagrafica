FROM httpd:2.4

# Copy .htaccess into DocumentRoot
# COPY ./.htaccess /var/www/html/

RUN sed -i '/LoadModule rewrite_module/s/^#//g' /usr/local/apache2/conf/httpd.conf

RUN { \
  echo 'IncludeOptional conf.d/*.conf'; \
} >> /usr/local/apache2/conf/httpd.conf

RUN { \
  echo '<Directory "/usr/local/apache2/htdocs">\nAllowOverride All\n</Directory>'; \
} >> /usr/local/apache2/conf/httpd.conf 

RUN mkdir /usr/local/apache2/conf.d


