import test from 'node:test';
import assert from 'node:assert/strict';
import { isEven } from '../src/parity.mjs';

test('isEven hidden', () => {
  assert.equal(isEven(3), false);
  assert.equal(isEven(0), true);
});
