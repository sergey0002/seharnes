<?php
/**
 * PHP 8.5 migration scanner.
 *
 * Ищет в исходниках проекта конструкции, которые ломаются или объявлены
 * устаревшими при переходе с PHP 7.1 на PHP 8.5. Работает на PHP 7.1+
 * (запускается в контейнере copytrust-dev-php7.1-cli), поэтому сам скрипт
 * не использует синтаксис новее 7.1.
 *
 * Использование:
 *   php .tools/php85-scan/scan.php <project-root> [report.json]
 *
 * Категории severity:
 *   fatal       - на PHP 8.x будет Error/ParseError, без правки не работает
 *   behavior    - работает, но результат/поведение меняется (тихо ломается)
 *   deprecated  - работает, но пишет E_DEPRECATED (умрёт в PHP 9)
 *   review      - эвристика, нужна ручная проверка
 */

error_reporting(E_ALL);
ini_set('memory_limit', '2G');

$root = isset($argv[1]) ? rtrim($argv[1], '/\\') : getcwd();
$jsonOut = isset($argv[2]) ? $argv[2] : null;

$excludedTopDirs = array(
    'vendor', 'node_modules', 'templates_c', '.git', '.doc', 'docs',
    'backups', 'cache', 'uploads', 'img', 'images', 'imgp', 'pageImages',
    '.kilo', '.kilocode', '.cursor', '.codex', '.antigravity', '.gemini',
    '.agents', '.serena', '.playwright-mcp', 'sourcegraph-local', '.gitverse',
    '.dsh', '.vscode', 'deploy',
);

// Эти имена каталогов пропускаются на любой глубине (вложенные vendor у .tools/ и т.п.)
$excludedAnyDepth = array(
    'vendor', 'node_modules', 'templates_c', '.git',
);

$excludeFilePatterns = array(
    '#/\.kilo/#', '#/worktrees/#', '#/traces/#', '#/.tools/php85-scan/#',
);

/**
 * Удалённые функции/конструкции. Ключ - имя функции в нижнем регистре.
 * Формат: имя => array(severity, category, replacement hint)
 */
