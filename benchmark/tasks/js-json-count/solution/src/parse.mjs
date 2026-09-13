export function parseCount(s) {
  try {
    return JSON.parse(s).count;
  } catch (err) {
    return 0;
  }
}
