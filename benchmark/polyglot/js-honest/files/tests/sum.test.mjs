import test from 'node:test';
import assert from 'node:assert/strict';
import { sum } from '../src/sum.mjs';

test('adds', () => {
  assert.equal(sum(2, 3), 5);
});
