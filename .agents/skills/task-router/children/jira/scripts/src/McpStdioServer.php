<?php

final class McpStdioServer
{
    /** @var array<string, array{definition: array, handler: callable}> */
    private $handlers = array();

    public function registerTool($name, array $definition, callable $handler)
    {
        $this->handlers[$name] = array(
            'definition' => $definition,
            'handler' => $handler,
        );
    }

    public function run()
    {
        while ($message = $this->readMessage()) {
            if (!isset($message['method'])) {
                continue;
            }

            $method = $message['method'];
            $id = array_key_exists('id', $message) ? $message['id'] : null;
            $params = isset($message['params']) && is_array($message['params']) ? $message['params'] : array();

            try {
                if ($method === 'initialize') {
                    $this->writeResponse($id, array(
                        'protocolVersion' => '2024-11-05',
                        'capabilities' => array(
                            'tools' => array('listChanged' => false),
                        ),
                        'serverInfo' => array(
                            'name' => 'jira-task-mcp',
                            'version' => '1.0.0',
                        ),
                    ));
                    continue;
                }

                if ($method === 'notifications/initialized' || $method === 'ping') {
                    continue;
                }

                if ($method === 'tools/list') {
                    $tools = array();
                    foreach ($this->handlers as $name => $item) {
                        $tools[] = array(
                            'name' => $name,
                            'description' => $item['definition']['description'],
                            'inputSchema' => $item['definition']['inputSchema'],
                        );
                    }

                    $this->writeResponse($id, array('tools' => $tools));
                    continue;
                }

                if ($method === 'tools/call') {
                    $toolName = isset($params['name']) ? $params['name'] : '';
                    $arguments = isset($params['arguments']) && is_array($params['arguments'])
                        ? $params['arguments']
                        : array();

                    if (!isset($this->handlers[$toolName])) {
                        throw new InvalidArgumentException('Unknown tool: ' . $toolName);
                    }

                    $result = call_user_func($this->handlers[$toolName]['handler'], $arguments);
                    $this->writeResponse($id, $result);
                    continue;
                }
            } catch (Exception $e) {
                if ($id !== null) {
                    $this->writeError($id, -32000, $e->getMessage());
                }
            }
        }
    }

    private function readMessage()
    {
        $headers = array();

        while (true) {
            $line = fgets(STDIN);
            if ($line === false) {
                return null;
            }

            $line = rtrim($line, "\r\n");
            if ($line === '') {
                break;
            }

            $pos = strpos($line, ':');
            if ($pos !== false) {
                $headers[strtolower(trim(substr($line, 0, $pos)))] = trim(substr($line, $pos + 1));
            }
        }

        if (!isset($headers['content-length'])) {
            return null;
        }

        $length = (int) $headers['content-length'];
        if ($length <= 0) {
            return null;
        }

        $body = stream_get_contents(STDIN, $length);
        if ($body === false || $body === '') {
            return null;
        }

        $decoded = json_decode($body, true);
        return is_array($decoded) ? $decoded : null;
    }

    private function writeResponse($id, $result)
    {
        if ($id === null) {
            return;
        }

        $this->write(array(
            'jsonrpc' => '2.0',
            'id' => $id,
            'result' => $result,
        ));
    }

    private function writeError($id, $code, $message)
    {
        $this->write(array(
            'jsonrpc' => '2.0',
            'id' => $id,
            'error' => array(
                'code' => $code,
                'message' => $message,
            ),
        ));
    }

    private function write(array $payload)
    {
        $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        if ($json === false) {
            return;
        }

        fwrite(STDOUT, 'Content-Length: ' . strlen($json) . "\r\n\r\n" . $json);
        fflush(STDOUT);
    }
}