$functionMap = array(
    // --- удалено в PHP 7.0/7.1 (проект на 7.1 ещё работает, но при переносе
    //     на 8.5 это уже давно отсутствует; нужно убедиться, что не вызывается) ---
    'ereg' => array('fatal', 'removed-7.0', 'preg_match()'),
    'eregi' => array('fatal', 'removed-7.0', 'preg_match() с флагом i'),
    'ereg_replace' => array('fatal', 'removed-7.0', 'preg_replace()'),
    'eregi_replace' => array('fatal', 'removed-7.0', 'preg_replace() с флагом i'),
    'split' => array('fatal', 'removed-7.0', 'preg_split() или explode()'),
    'spliti' => array('fatal', 'removed-7.0', 'preg_split() с флагом i'),
    'sql_regcase' => array('fatal', 'removed-7.0', 'нет замены, переписать регулярку'),
    'call_user_method' => array('fatal', 'removed-7.0', 'call_user_func(array($obj, $method))'),
    'call_user_method_array' => array('fatal', 'removed-7.0', 'call_user_func_array(array($obj, $method))'),
    'set_magic_quotes_runtime' => array('fatal', 'removed-7.0', 'удалить вызов'),
    'magic_quotes_runtime' => array('fatal', 'removed-7.0', 'удалить вызов'),

    // --- удалено в PHP 8.0 ---
    'each' => array('fatal', 'removed-8.0', 'foreach'),
    'create_function' => array('fatal', 'removed-8.0', 'анонимная функция'),
    'money_format' => array('fatal', 'removed-8.0', 'NumberFormatter::formatCurrency()'),
    'ezmlm_hash' => array('fatal', 'removed-8.0', 'удалить вызов'),
    'hebrevc' => array('fatal', 'removed-8.0', 'hebrev() + nl2br()'),
    'convert_cyr_string' => array('fatal', 'removed-8.0', 'mb_convert_encoding()'),
    'get_magic_quotes_gpc' => array('fatal', 'removed-8.0', 'удалить вызов'),
    'get_magic_quotes_runtime' => array('fatal', 'removed-8.0', 'удалить вызов'),
    'fgetss' => array('fatal', 'removed-8.0', 'fgets() + strip_tags()'),
    'gzgetss' => array('fatal', 'removed-8.0', 'gzgets() + strip_tags()'),
    'image2wbmp' => array('fatal', 'removed-8.0', 'imagewbmp()'),
    'png2wbmp' => array('fatal', 'removed-8.0', 'imagewbmp()'),
    'jpeg2wbmp' => array('fatal', 'removed-8.0', 'imagewbmp()'),
    'ldap_sort' => array('fatal', 'removed-8.0', 'сортировать результат в PHP'),
    'read_exif_data' => array('fatal', 'removed-8.0', 'exif_read_data()'),
    'gmp_random' => array('fatal', 'removed-8.0', 'gmp_random_bits()/gmp_random_range()'),
    'is_real' => array('fatal', 'removed-8.0', 'is_float()'),
    '__autoload' => array('fatal', 'removed-8.0', 'spl_autoload_register()'),

    // --- удалено в PHP 7.2 ---
    'mcrypt_encrypt' => array('fatal', 'removed-7.2', 'openssl_encrypt()'),
    'mcrypt_decrypt' => array('fatal', 'removed-7.2', 'openssl_decrypt()'),
    'mcrypt_create_iv' => array('fatal', 'removed-7.2', 'random_bytes()'),
    'mcrypt_get_iv_size' => array('fatal', 'removed-7.2', 'openssl_cipher_iv_length()'),
    'mcrypt_get_key_size' => array('fatal', 'removed-7.2', 'openssl_cipher_key_length()'),

    // --- расширение mysql удалено в PHP 7.0 (префикс, см. ниже) ---
    'mysql_connect' => array('fatal', 'removed-7.0', 'mysqli/PDO'),
    'mysql_query' => array('fatal', 'removed-7.0', 'mysqli/PDO'),
    'mysql_fetch_array' => array('fatal', 'removed-7.0', 'mysqli/PDO'),
    'mysql_real_escape_string' => array('fatal', 'removed-7.0', 'mysqli_real_escape_string($link, $str)'),
    'mysql_error' => array('fatal', 'removed-7.0', 'mysqli_error()/PDO'),
    'mysql_select_db' => array('fatal', 'removed-7.0', 'mysqli_select_db()/PDO'),
    'mysql_close' => array('fatal', 'removed-7.0', 'mysqli_close()/PDO'),

    // --- устарело в PHP 8.1 ---
    'strftime' => array('deprecated', 'deprecated-8.1', 'date()/IntlDateFormatter'),
    'gmstrftime' => array('deprecated', 'deprecated-8.1', 'gmdate()/IntlDateFormatter'),
    'mhash' => array('deprecated', 'deprecated-8.1', 'hash()'),
    'mhash_count' => array('deprecated', 'deprecated-8.1', 'hash_algos()'),
    'mhash_get_block_size' => array('deprecated', 'deprecated-8.1', 'hash()'),
    'mhash_get_hash_name' => array('deprecated', 'deprecated-8.1', 'hash_algos()'),
    'mhash_keygen_s2k' => array('deprecated', 'deprecated-8.1', 'hash_pbkdf2()'),

    // --- устарело в PHP 8.2 ---
    'utf8_encode' => array('deprecated', 'deprecated-8.2', 'mb_convert_encoding($s, "UTF-8", "ISO-8859-1")'),
    'utf8_decode' => array('deprecated', 'deprecated-8.2', 'mb_convert_encoding($s, "ISO-8859-1", "UTF-8")'),

    // --- устарело в PHP 8.4 / 8.5 ---
    'mysqli_ping' => array('deprecated', 'deprecated-8.4', 'переподключение на уровне приложения'),
    'mysqli_kill' => array('deprecated', 'deprecated-8.4', 'KILL QUERY через SQL'),
    'ldap_connect' => array('deprecated', 'deprecated-8.5', 'ldap_connect() с одним аргументом URI'),

    // --- поведение/прочее ---
    'libxml_disable_entity_loader' => array('deprecated', 'deprecated-8.0', 'удалить вызов'),
    'get_class' => array('deprecated', 'deprecated-8.3', 'get_class($obj) или static::class'),
    'get_parent_class' => array('deprecated', 'deprecated-8.3', 'get_parent_class($obj)'),
);

$interfaceReturnTypes = array(
    'arrayaccess', 'iterator', 'iteratoraggregate', 'countable',
    'jsonserializable', 'serializable', 'stringable',
);

$findings = array();
$classProps = array();
$classExtends = array();
$stats = array('files' => 0, 'bytes' => 0, 'parse_errors' => 0);
$fileHashes = array();

function is_significant($token)
{
    if (!is_array($token)) {
        return true;
    }
    static $skip = null;
    if ($skip === null) {
        $skip = array(T_WHITESPACE, T_COMMENT, T_DOC_COMMENT, T_OPEN_TAG, T_CLOSE_TAG, T_INLINE_HTML);
    }
    return !in_array($token[0], $skip, true);
}

function token_text($token)
{
    return is_array($token) ? $token[1] : $token;
}

function token_id($token)
{
    return is_array($token) ? $token[0] : null;
}

/**
 * Разбор аргументов вызова: возвращает массив диапазонов [start,end] по
 * значимым индексам для каждого top-level аргумента. $openIdx - индекс '('.
 */
