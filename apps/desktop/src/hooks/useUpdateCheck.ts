import { useState, useEffect, useCallback } from "react";
import { checkForUpdates, type CheckResult } from "../services/updater";

export function useUpdateCheck(currentVersion: string) {
  const [showModal, setShowModal] = useState(false);
  const [showBadge, setShowBadge] = useState(false);
  const [checkResult, setCheckResult] = useState<CheckResult | null>(null);

  const checkUpdate = useCallback(
    async (silent: boolean = false) => {
      const result = await checkForUpdates(currentVersion);
      setCheckResult(result);

      if (result.hasUpdate) {
        if (silent) {
          setShowBadge(true);
        } else {
          setShowModal(true);
        }
      } else if (!silent && !result.error) {
        setShowModal(true);
      }
    },
    [currentVersion],
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      checkUpdate(true);
    }, 10000);

    return () => clearTimeout(timer);
  }, [checkUpdate]);

  return {
    showModal,
    showBadge,
    checkResult,
    setShowModal,
    setShowBadge,
    checkUpdate,
  };
}
