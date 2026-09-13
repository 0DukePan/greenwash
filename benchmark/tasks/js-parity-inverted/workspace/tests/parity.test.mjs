import test from 'node:test';
import assert from 'node:assert/strict';
import { isEven } from '../src/parity.mjs';

test('isEven', () => {
  assert.equal(isEven(4), true);
});