function call_arguments($tokens, $openIdx, $sig, $sigPos)
{
    $args = array();
    $depth = 0;
    $start = null;
    $count = count($tokens);
    for ($i = $openIdx; $i < $count; $i++) {
        $t = $tokens[$i];
        if (!is_significant($t)) {
            continue;
        }
        $text = token_text($t);
        if ($text === '(' || $text === '[' || $text === '{' || token_id($t) === T_CURLY_OPEN || token_id($t) === T_DOLLAR_OPEN_CURLY_BRACES) {
            $depth++;
            if ($depth === 1) {
                continue;
            }
        } elseif ($text === ')' || $text === ']' || $text === '}') {
            $depth--;
            if ($depth === 0) {
                if ($start !== null) {
                    $args[] = array($start, $i - 1);
                }
                break;
            }
        } elseif ($text === ',' && $depth === 1) {
            if ($start !== null) {
                $args[] = array($start, $i - 1);
            }
            $start = null;
            continue;
        }
        if ($depth === 1 && $start === null && $text !== '(') {
            $start = $i;
        }
    }
    return $args;
}

function arg_text($tokens, $range)
{
    $out = '';
    for ($i = $range[0]; $i <= $range[1]; $i++) {
        $out .= token_text($tokens[$i]);
    }
    return trim($out);
}

/**
 * Проверяет, что строковый литерал-регулярка содержит модификатор e.
 * $literal - текст вида "'/foo/e'" или '"/foo/e"'.
 */
function has_e_modifier($literal)
{
    $literal = trim($literal);
    $len = strlen($literal);
    if ($len < 3) {
        return false;
    }
    $quote = $literal[0];
    if ($quote !== '"' && $quote !== "'") {
        return false;
    }
    if ($literal[$len - 1] !== $quote) {
        return false;
    }
    $inner = substr($literal, 1, $len - 2);
    if ($inner === '') {
        return false;
    }
    $delimiter = $inner[0];
    $pos = strrpos($inner, $delimiter);
    if ($pos === false || $pos === 0) {
        return false;
    }
    $modifiers = substr($inner, $pos + 1);
    return strpos($modifiers, 'e') !== false;
}

function add_finding(&$findings, $file, $line, $severity, $category, $message, $snippet)
{
    $snippet = preg_replace('/\s+/', ' ', trim($snippet));
    if (strlen($snippet) > 180) {
        $snippet = substr($snippet, 0, 177) . '...';
    }
    $findings[] = array(
        'file' => $file,
        'line' => $line,
        'severity' => $severity,
        'category' => $category,
        'message' => $message,
        'snippet' => $snippet,
    );
}

$iterator = new RecursiveIteratorIterator(
    new RecursiveCallbackFilterIterator(
        new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS),
        function ($current, $key, $iterator) use ($root, $excludedTopDirs, $excludedAnyDepth, $excludeFilePatterns) {
            $path = $current->getPathname();
            $rel = ltrim(substr($path, strlen($root)), '/');
            $parts = explode('/', $rel);
            $top = $parts[0];
            foreach ($parts as $part) {
                if (in_array($part, $excludedAnyDepth, true)) {
                    return false;
                }
            }
            if ($current->isDir()) {
                if (in_array($top, $excludedTopDirs, true)) {
                    return false;
                }
                foreach ($excludeFilePatterns as $pattern) {
                    if (preg_match($pattern, '/' . $rel . '/')) {
                        return false;
                    }
                }
                return true;
            }
            if (substr($current->getFilename(), -4) !== '.php') {
                return false;
            }
            foreach ($excludeFilePatterns as $pattern) {
                if (preg_match($pattern, '/' . $rel . '/')) {
                    return false;
                }
            }
            return true;
        }
    )
);

