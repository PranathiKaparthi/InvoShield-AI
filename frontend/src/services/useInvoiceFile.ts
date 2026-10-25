import { useEffect, useState } from 'react';
import { apiClient } from './api';

/**
 * The invoice file endpoint needs the login token, which a plain <iframe src> or <img src>
 * cannot send. Download the file with the token and hand the page a temporary local URL.
 */
export function useInvoiceFileUrl(id?: string | number | null): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (id === undefined || id === null || id === '') return;
    let objectUrl: string | null = null;
    let cancelled = false;
    apiClient
      .get(`/api/invoices/${id}/file`, { responseType: 'blob' })
      .then((res) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(res.data as Blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setUrl(null);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id]);

  return url;
}
