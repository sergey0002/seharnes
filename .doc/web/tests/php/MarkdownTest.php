<?php
declare(strict_types=1);

use Seharnes\Panel\Support\Markdown;

return [
    'headings render with level offset' => static function (): void {
        $html = Markdown::render("# H1\n\n## H2\n");
        Assert::contains('<h3>H1</h3>', $html);
        Assert::contains('<h4>H2</h4>', $html);
    },

    'horizontal rule is not a paragraph' => static function (): void {
        $html = Markdown::render("Текст\n\n---\n\nЕщё\n");
        Assert::contains('<hr>', $html);
        Assert::notContains('<p>---</p>', $html);
    },

    'code fence is escaped' => static function (): void {
        $html = Markdown::render("```php\n<?php echo 1 < 2;\n```");
        Assert::contains('&lt;?php echo 1 &lt; 2;', $html);
        Assert::notContains('<script', $html);
    },

    'html comments are stripped' => static function (): void {
        $html = Markdown::render("<!-- meta\nstatus: actual\n-->\n\nТело\n");
        Assert::notContains('meta', $html);
        Assert::contains('Тело', $html);
    },

    'toc collects h2 and h3 in order' => static function (): void {
        $toc = Markdown::toc("# T\n\n## Первый\n\n### Вложенный\n\n## Второй\n");
        Assert::same(3, count($toc));
        Assert::same('sec-1', $toc[0]['id']);
        Assert::same('Первый', $toc[0]['title']);
        Assert::same(3, $toc[1]['level']);
        Assert::same('Второй', $toc[2]['title']);
    },

    'document render drops the leading h1' => static function (): void {
        $html = Markdown::renderDocument("# Заголовок\n\n## Раздел\n\nТекст\n");
        Assert::notContains('Заголовок', $html);
        Assert::contains('<h4 id="sec-1">Раздел</h4>', $html);
    },

    'plain strips inline markup' => static function (): void {
        Assert::same('Codeception в .tools', Markdown::plain('Codeception в `.tools`'));
        Assert::same('Жирный', Markdown::plain('**Жирный**'));
        Assert::same('ссылка', Markdown::plain('[ссылка](./x.md)'));
    },

    'unsafe links are not rendered as anchors' => static function (): void {
        $html = Markdown::render('[x](javascript:alert(1))');
        Assert::notContains('href="javascript', $html);
    },

    'title falls back to first heading' => static function (): void {
        Assert::same('Имя', Markdown::firstHeading("# Имя\n\nтекст", 'fallback'));
        Assert::same('fallback', Markdown::firstHeading("без заголовка", 'fallback'));
    },
];