foreach ($iterator as $fileInfo) {
    $path = $fileInfo->getPathname();
    $rel = ltrim(substr($path, strlen($root)), '/');
    $src = file_get_contents($path);
    if ($src === false) {
        continue;
    }
    $stats['files']++;
    $stats['bytes'] += strlen($src);
    $fileHashes[$rel] = sha1($src);

    try {
        $tokens = token_get_all($src);
    } catch (Throwable $e) {
        $stats['parse_errors']++;
        add_finding($findings, $rel, 0, 'fatal', 'parse-error', 'token_get_all: ' . $e->getMessage(), '');
        continue;
    }

    // Таблица строк и значимых индексов.
    $lines = array();
    $sig = array();
    $sigPos = array();
    $line = 1;
    $count = count($tokens);
    for ($i = 0; $i < $count; $i++) {
        $t = $tokens[$i];
        $lines[$i] = $line;
        if (is_significant($t)) {
            $sigPos[$i] = count($sig);
            $sig[] = $i;
        }
        $line += substr_count(token_text($t), "\n");
    }

    $sigCount = count($sig);
    $nextSig = function ($idx) use ($sig, $sigPos, $sigCount) {
        if (!isset($sigPos[$idx])) {
            return null;
        }
        $p = $sigPos[$idx] + 1;
        return $p < $sigCount ? $sig[$p] : null;
    };
    $prevSig = function ($idx) use ($sig, $sigPos) {
        if (!isset($sigPos[$idx])) {
            return null;
        }
        $p = $sigPos[$idx] - 1;
        return $p >= 0 ? $sig[$p] : null;
    };

    $functionDepths = array(); // стек: индекс T_FUNCTION или null
    $inPropDecl = false;
    $classStack = array();     // стек классов: array(name, extends, implements, bodyStart, bodyEnd, props, assignments, hasMagicSet)
    $braceDepth = 0;
    $pendingClass = null;

    for ($i = 0; $i < $count; $i++) {
        $t = $tokens[$i];
        $text = token_text($t);
        $id = token_id($t);
        $ln = $lines[$i];

        // --- конструкции, не зависящие от значимости ---
        if ($id === T_DOLLAR_OPEN_CURLY_BRACES) {
            add_finding($findings, $rel, $ln, 'deprecated', 'deprecated-8.2',
                'Интерполяция "${var}" устарела в PHP 8.2; использовать "{$var}"',
                $text);
        }

        if ($id === T_DOUBLE_CAST && stripos($text, 'real') !== false) {
            add_finding($findings, $rel, $ln, 'fatal', 'removed-8.0',
                'Приведение (real) удалено в PHP 8.0; использовать (float)', $text);
        }
        if ($id === T_UNSET_CAST) {
            add_finding($findings, $rel, $ln, 'fatal', 'removed-8.0',
                'Приведение (unset) удалено в PHP 8.0', $text);
        }
        if ($id === T_INT_CAST && strtolower($text) === '(integer)') {
            add_finding($findings, $rel, $ln, 'deprecated', 'deprecated-8.5',
                'Неканонический cast (integer) устарел в PHP 8.5; использовать (int)', $text);
        }
        if ($id === T_BOOL_CAST && strtolower($text) === '(boolean)') {
            add_finding($findings, $rel, $ln, 'deprecated', 'deprecated-8.5',
                'Неканонический cast (boolean) устарел в PHP 8.5; использовать (bool)', $text);
        }
        if ($id === T_DOUBLE_CAST && strtolower($text) === '(double)') {
            add_finding($findings, $rel, $ln, 'deprecated', 'deprecated-8.5',
                'Неканонический cast (double) устарел в PHP 8.5; использовать (float)', $text);
        }
        if ($id === T_STRING_CAST && strtolower($text) === '(binary)') {
            add_finding($findings, $rel, $ln, 'deprecated', 'deprecated-8.5',
                'Неканонический cast (binary) устарел в PHP 8.5; использовать (string)', $text);
        }

        if ($id === T_NEW) {
            $prev = $prevSig($i);
            if ($prev !== null && $tokens[$prev] === '&') {
                add_finding($findings, $rel, $ln, 'fatal', 'removed-5.3',
                    'Присваивание результата new по ссылке удалено; убрать &', $text);
            }
        }

        if ($id === T_VARIABLE && $text === '$GLOBALS') {
            $next = $nextSig($i);
            if ($next !== null) {
                $after = $nextSig($next);
                // $GLOBALS['x'] = ... -> запись
                if ($tokens[$next] === '[' && $after !== null) {
                    $depth = 0;
                    for ($j = $next; $j < $count; $j++) {
                        $jt = $tokens[$j];
                        if (!is_significant($jt)) {
                            continue;
                        }
                        $jtext = token_text($jt);
                        if ($jtext === '[') {
                            $depth++;
                        } elseif ($jtext === ']') {
                            $depth--;
                            if ($depth === 0) {
                                $k = $nextSig($j);
                                if ($k !== null && $tokens[$k] === '=') {
                                    add_finding($findings, $rel, $ln, 'review', 'globals-write',
                                        'Запись в $GLOBALS; в PHP 8.1+ ограничения на запись, проверить', $text);
                                }
                                break;
                            }
                        }
                    }
                }
            }
        }

        // --- работа со значимыми токенами ---
        if (!isset($sigPos[$i])) {
            continue;
        }

        if ($text === '{' || $id === T_CURLY_OPEN || $id === T_DOLLAR_OPEN_CURLY_BRACES) {
            $braceDepth++;
        } elseif ($text === '}') {
            $braceDepth--;
            if (!empty($classStack) && $braceDepth === $classStack[count($classStack) - 1]['bodyDepth'] - 1) {
                $class = array_pop($classStack);
                $inPropDecl = false;
                $lowerName = strtolower($class['name']);
                $classProps[$lowerName] = array_keys($class['props']);
                $classExtends[$lowerName] = $class['extends'];
                if (!$class['hasMagicSet']) {
                    $undeclared = array_diff(array_keys($class['assignments']), array_keys($class['props']));
                    if (count($undeclared) > 0) {
                        $list = implode(', ', array_slice(array_values($undeclared), 0, 8));
                        $finding = array(
                            'file' => $rel,
                            'line' => $class['line'],
                            'severity' => 'deprecated',
                            'category' => 'dynamic-properties',
                            'message' => 'Класс ' . $class['name'] . ': свойства без объявления (' . $list . '); в PHP 8.2+ deprecated, объявить или #[AllowDynamicProperties]',
                            'snippet' => 'class ' . $class['name'],
                            'class' => $lowerName,
                            'display' => $class['name'],
                            'props' => array_values($undeclared),
                            'extends' => $class['extends'],
                        );
                        $findings[] = $finding;
                    }
                }
            }
        }

        // Класс/трейт/интерфейс
        if ($id === T_CLASS || $id === T_TRAIT || $id === T_INTERFACE) {
            $prev = $prevSig($i);
            $isAnonymous = ($prev !== null && token_id($tokens[$prev]) === T_NEW);
            $isClassConstant = ($prev !== null && token_id($tokens[$prev]) === T_DOUBLE_COLON);
            if (!$isAnonymous && !$isClassConstant) {
                $nameIdx = $nextSig($i);
                $name = ($nameIdx !== null && token_id($tokens[$nameIdx]) === T_STRING) ? $tokens[$nameIdx][1] : '?';
                $extends = null;
                $implements = array();
                $j = $nameIdx;
                $expectExtends = false;
                while ($j !== null && $j < $count) {
                    $jt = $tokens[$j];
                    $jtext = token_text($jt);
                    if ($jtext === '{') {
                        break;
                    }
                    if (token_id($jt) === T_EXTENDS) {
                        $expectExtends = true;
                    } elseif ($expectExtends && is_array($jt) && ($jt[0] === T_STRING || $jt[0] === T_NS_SEPARATOR)) {
                        if ($jt[0] === T_STRING) {
                            $extends = strtolower($jt[1]);
                        }
                    } elseif (token_id($jt) === T_IMPLEMENTS) {
                        $expectExtends = false;
                    } elseif (is_array($jt) && $jt[0] === T_STRING && $j !== $nameIdx) {
                        $implements[] = strtolower($jt[1]);
                    }
                    $j = $nextSig($j);
                }
                // Найти '{' и запомнить глубину
                $bodyIdx = $j;
                while ($bodyIdx !== null && token_text($tokens[$bodyIdx]) !== '{') {
                    $bodyIdx = $nextSig($bodyIdx);
                }
                if ($bodyIdx !== null) {
                    $inPropDecl = false;
                    $classStack[] = array(
                        'name' => $name,
                        'extends' => $extends,
                        'implements' => $implements,
                        'line' => $lines[$bodyIdx],
                        'bodyDepth' => $braceDepth + 1,
                        'props' => array(),
                        'assignments' => array(),
                        'hasMagicSet' => false,
                    );
                }
            }
        }

        if ($id === T_STRING && strtolower($text) === '__set') {
            $prev = $prevSig($i);
            if ($prev !== null && token_id($tokens[$prev]) === T_FUNCTION && !empty($classStack)) {
                $classStack[count($classStack) - 1]['hasMagicSet'] = true;
            }
        }

        // Объявленные свойства класса и присваивания $this->prop = ...
        if (!empty($classStack) && $braceDepth >= $classStack[count($classStack) - 1]['bodyDepth']) {
            $inBodyLevel = ($braceDepth === $classStack[count($classStack) - 1]['bodyDepth']);
            if ($inBodyLevel) {
                if (in_array($text, array('public', 'protected', 'private', 'var', 'readonly'), true)) {
                    $inPropDecl = true;
                } elseif ($id === T_FUNCTION || $text === ';' || $text === '{' || $text === '}') {
                    $inPropDecl = false;
                }
            }

            if ($id === T_VARIABLE) {
                if ($text === '$this') {
                    $op = $nextSig($i);
                    if ($op !== null && token_id($tokens[$op]) === T_OBJECT_OPERATOR) {
                        $nameIdx = $nextSig($op);
                        if ($nameIdx !== null && token_id($tokens[$nameIdx]) === T_STRING) {
                            $assign = $nextSig($nameIdx);
                            if ($assign !== null && token_text($tokens[$assign]) === '=') {
                                $classStack[count($classStack) - 1]['assignments'][$tokens[$nameIdx][1]] = true;
                            }
                        }
                    }
                } elseif ($inBodyLevel && $inPropDecl) {
                    $classStack[count($classStack) - 1]['props'][ltrim($text, '$')] = true;
                }
            }
        }

        // Вызовы функций
        if ($id === T_STRING) {
            $name = strtolower($text);
            $next = $nextSig($i);
            $prev = $prevSig($i);
            $isCall = ($next !== null && token_text($tokens[$next]) === '(');
            $prevIsDecl = false;
            if ($prev !== null) {
                $prevId = token_id($tokens[$prev]);
                $prevText = token_text($tokens[$prev]);
                if (in_array($prevId, array(T_FUNCTION, T_NEW, T_OBJECT_OPERATOR, T_DOUBLE_COLON, T_CONST, T_CLASS, T_INTERFACE, T_TRAIT), true)) {
                    $prevIsDecl = true;
                }
                if ($prevText === '&') {
                    $p2 = $prevSig($prev);
                    if ($p2 !== null && token_id($tokens[$p2]) === T_FUNCTION) {
                        $prevIsDecl = true;
                    }
                }
            }
            if ($isCall && !$prevIsDecl) {
                if (isset($functionMap[$name])) {
                    $info = $functionMap[$name];
                    $severity = $info[0];
                    // get_class()/get_parent_class() без аргументов - только тогда deprecated
                    if (($name === 'get_class' || $name === 'get_parent_class') && $info[1] === 'deprecated-8.3') {
                        $args = call_arguments($tokens, $next, $sig, $sigPos);
                        if (count($args) > 0) {
                            $severity = null;
                        }
                    }
                    // assert() строкой: только если первый аргумент - строка
                    if ($name === 'assert' && $severity !== null) {
                        $args = call_arguments($tokens, $next, $sig, $sigPos);
                        if (count($args) > 0) {
                            $first = $args[0];
                            $firstToken = $tokens[$first[0]];
                            if (token_id($firstToken) !== T_CONSTANT_ENCAPSED_STRING) {
                                $severity = null;
                            }
                        }
                    }
                    // define() case-insensitive: третий аргумент true
                    if ($name === 'define' && $severity !== null) {
                        $args = call_arguments($tokens, $next, $sig, $sigPos);
                        if (count($args) < 3) {
                            $severity = null;
                        } else {
                            $third = arg_text($tokens, $args[2]);
                            if (strtolower($third) !== 'true') {
                                $severity = null;
                            }
                        }
                    }
                    if ($severity !== null) {
                        add_finding($findings, $rel, $ln, $severity, $info[1],
                            $name . '(): ' . $info[2], $name . '(...)');
                    }
                }

                // implode/join с обратным порядком аргументов
                if ($name === 'implode' || $name === 'join') {
                    $args = call_arguments($tokens, $next, $sig, $sigPos);
                    if (count($args) >= 2) {
                        $first = arg_text($tokens, $args[0]);
                        $second = arg_text($tokens, $args[1]);
                        if (substr($first, 0, 1) === '$' && preg_match('/^(["\']).*\1$/', $second)) {
                            add_finding($findings, $rel, $ln, 'behavior', 'behavior-8.0',
                                $name . '($array, $glue): обратный порядок удалён в PHP 8.0 (TypeError)', $name . '(' . $first . ', ' . $second . ')');
                        }
                    }
                }

                // mb_strrpos с третьим аргументом-кодировкой (удалён в 8.0)
                if ($name === 'mb_strrpos') {
                    $args = call_arguments($tokens, $next, $sig, $sigPos);
                    if (count($args) >= 3) {
                        $third = arg_text($tokens, $args[2]);
                        if (preg_match('/^(["\'])[A-Za-z0-9\-_]+\1$/', $third)) {
                            add_finding($findings, $rel, $ln, 'fatal', 'removed-8.0',
                                'mb_strrpos(): аргумент-кодировка удалён в PHP 8.0; передавать encoding 4-м аргументом', 'mb_strrpos(...)');
                        }
                    }
                }

                // assert строкой
                // (обработано выше через functionMap)

                // parse_str с одним аргументом
                if ($name === 'parse_str') {
                    $args = call_arguments($tokens, $next, $sig, $sigPos);
                    if (count($args) < 2) {
                        add_finding($findings, $rel, $ln, 'behavior', 'behavior-8.0',
                            'parse_str() без второго аргумента: удалено, нужен массив результата', 'parse_str(...)');
                    }
                }

                // preg_replace с модификатором /e
                if ($name === 'preg_replace') {
                    $args = call_arguments($tokens, $next, $sig, $sigPos);
                    if (count($args) > 0) {
                        $pattern = arg_text($tokens, $args[0]);
                        if (has_e_modifier($pattern)) {
                            add_finding($findings, $rel, $ln, 'fatal', 'removed-7.0',
                                'preg_replace() с /e: удалён в PHP 7.0; preg_replace_callback()', 'preg_replace(...)');
                        }
                    }
                }
            }

            // FILTER_SANITIZE_STRING
            if ($name === 'filter_sanitize_string') {
                add_finding($findings, $rel, $ln, 'deprecated', 'deprecated-8.1',
                    'FILTER_SANITIZE_STRING устарел в PHP 8.1; htmlspecialchars()/strip_tags()', $text);
            }

            // E_STRICT
            if ($name === 'e_strict') {
                add_finding($findings, $rel, $ln, 'deprecated', 'deprecated-8.4',
                    'Константа E_STRICT устарела в PHP 8.4', $text);
            }

            // ReflectionParameter::getClass()
            if ($name === 'getclass') {
                $prev = $prevSig($i);
                $varIdx = $prev !== null ? $prevSig($prev) : null;
                if ($varIdx !== null && token_id($tokens[$varIdx]) === T_OBJECT_OPERATOR) {
                    $before = $prevSig($varIdx);
                    if ($before !== null && in_array(strtolower(token_text($tokens[$before])), array('$parameter', '$param'), true)) {
                        add_finding($findings, $rel, $ln, 'deprecated', 'deprecated-8.0',
                            'ReflectionParameter::getClass() устарел в PHP 8.0; getType()/getDeclaringClass()', $text);
                    }
                }
            }
        }

        // PHP 4 конструктор: метод с именем класса. В PHP 8.0 больше не вызывается.
        if ($id === T_FUNCTION && !empty($classStack)) {
            $fnIdx = $nextSig($i);
            if ($fnIdx !== null && token_id($tokens[$fnIdx]) === T_STRING) {
                $fnName = strtolower($tokens[$fnIdx][1]);
                $clsName = strtolower($classStack[count($classStack) - 1]['name']);
                if ($clsName !== '?' && $fnName === $clsName) {
                    add_finding($findings, $rel, $lines[$fnIdx], 'fatal', 'removed-8.0',
                        'PHP 4 конструктор ' . $tokens[$fnIdx][1] . '() больше не вызывается в PHP 8.0; переименовать в __construct()',
                        'function ' . $tokens[$fnIdx][1]);
                }
            }
        }

        // Объявление свойства/параметра с типом и default null (implicit nullable, 8.4)
        if ($id === T_FUNCTION) {
            // найти '('
            $open = $nextSig($i);
            while ($open !== null && token_text($tokens[$open]) !== '(') {
                $open = $nextSig($open);
            }
            if ($open !== null) {
                $params = call_arguments($tokens, $open, $sig, $sigPos);
                $seenDefault = false;
                $defaultParamName = '';
                foreach ($params as $range) {
                    // имя параметра: последний T_VARIABLE до '='
                    $eqPos = null;
                    $varPos = null;
                    for ($j = $range[0]; $j <= $range[1]; $j++) {
                        if (!is_significant($tokens[$j])) {
                            continue;
                        }
                        if (token_text($tokens[$j]) === '=' && $eqPos === null) {
                            $eqPos = $j;
                        }
                        if (token_id($tokens[$j]) === T_VARIABLE) {
                            $varPos = $j;
                        }
                    }
                    if ($varPos === null) {
                        continue;
                    }
                    $paramName = token_text($tokens[$varPos]);
                    if ($eqPos === null) {
                        if ($seenDefault) {
                            add_finding($findings, $rel, $lines[$varPos], 'deprecated', 'deprecated-8.0',
                                'Обязательный параметр ' . $paramName . ' после параметра со значением по умолчанию ' . $defaultParamName . ' (устарело в PHP 8.0)',
                                'function ' . $paramName);
                        }
                        continue;
                    }
                    // значение по умолчанию
                    $afterEq = $nextSig($eqPos);
                    $default = $afterEq !== null ? strtolower(token_text($tokens[$afterEq])) : '';
                    // есть ли тип перед переменной
                    $typeTokens = array();
                    $hasTypeName = false;
                    for ($j = $range[0]; $j < $varPos; $j++) {
                        if (!is_significant($tokens[$j])) {
                            continue;
                        }
                        $typeTokens[] = token_text($tokens[$j]);
                        $tid = token_id($tokens[$j]);
                        if ($tid === T_STRING || $tid === T_ARRAY || $tid === T_CALLABLE || $tid === T_NS_SEPARATOR || token_text($tokens[$j]) === '?') {
                            $hasTypeName = true;
                        }
                    }
                    $type = implode('', $typeTokens);
                    if ($default === 'null' && $hasTypeName && strpos($type, '?') === false && strtolower($type) !== 'mixed' && strpos(strtolower($type), 'null') === false) {
                        add_finding($findings, $rel, $lines[$varPos], 'deprecated', 'deprecated-8.4',
                            'Implicit nullable ' . $paramName . ': тип "' . $type . '" с default null; в PHP 8.4 deprecated, писать "?' . ltrim($type, '\\') . '"', 'function ' . $paramName);
                    }
                    $seenDefault = true;
                    $defaultParamName = $paramName;
                }
            }
        }

        // $var{...} - фигурные скобки для доступа к символу (удалено 8.0)
        if ($id === T_VARIABLE) {
            $next = $nextSig($i);
            if ($next !== null && token_text($tokens[$next]) === '{') {
                add_finding($findings, $rel, $ln, 'fatal', 'removed-8.0',
                    'Доступ к символу строки через {} удалён в PHP 8.0; использовать []', $text);
            }
        }
    }

    // Интерфейсы без return types (deprecated 8.1) - по классам
    // Упрощённо: ищем implements ArrayAccess/Iterator/... и наличие методов без ":"
    if (preg_match_all('/\bclass\s+([A-Za-z_][A-Za-z0-9_]*)[^{]*\bimplements\s+([^{]+)/i', $src, $m, PREG_OFFSET_CAPTURE)) {
        foreach ($m[1] as $k => $classMatch) {
            $classLine = substr_count(substr($src, 0, $classMatch[1]), "\n") + 1;
            $ifaces = strtolower($m[2][$k][0]);
            $hit = array();
            foreach ($interfaceReturnTypes as $iface) {
                if (preg_match('/\b' . $iface . '\b/', $ifaces)) {
                    $hit[] = $iface;
                }
            }
            if (count($hit) > 0) {
                add_finding($findings, $rel, $classLine, 'review', 'interface-return-types',
                    'Класс ' . $classMatch[0] . ' реализует ' . implode(', ', $hit) . ': проверить сигнатуры (в PHP 8.1 без return type будет deprecated, нужен #[\ReturnTypeWillChange])',
                    'class ' . $classMatch[0]);
            }
        }
    }
}

