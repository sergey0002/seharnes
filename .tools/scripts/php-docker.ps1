param([Parameter(ValueFromRemainingArguments = $true)] [string[]] $Args)
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
while ($repo -and -not (Test-Path (Join-Path $repo ".cursor")) -and -not (Test-Path (Join-Path $repo ".git"))) {
    $repo = Split-Path $repo -Parent
}
if (-not $repo) { throw "php-docker: project root not found" }
$linuxRoot = "/var/www/html"
$container = if ($env:DOCKER_PHP_CONTAINER) { $env:DOCKER_PHP_CONTAINER } else { "copytrust-dev-php-apache-1" }
$translated = foreach ($a in $Args) {
    $n = $a -replace '\\', '/'
    $prefix = $repo -replace '\\', '/'
    if ($n.StartsWith($prefix)) {
        $n.Substring($prefix.Length)
        if ($n.StartsWith('/')) { "/var/www/html$n" } else { "/var/www/html/$n" }
    } else { $n }
}
& docker exec -i $container php @translated
