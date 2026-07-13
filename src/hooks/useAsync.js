import { useCallback, useEffect, useRef, useState } from 'react';

export function useAsync(load, dependencies = []) {
  const [reloadVersion, setReloadVersion] = useState(0);
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    setState({ data: null, error: null, loading: true });

    Promise.resolve(load(controller.signal))
      .then((data) => {
        if (mounted.current && !controller.signal.aborted) setState({ data, error: null, loading: false });
      })
      .catch((error) => {
        if (mounted.current && !controller.signal.aborted && error?.name !== 'AbortError') {
          setState({ data: null, error, loading: false });
        }
      });

    return () => {
      mounted.current = false;
      controller.abort();
    };
  }, [...dependencies, reloadVersion]);

  const reload = useCallback(() => setReloadVersion((value) => value + 1), []);
  return { ...state, reload };
}
