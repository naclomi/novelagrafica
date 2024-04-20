#!/usr/bin/sh
docker run --rm -p 8080:80 -v $(pwd):/usr/local/apache2/htdocs/ httpd:mod-rewrite
