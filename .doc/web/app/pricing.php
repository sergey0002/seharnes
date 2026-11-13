<?php
// Provider-specific model prices. Unknown provider or model means no cost, no error.
// PHP 7.1 compatible.

function prices_config() {
    static $cfg = null;
    if ($cfg !== null) {
        return $cfg;
    }
    $defaults = array(
        'schema' => 2,
        'currency' => 'RUB',
        'unit' => 'rub_per_1m_tokens',
        'token_price' => 0.0,
        'providers' => array(),
        'aliases' => array(),
        'models' => array(),
    );
    $raw = @file_get_contents(__DIR__ . '/../config/prices.json');
    $data = $raw === false ? null : json_decode($raw, true);
    $cfg = is_array($data) ? array_merge($defaults, $data) : $defaults;
    $local_path = __DIR__ . '/../config/prices.local.json';
    if (is_file($local_path)) {
        $raw = @file_get_contents($local_path);
        $local = $raw === false ? null : json_decode($raw, true);
        if (is_array($local)) {
            $cfg = prices_merge($cfg, $local);
        }
    }
    return $cfg;
}

function prices_merge($base, $local) {
    foreach (array('aliases', 'models') as $key) {
        if (isset($local[$key]) && is_array($local[$key])) {
            $base[$key] = array_merge(
                isset($base[$key]) && is_array($base[$key]) ? $base[$key] : array(),
                $local[$key]
            );
        }
    }
    if (isset($local['providers']) && is_array($local['providers'])) {
        foreach ($local['providers'] as $name => $provider) {
            if (!is_array($provider)) {
                continue;
            }
            $current = isset($base['providers'][$name]) && is_array($base['providers'][$name])
                ? $base['providers'][$name] : array();
            if (isset($provider['models']) && is_array($provider['models'])) {
                $provider['models'] = array_merge(
                    isset($current['models']) && is_array($current['models']) ? $current['models'] : array(),
                    $provider['models']
                );
            }
            $base['providers'][$name] = array_merge($current, $provider);
        }
    }
    foreach (array('schema', 'currency', 'unit', 'token_price') as $key) {
        if (array_key_exists($key, $local)) {
            $base[$key] = $local[$key];
        }
    }
    return $base;
}

function price_model($model, $provider = '') {
    $cfg = prices_config();
    $model = (string) $model;
    $aliases = isset($cfg['aliases']) && is_array($cfg['aliases']) ? $cfg['aliases'] : array();
    if (isset($aliases[$model])) {
        $model = (string) $aliases[$model];
    }
    $provider = (string) $provider;
    if ($provider !== '' && isset($cfg['providers'][$provider]['models'][$model])
        && is_array($cfg['providers'][$provider]['models'][$model])) {
        return array(
            'model' => $cfg['providers'][$provider]['models'][$model],
            'provider' => $cfg['providers'][$provider],
            'provider_id' => $provider,
        );
    }
    if (isset($cfg['models'][$model]) && is_array($cfg['models'][$model])) {
        return array('model' => $cfg['models'][$model], 'provider' => null, 'provider_id' => '');
    }
    return null;
}

function price_value($row, $key, $provider) {
    if (isset($row[$key]) && is_numeric($row[$key])) {
        return (float) $row[$key];
    }
    if (isset($row['coefficient']) && is_array($provider) && isset($provider['token_price'])) {
        return (float) $row['coefficient'] * (float) $provider['token_price'] * 1000000.0;
    }
    if ($key === 'cache_read' || $key === 'cache_write') {
        return 0.0;
    }
    return null;
}

function price_cost($model, $input, $output, $cache_read, $cache_write, $provider = '') {
    $hit = price_model($model, $provider);
    if ($hit === null) {
        return 0.0;
    }
    $row = $hit['model'];
    $provider_cfg = $hit['provider'];
    $input_price = price_value($row, 'input', $provider_cfg);
    $output_price = price_value($row, 'output', $provider_cfg);
    $cache_read_price = price_value($row, 'cache_read', $provider_cfg);
    $cache_write_price = price_value($row, 'cache_write', $provider_cfg);
    $cost = 0.0;
    if ($input_price !== null) {
        $cost += ((int) $input / 1000000.0) * $input_price;
    }
    if ($output_price !== null) {
        $cost += ((int) $output / 1000000.0) * $output_price;
    }
    if ($cache_read_price !== null) {
        $cost += ((int) $cache_read / 1000000.0) * $cache_read_price;
    }
    if ($cache_write_price !== null) {
        $cost += ((int) $cache_write / 1000000.0) * $cache_write_price;
    }
    return $cost;
}

function price_currency($provider = '') {
    $cfg = prices_config();
    $provider = (string) $provider;
    if ($provider !== '' && isset($cfg['providers'][$provider]['currency'])) {
        return (string) $cfg['providers'][$provider]['currency'];
    }
    return isset($cfg['currency']) ? (string) $cfg['currency'] : 'RUB';
}

function provider_label($provider) {
    $cfg = prices_config();
    $provider = (string) $provider;
    if (isset($cfg['providers'][$provider]['name'])) {
        return (string) $cfg['providers'][$provider]['name'];
    }
    return $provider === '' ? 'неизвестно' : $provider;
}
