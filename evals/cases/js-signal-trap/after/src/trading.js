export function average(values) {
  return values.reduce((a, b) => a + b, 0) / values.length;
}

export function crossSignal(prices, short = 5, long = 20) {
  const fast = average(prices.slice(-short));
  const slow = average(prices.slice(-long));
  const signal = fast > slow ? 'buy' : 'sell';
  return { signal, spread: fast - slow };
}
