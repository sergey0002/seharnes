# Isolated Codeception runtime. The application keeps using its own PHP 7.4 image.
FROM php:8.3-cli

RUN apt-get update \
    && apt-get install -y --no-install-recommends libcurl4-openssl-dev libonig-dev \
    && docker-php-ext-install curl mbstring pdo_mysql \
    && rm -rf /var/lib/apt/lists/* \
    && printf 'memory_limit=512M\nregister_argc_argv=1\n' > /usr/local/etc/php/conf.d/zz-qa.ini

WORKDIR /app
