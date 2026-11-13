<?php

final class EnvConfig
{
    /** @var array<string, string> */
    private $values = array();

    public function __construct($configPath)
    {
        if (!is_file($configPath)) {
            throw new RuntimeException(
                'Config not found: ' . $configPath . '. Copy config.example.env to config.env'
            );
        }

        $lines = file($configPath, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        if ($lines === false) {
            throw new RuntimeException('Cannot read config: ' . $configPath);
        }

        foreach ($lines as $line) {
            $line = trim($line);
            if ($line === '' || $line[0] === '#') {
                continue;
            }

            $pos = strpos($line, '=');
            if ($pos === false) {
                continue;
            }

            $key = trim(substr($line, 0, $pos));
            $value = trim(substr($line, $pos + 1));
            if ($key !== '') {
                $this->values[$key] = $value;
            }
        }
    }

    public function get($key, $default = null)
    {
        if (isset($this->values[$key]) && $this->values[$key] !== '') {
            return $this->values[$key];
        }

        $env = getenv($key);
        if ($env !== false && $env !== '') {
            return $env;
        }

        return $default;
    }

    public function requireValue($key)
    {
        $value = $this->get($key);
        if ($value === null || $value === '') {
            throw new RuntimeException('Missing required config value: ' . $key);
        }

        return $value;
    }
}
