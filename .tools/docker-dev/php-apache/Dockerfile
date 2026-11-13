FROM php:7.4-apache

RUN set -eux; \
  echo 'deb http://archive.debian.org/debian bullseye main' > /etc/apt/sources.list; \
  echo 'deb http://archive.debian.org/debian-security bullseye-security main' >> /etc/apt/sources.list; \
  echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid-until; \
  apt-get update \
  && apt-get install -y --no-install-recommends \
    curl \
    libicu-dev \
    libmemcached-dev \
    libz-dev \
    libpq-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    libssl-dev \
    libxml2-dev \
    libbz2-dev \
    libjpeg62-turbo-dev \
    git \
    subversion \
    libzip-dev \
    libonig-dev \
  && rm -rf /var/lib/apt/lists/*

RUN docker-php-ext-configure gd --with-jpeg --with-freetype \
  && docker-php-ext-install -j$(nproc) \
        bcmath \
        intl \
        mbstring \
        mysqli \
        pcntl \
        gettext \
        pdo_mysql \
        pdo_pgsql \
        soap \
        sockets \
        zip \
        gd \
        opcache \
  && docker-php-ext-enable opcache

RUN rm -f /etc/localtime \
    && ln -s /usr/share/zoneinfo/Europe/Moscow /etc/localtime

COPY ./php/conf.d /usr/local/etc/php/conf.d
COPY ./apache/zz-copytrust.conf /etc/apache2/conf-enabled/zz-copytrust.conf

RUN a2enmod rewrite headers
