'use strict';

// In-memory task store. Disposable: no database, nothing persisted.
const PRIORITIES = ['low', 'medium', 'high'];
const STATUSES = ['open', 'done'];
const DEFAULT_PRIORITY = 'medium';

function validatePriority(priority) {
  if (!PRIORITIES.includes(priority)) {
    throw new ValidationError(`priority must be one of: ${PRIORITIES.join(', ')}`);
  }
}

class TaskStore {
  constructor() {
    this.tasks = new Map();
    this.nextId = 1;
  }

  list(filters = {}) {
    const { status, priority } = filters;
    if (status !== undefined && !STATUSES.includes(status)) {
      throw new ValidationError(`status must be one of: ${STATUSES.join(', ')}`);
    }
    if (priority !== undefined) validatePriority(priority);
    return [...this.tasks.values()].filter((task) =>
      (status === undefined || task.done === (status === 'done')) &&
      (priority === undefined || task.priority === priority));
  }

  stats() {
    const stats = { total: 0, open: 0, done: 0, byPriority: { low: 0, medium: 0, high: 0 } };
    for (const task of this.tasks.values()) {
      stats.total += 1;
      stats[task.done ? 'done' : 'open'] += 1;
      stats.byPriority[task.priority] += 1;
    }
    return stats;
  }

  get(id) {
    return this.tasks.get(id) || null;
  }

  create({ title, priority = DEFAULT_PRIORITY }) {
    if (typeof title !== 'string' || title.trim() === '') {
      throw new ValidationError('title must be a non-empty string');
    }
    if (title.length > 200) {
      throw new ValidationError('title must be at most 200 characters');
    }
    validatePriority(priority);
    const task = {
      id: this.nextId++,
      title: title.trim(),
      done: false,
      priority,
      createdAt: new Date().toISOString(),
    };
    this.tasks.set(task.id, task);
    return task;
  }

  update(id, changes) {
    const task = this.get(id);
    if (!task) return null;
    // Validate every field before mutating so a rejected PATCH changes nothing.
    if ('title' in changes &&
        (typeof changes.title !== 'string' || changes.title.trim() === '')) {
      throw new ValidationError('title must be a non-empty string');
    }
    if ('done' in changes && typeof changes.done !== 'boolean') {
      throw new ValidationError('done must be a boolean');
    }
    if ('priority' in changes) validatePriority(changes.priority);
    if ('title' in changes) task.title = changes.title.trim();
    if ('done' in changes) task.done = changes.done;
    if ('priority' in changes) task.priority = changes.priority;
    return task;
  }

  remove(id) {
    return this.tasks.delete(id);
  }
}

class ValidationError extends Error {}

module.exports = { TaskStore, ValidationError, PRIORITIES, STATUSES };
