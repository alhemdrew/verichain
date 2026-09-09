import { createContext, useContext } from 'react';

export type SearchContextValue = {
  query: string;
  setQuery: (value: string) => void;
};

export const SearchContext = createContext<SearchContextValue | null>(null);

export function useSearch() {
  const context = useContext(SearchContext);
  if (!context) {
    throw new Error('useSearch must be used within SearchProvider');
  }
  return context;
}
