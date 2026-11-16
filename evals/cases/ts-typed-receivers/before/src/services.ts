export class Api {
  get(path: string) {
    return fetch(path);
  }
}

export class Store {
  set(key: string, value: unknown) {
    return { key, value };
  }
}

export class Repo {
  find(id: string) {
    return { id };
  }
}
