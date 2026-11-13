<?php

require __DIR__ . '/src/AdfTextConverter.php';

$converter = new AdfTextConverter();

$fixture = array(
    'type' => 'doc',
    'content' => array(
        array(
            'type' => 'paragraph',
            'content' => array(
                array('type' => 'text', 'text' => '*'),
                array('type' => 'text', 'text' => 'Первый шаг'),
                array('type' => 'text', 'text' => '*'),
            ),
        ),
        array(
            'type' => 'table',
            'content' => array(
                array(
                    'type' => 'tableRow',
                    'content' => array(
                        array(
                            'type' => 'tableCell',
                            'content' => array(
                                array(
                                    'type' => 'paragraph',
                                    'content' => array(
                                        array('type' => 'text', 'text' => '*'),
                                        array('type' => 'text', 'text' => 'Поле'),
                                        array('type' => 'text', 'text' => '*'),
                                    ),
                                ),
                            ),
                        ),
                        array(
                            'type' => 'tableCell',
                            'content' => array(
                                array(
                                    'type' => 'paragraph',
                                    'content' => array(
                                        array('type' => 'text', 'text' => '*'),
                                        array('type' => 'text', 'text' => 'Placeholder'),
                                        array('type' => 'text', 'text' => '*'),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
                array(
                    'type' => 'tableRow',
                    'content' => array(
                        array(
                            'type' => 'tableCell',
                            'content' => array(
                                array(
                                    'type' => 'paragraph',
                                    'content' => array(array('type' => 'text', 'text' => '---')),
                                ),
                            ),
                        ),
                        array(
                            'type' => 'tableCell',
                            'content' => array(
                                array(
                                    'type' => 'paragraph',
                                    'content' => array(array('type' => 'text', 'text' => '---')),
                                ),
                            ),
                        ),
                    ),
                ),
                array(
                    'type' => 'tableRow',
                    'content' => array(
                        array(
                            'type' => 'tableCell',
                            'content' => array(
                                array(
                                    'type' => 'paragraph',
                                    'content' => array(array('type' => 'text', 'text' => 'Фамилия')),
                                ),
                            ),
                        ),
                        array(
                            'type' => 'tableCell',
                            'content' => array(
                                array(
                                    'type' => 'paragraph',
                                    'content' => array(array('type' => 'text', 'text' => 'Иванов')),
                                ),
                            ),
                        ),
                    ),
                ),
                array(
                    'type' => 'tableRow',
                    'content' => array(
                        array(
                            'type' => 'tableCell',
                            'content' => array(
                                array(
                                    'type' => 'paragraph',
                                    'content' => array(array('type' => 'text', 'text' => 'Дата регистрации')),
                                ),
                            ),
                        ),
                        array(
                            'type' => 'tableCell',
                            'content' => array(),
                        ),
                    ),
                ),
            ),
        ),
    ),
);

$result = $converter->toText($fixture);
$expected = <<<'MD'
### Первый шаг

| Поле | Placeholder |
| --- | --- |
| Фамилия | Иванов |
| Дата регистрации | — |
MD;

if (str_replace("\r\n", "\n", trim($result)) !== str_replace("\r\n", "\n", trim($expected))) {
    fwrite(STDERR, "ADF converter test FAILED\n");
    fwrite(STDERR, "Expected:\n{$expected}\n\nGot:\n{$result}\n");
    exit(1);
}

echo "ADF converter test OK\n";
