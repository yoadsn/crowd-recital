import { useCallback, useEffect, useState } from "react";
import { jwtDecode, JwtPayload } from "jwt-decode";
import { usePostHog } from "posthog-js/react";
import type { PostHog } from "posthog-js/react";

import {
  getUserIfLoggedIn,
  FailedFetchUserResponse,
  SuccessFetchUserResponse,
  loginUsingGoogleCredential,
  LoginResponse,
  logout,
} from "@/client/user";
import { User } from "../../types/user";
import { useLocalStorage } from "@uidotdev/usehooks";
import { INVITE_STORAGE_KEY } from "@/env/invites";
import { EnvConfig } from "@/env/config";

const reportLogin = (posthog: PostHog, loginResponse: LoginResponse) => {
  try {
    jwtDecode<JwtPayload & { email: string; name: string }>(
      loginResponse.accessToken,
    );
    posthog?.capture("logged_in");
  } catch (e) {
    // This is a non critical error supposedly.
    posthog?.capture("decode_access_token_failed");
    console.error(e);
  }
};

export type GoogleLoginProps = {
  onCredential: (loginCredential: string) => void;
};

export default function useLogin() {
  const posthog = usePostHog();
  const [csrfToken, setCsrfToken] = useState("");
  const [activeUser, setActiveUser] = useState<User | null>(null);
  const [loggingIn, setLoggingIn] = useState(true);
  const [accessToken, setAccessToken] = useLocalStorage<string>("actk", "");
  const [inviteValueObj] = useLocalStorage(INVITE_STORAGE_KEY, {
    inviteValue: "",
  });
  const { inviteValue } = inviteValueObj;

  useEffect(() => {
    const init = async () => {
      try {
        const fetchUserResponse = await getUserIfLoggedIn();
        // If login is required
        if (!fetchUserResponse.success) {
          const { g_csrf_token } = fetchUserResponse as FailedFetchUserResponse;
          setCsrfToken(g_csrf_token);
          setAccessToken("");
        } else {
          // If user is already logged in
          const { user } = fetchUserResponse as SuccessFetchUserResponse;
          setActiveUser(new User(user));
          posthog?.identify(user.id, {
            email: user.email,
            name: user.name,
            group: user.group,
          });
        }
      } finally {
        setLoggingIn(false);
      }
    };
    setLoggingIn(true);
    init();
  }, [accessToken]);

  const onLogout = useCallback(
    (reload: boolean = false) => {
      posthog?.capture("logout");
      posthog?.reset();
      logout().then(() => {
        setActiveUser(null);
        setAccessToken("");
        if (EnvConfig.get("auth_mode") === "xhost") {
          // Also end the xhost identity session (clears __Host-xhost_id),
          // otherwise the visitor would be silently re-authenticated on next load.
          window.location.href = "/xhost-auth/logout?return_to=/";
        } else if (reload) {
          window.location.reload();
        }
      });
    },
    [setActiveUser, setAccessToken],
  );

  const onGoogleLoginCredential = useCallback(
    (loginCredential: string) => {
      if (!csrfToken) {
        console.warn(
          "CSRF token not acquired in this session. Logging out to try again.",
        );
        onLogout(true);
      } else {
        const doLogin = async () => {
          posthog?.capture("authenticate_using_google_id");
          const loginResponse = await loginUsingGoogleCredential(
            loginCredential,
            csrfToken,
            inviteValue,
          );

          if (loginResponse) {
            reportLogin(posthog, loginResponse);
            setAccessToken(loginResponse.accessToken);
          }
        };

        doLogin();
      }
    },
    [setAccessToken, onLogout, csrfToken],
  );

  const googleLoginProps = {
    onCredential: onGoogleLoginCredential,
  };

  return { googleLoginProps, onLogout, activeUser, loggingIn, accessToken };
}
