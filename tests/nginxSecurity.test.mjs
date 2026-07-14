import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('nginx rejects unknown hosts before serving localhost', async () => {
  const config = await readFile(
    new URL('../docker/nginx.conf', import.meta.url),
    'utf8',
  )

  const rejectServer = config.indexOf('listen 80 default_server;')
  const allowedServer = config.indexOf('server_name localhost 127.0.0.1;')

  assert.notEqual(rejectServer, -1)
  assert.notEqual(allowedServer, -1)
  assert.ok(rejectServer < allowedServer)
  assert.match(config.slice(rejectServer, allowedServer), /return 444;/)
})
