import { useEffect, useReducer } from 'react';

type State<T> = { status: 'idle' | 'loading' | 'done' | 'error'; data?: T; error?: string };
type Action<T> = { type: 'start' } | { type: 'done'; data: T } | { type: 'fail'; error: string };

function reducer<T>(state: State<T>, action: Action<T>): State<T> {
  switch (action.type) {
    case 'start':
      return { status: 'loading' };
    case 'done':
      return { status: 'done', data: action.data };
    case 'fail':
      return { status: 'error', error: action.error };
  }
}

export function useFetch<T>(url: string): State<T> {
  const [state, dispatch] = useReducer(reducer<T>, { status: 'idle' });
  useEffect(() => {
    const controller = new AbortController();
    dispatch({ type: 'start' });
    fetch(url, { signal: controller.signal })
      .then((r) => r.json() as Promise<T>)
      .then((data) => dispatch({ type: 'done', data }))
      .catch((e) => controller.signal.aborted || dispatch({ type: 'fail', error: String(e) }));
    return () => controller.abort();
  }, [url]);
  return state;
}
