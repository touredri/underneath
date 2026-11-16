import { Api, Repo, Store } from './services';

export class ProfileService {
  private store = new Store();

  constructor(private api: Api) {}

  load(id: string, seen: Map<string, boolean>) {
    seen.set(id, true);
    this.store.set(id, null);
    const repo = new Repo();
    repo.find(id);
    return this.api.get(`/profiles/${id}`);
  }
}