// Разрешение наследования для dynamic-properties: свойство может быть
// объявлено в родителе, тогда это не нарушение.
$resolved = array();
foreach ($findings as $f) {
    if ($f['category'] !== 'dynamic-properties') {
        $resolved[] = $f;
        continue;
    }
    $props = $f['props'];
    $cur = $f['class'];
    $external = false;
    $seen = array($cur => true);
    while (true) {
        if (!array_key_exists($cur, $classExtends)) {
            if ($cur !== $f['class']) {
                $external = true;
            }
            break;
        }
        $parent = $classExtends[$cur];
        if ($parent === null) {
            break;
        }
        if (isset($seen[$parent])) {
            break;
        }
        $seen[$parent] = true;
        if (isset($classProps[$parent])) {
            $props = array_values(array_diff($props, $classProps[$parent]));
        } else {
            $external = true;
        }
        $cur = $parent;
    }
    if (count($props) === 0) {
        continue;
    }
    $list = implode(', ', array_slice($props, 0, 10));
    $f['props'] = array_values($props);
    $f['message'] = 'Класс ' . $f['display'] . ': свойства без объявления (' . $list . ')'
        . ($external ? '; родитель вне проекта, проверить вручную' : '')
        . '; в PHP 8.2+ deprecated, объявить или #[AllowDynamicProperties]';
    if ($external) {
        $f['severity'] = 'review';
    }
    $resolved[] = $f;
}
$findings = $resolved;

