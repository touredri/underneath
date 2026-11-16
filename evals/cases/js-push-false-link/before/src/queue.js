export class Queue {
  constructor() {
    this.items = [];
  }

  push(job) {
    this.items.push(job);
    return this.items.length;
  }
}
