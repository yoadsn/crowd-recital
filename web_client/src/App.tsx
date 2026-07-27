import { useCallback, useContext, useState } from "react";
import { PostHogProvider } from "posthog-js/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createRouter } from "@tanstack/react-router";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

import { routeTree } from "./routeTree.gen";
import { getPosthogClient } from "@/analytics";
import {
  withTrackedErrorBoundary,
  reportCaughtError,
} from "@/analytics/TrackedErrorBoundary/withTrackedErrorBoundary";
import { FallbackErrorPage } from "@/analytics/TrackedErrorBoundary";
import { UserContext } from "@/context/user";
import useLogin from "@/hooks/useLogin";
import WholePageLoading from "@/components/WholePageLoading";
import { MicCheckModal } from "@/components/MicCheck";
import CentredPage from "@/components/CenteredPage";
import NotFound from "@/pages/NotFound";

const queryClient = new QueryClient();

const router = createRouter({
  routeTree,
  context: {
    queryClient,
    // auth will initially be undefined
    // We'll be passing down the auth state from within a React component
    auth: undefined!,
    mic: undefined!,
  },
  defaultNotFoundComponent: NotFound,
  defaultErrorComponent: FallbackErrorPage,
  defaultOnCatch: reportCaughtError,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

function AppWithProviders() {
  const [micCheckActive, setMicCheckActive] = useState(false);
  const onCloseMicCheck = useCallback(() => {
    setMicCheckActive(false);
  }, []);

  const { auth } = useContext(UserContext);

  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider
        router={router}
        context={{ auth, mic: { micCheckActive, setMicCheckActive } }}
      />
      <MicCheckModal open={micCheckActive} onClose={onCloseMicCheck} />
      <ReactQueryDevtools />
    </QueryClientProvider>
  );
}

function AppWithAuthContext() {
  const { activeUser, googleLoginProps, accessToken, onLogout, loggingIn } =
    useLogin();

  if (loggingIn) {
    return (
      <CentredPage>
        <WholePageLoading />;
      </CentredPage>
    );
  }

  return (
    <UserContext.Provider
      value={{
        auth: { user: activeUser, accessToken },
        logout: onLogout,
        googleLoginProps: googleLoginProps,
      }}
    >
      <AppWithProviders />
    </UserContext.Provider>
  );
}

// Auth must always be wired up (it provides the real UserContext that the
// router relies on for its beforeLoad guards) - PostHog is optional and only
// wraps around it when configured. These two concerns used to be conflated:
// when PostHog was unconfigured, AppWithAuthContext (and therefore the real
// auth context) was skipped entirely, leaving the router's `auth` context
// value undefined and crashing every route's beforeLoad guard.
const posthog = getPosthogClient();
const TrackedApp = posthog
  ? () => (
      <PostHogProvider client={posthog}>
        <AppWithAuthContext />
      </PostHogProvider>
    )
  : AppWithAuthContext;

const WrappedErrorBoundedApp = withTrackedErrorBoundary(TrackedApp);

export default WrappedErrorBoundedApp;
