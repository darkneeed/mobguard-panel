import { useEffect, useState } from "react";

import { api, Session } from "../api/client";

export function useSession() {
  const [session, setSession] = useState<Session | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "guest">("loading");

  useEffect(() => {
    api
      .me()
      .then((payload) => {
        setSession(payload);
        setState("ready");
      })
      .catch(() => {
        setSession(null);
        setState("guest");
      });
  }, []);

  return { session, setSession, state, setState };
}
