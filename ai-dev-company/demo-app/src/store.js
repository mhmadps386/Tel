'use strict';

// In-memory task store. Disposable: no database, nothing persisted.
class TaskStore {
  constructor() {
    this.tasks = new Map();
    this.nextId = 1;
  }

  list() {
    return [...this.tasks.values()];
  }

  get(id) {
    return this.tasks.get(id) || null;
  }

  create({ title }) {
    if (typeof title !== 'string' || title.trim() === '') {
      throw new ValidationError('title must be a non-empty string');
    }
    if (title.length > 200) {
      throw new ValidationError('title must be at most 200 characters');
    }
    const task = {
      id: this.nextId++,
      title: title.trim(),
      done: false,
      createdAt: new Date().toISOString(),
    };
    this.tasks.set(task.id, task);
    return task;
  }

  update(id, changes) {
    const task = this.get(id);
    if (!task) return null;
    if ('title' in changes) {
      if (typeof changes.title !== 'string' || changes.title.trim() === '') {
        throw new ValidationError('title must be a non-empty string');
      }
      task.title = changes.title.trim();
    }
    if ('done' in changes) {
      if (typeof changes.done !== 'boolean') {
        throw new ValidationError('done must be a boolean');
      }
      task.done = changes.done;
    }
    return task;
  }

  remove(id) {
    return this.tasks.delete(id);
  }
}

class ValidationError extends Error {}

module.exports = { TaskStore, ValidationError };
