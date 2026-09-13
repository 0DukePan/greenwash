import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCount } from '../src/parse.mjs';

test('parseCount', () => {
  assert.equal(parseCount('{bad}'), 0);
});
