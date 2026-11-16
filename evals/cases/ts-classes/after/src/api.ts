export class HttpClient {
  constructor(private base: string) {}

  request(path: string) {
    return fetch(this.base + path).then((r) => r.json());
  }
}

export class UsersApi extends HttpClient {
  list() {
    return this.request('/users');
  }
}

export function makeUsersApi() {
  return new UsersApi('/api');
}
