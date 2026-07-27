import { usePostHog } from "posthog-js/react";

// xhost's built-in Google sign-in dance (see https://docs.xhostd.com/oauth).
// Signed-out visitors are sent to /xhost-auth/login, which runs the Google
// login flow and, on success, sets the __Host-xhost_id identity cookie and
// redirects back to return_to. The backend verifies that cookie on the next
// request (see server/utility/authentication/xhost_auth.py) - no client-side
// token handling is needed here.
const XhostLogin = () => {
  const posthog = usePostHog();

  const returnTo = `${window.location.pathname}${window.location.search}`;
  const loginUrl = `/xhost-auth/login?return_to=${encodeURIComponent(returnTo)}`;

  return (
    <a
      className="btn btn-primary"
      href={loginUrl}
      onClick={() => posthog?.capture("login_button_clicked")}
    >
      Sign in
    </a>
  );
};

export default XhostLogin;
