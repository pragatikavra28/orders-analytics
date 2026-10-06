import { createContext, useContext, useEffect, useReducer, useCallback } from "react";
import { fetchSummary, fetchOrders } from "./api";

const initial = {
  filters: { start: "", end: "", category: "", status: "", currency: "USD" },
  view: "revenue", // revenue | orders
  page: 1, pageSize: 5,
  summary: null, orders: null, options: { categories: [], statuses: [] },
  loading: true, error: null,
};

function reducer(s, a) {
  switch (a.type) {
    case "filters": return { ...s, filters: { ...s.filters, ...a.payload }, page: 1 };
    case "view": return { ...s, view: a.payload };
    case "page": return { ...s, page: a.payload };
    case "pageSize": return s.pageSize === a.payload ? s : { ...s, pageSize: a.payload, page: 1 };
    case "loading": return { ...s, loading: true, error: null };
    case "loaded": return { ...s, loading: false, summary: a.summary, orders: a.orders,
      options: a.summary.meta.options || s.options };
    case "error": return { ...s, loading: false, error: a.payload };
    default: return s;
  }
}

const Ctx = createContext();
export const useStore = () => useContext(Ctx);

export function StoreProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initial);
  const { filters, page, pageSize } = state;

  const load = useCallback(async () => {
    dispatch({ type: "loading" });
    try {
      const [summary, orders] = await Promise.all([fetchSummary(filters), fetchOrders(filters, page, pageSize)]);
      dispatch({ type: "loaded", summary, orders });
    } catch (e) {
      dispatch({ type: "error", payload: e.message });
    }
  }, [filters, page, pageSize]);

  useEffect(() => { load(); }, [load]);

  return <Ctx.Provider value={{ state, dispatch, reload: load }}>{children}</Ctx.Provider>;
}
