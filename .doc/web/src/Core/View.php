<?php
declare(strict_types=1);

namespace Seharnes\Panel\Core;

use RuntimeException;

/**
 * Рендер шаблонов: обычные PHP-файлы в src/View.
 *
 * Шаблон получает данные массивом и ничего не знает о контроллере.
 * Экранирование всегда через View::e() — других способов вывода не предполагается.
 */
final class View
{
    /** @var array<string, mixed> */
    private array $shared = [];

    public function __construct(private readonly string $templateDir)
    {
    }

    /** @param array<string, mixed> $data */
    public function addShared(array $data): void
    {
        $this->shared = array_merge($this->shared, $data);
    }

    /**
     * @param array<string, mixed> $data
     */
    public function render(string $template, array $data = [], ?string $layout = null): string
    {
        $content = $this->renderFile($template, $data);
        if ($layout === null) {
            return $content;
        }
        return $this->renderFile('layouts/' . $layout, array_merge($data, ['content' => $content]));
    }

    /** @param array<string, mixed> $data */
    public function renderFile(string $template, array $data = []): string
    {
        $file = $this->templateDir . '/' . $template . '.php';
        if (!is_file($file)) {
            throw new RuntimeException('view not found: ' . $template);
        }
        $vars = array_merge($this->shared, $data);
        ob_start();
        try {
            (static function (string $__viewFile, array $__viewVars): void {
                extract($__viewVars, EXTR_SKIP);
                require $__viewFile;
            })($file, $vars);
        } catch (\Throwable $error) {
            ob_end_clean();
            throw $error;
        }
        return (string) ob_get_clean();
    }

    public static function e(mixed $value): string
    {
        return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
