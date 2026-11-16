export function getJson(url) {
  return fetch(url).then((r) => r.json());
}