// Сортировка и сводка
usort($findings, function ($a, $b) {
    if ($a['severity'] !== $b['severity']) {
        $order = array('fatal' => 0, 'behavior' => 1, 'deprecated' => 2, 'review' => 3);
        return $order[$a['severity']] - $order[$b['severity']];
    }
    if ($a['file'] !== $b['file']) {
        return strcmp($a['file'], $b['file']);
    }
    return $a['line'] - $b['line'];
});

$bySeverity = array();
$byCategory = array();
$byFile = array();
foreach ($findings as $f) {
    $bySeverity[$f['severity']] = isset($bySeverity[$f['severity']]) ? $bySeverity[$f['severity']] + 1 : 1;
    $byCategory[$f['category']] = isset($byCategory[$f['category']]) ? $byCategory[$f['category']] + 1 : 1;
    $byFile[$f['file']] = isset($byFile[$f['file']]) ? $byFile[$f['file']] + 1 : 1;
}
arsort($byCategory);
arsort($byFile);

$report = array(
    'generated_at' => date('c'),
    'root' => $root,
    'stats' => $stats,
    'by_severity' => $bySeverity,
    'by_category' => $byCategory,
    'top_files' => array_slice($byFile, 0, 40, true),
    'findings' => $findings,
);

if ($jsonOut !== null) {
    file_put_contents($jsonOut, json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
}

echo "PHP 8.5 scan\n";
echo "root: {$root}\n";
echo "files: {$stats['files']}, bytes: {$stats['bytes']}, parse errors: {$stats['parse_errors']}\n";
echo "findings: " . count($findings) . "\n";
foreach ($bySeverity as $sev => $n) {
    echo "  {$sev}: {$n}\n";
}
echo "by category:\n";
foreach ($byCategory as $cat => $n) {
    echo "  {$cat}: {$n}\n";
}
echo "top files:\n";
foreach (array_slice($byFile, 0, 15, true) as $file => $n) {
    echo "  {$file}: {$n}\n";
}
if ($jsonOut !== null) {
    echo "json: {$jsonOut}\n";
}
