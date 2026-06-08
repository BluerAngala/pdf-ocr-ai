import { useState, useEffect, useCallback } from "react";
import { checkForUpdates, subscribeStatus, type DownloadStatus } from "../services/updater";

export function useUpdateCheck(_currentVersion: string) {
  const [showModal, setShowModal] = useState(false);
  const [showBadge, setShowBadge] = useState(false);
  const [status, setStatus] = useState<DownloadStatus | null>(null);

  useEffect(() => {
    const unsubscribe = subscribeStatus((newStatus) => {
      setStatus(newStatus);
      if (newStatus.type === "available") {
        setShowBadge(true);
      }
    });

    return unsubscribe;
  }, []);

  const checkUpdate = useCallback(async (silent: boolean = false) => {
    const result = await checkForUpdates();

    if (result.type === "error" && !silent) {
      setShowModal(true);
    } else if (result.type === "available") {
      if (silent) {
        setShowBadge(true);
      } else {
        setShowModal(true);
      }
    } else if (!silent && result.type === "uptodate") {
      setShowModal(true);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      checkUpdate(true);
    }, 10000);

    return () => clearTimeout(timer);
  }, [checkUpdate]);

  return {
    showModal,
    showBadge,
    status,
    setShowModal,
    setShowBadge,
    checkUpdate,
  };
}
