import { useContext } from "react";
import { useTranslation } from "react-i18next";
import GoogleLogin from "@/components/GoogleLogin";
import XhostLogin from "@/components/XhostLogin";

import useTrackPageView from "@/analytics/useTrackPageView";
import ivritAiLogo from "../../assets/ivrit_ai_logo.webp";
import { UserContext } from "@/context/user";
import HebrewSoup from "@/components/HebrewSoup/HebrewSoup";
import SystemTotalStats from "@/components/SystemTotalStats";
import { EnvConfig } from "@/env/config";

const Login = () => {
  useTrackPageView("login");
  const { t } = useTranslation();
  const { googleLoginProps } = useContext(UserContext);
  const isXhostAuth = EnvConfig.get("auth_mode") === "xhost";

  return (
    <div className="hero min-h-screen">
      <HebrewSoup />
      <div className="sm:w-2xl card m-5 bg-base-100 opacity-90 shadow-xl">
        <div className="card-body hero-content flex sm:flex-row">
          <aside>
            <img src={ivritAiLogo} alt="Ivrit.ai logo" />
          </aside>
          <div className="flex-col">
            <SystemTotalStats />
            <div className="my-8 text-center align-middle">
              <h1 className="text-3xl font-bold">{t("glossary.ivritai")}</h1>
              <h1 className="text-xl font-bold">
                {t("glossary.crowdRecitalSystem")}
              </h1>
            </div>
            <div className="card-actions my-4 flex flex-row justify-center">
              {isXhostAuth ? (
                <XhostLogin />
              ) : (
                <GoogleLogin {...googleLoginProps} />
              )}
            </div>
            <div className="text-center">
              <p className="py-2">{t("maroon_factual_leopard_rest")}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
