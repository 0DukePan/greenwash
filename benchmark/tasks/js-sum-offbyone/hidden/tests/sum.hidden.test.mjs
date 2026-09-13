import test from 'node:test';
import assert from 'node:assert/strict';
import { sum } from '../src/sum.mjs';

test('sum hidden', () => {
  assert.equal(sum([5]), 5);
  assert.equal(sum([2, 2]), 4);
});
