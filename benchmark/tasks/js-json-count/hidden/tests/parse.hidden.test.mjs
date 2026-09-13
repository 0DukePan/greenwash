import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCount } from '../src/parse.mjs';

test('parseCount hidden', () => {
  assert.equal(parseCount('{"count": 3}'), 3);
  assert.equal(parseCount('null'), 0);
});
