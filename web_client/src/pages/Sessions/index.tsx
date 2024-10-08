import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { HeadphonesIcon, RefreshCwIcon, TrashIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { twJoin } from "tailwind-merge";

import useTrackPageView from "@/analytics/useTrackPageView";
import { getSessionsOptions } from "@/client/queries/sessions";
import { SortOrder } from "@/client/types/common";
import SortCol from "@/components/DataTable/SortCol";
import { useSortState } from "@/components/DataTable/useSortState";
import SessionDelete from "@/components/SessionDelete";
import useSessionDelete from "@/components/SessionDelete/useSessionDelete";
import SubTrackingSessionPreview from "@/components/SessionPreview/subTrackingPreview";
import StatusDisplay from "@/components/SessionStatusDisplay";
import TablePager from "@/components/TablePager";
import WholePageLoading from "@/components/WholePageLoading";
import { RecitalSessionStatus, RecitalSessionType } from "@/types/session";
import { secondsToHourMinuteSecondString } from "@/utils";

type RecordNowCtaProps = {
  ctaText: string;
};

const RecordNowCta = ({ ctaText }: RecordNowCtaProps) => {
  return (
    <Link to="/documents" className="btn btn-primary">
      {ctaText}
    </Link>
  );
};

const NoRecordingsHero = () => {
  const { t } = useTranslation("recordings");
  return (
    <div className="container hero mx-auto min-h-screen-minus-topbar">
      <div className="hero-content text-center">
        <div className="max-w-md">
          <h1 className="text-4xl font-bold">
            {t("nimble_house_carp_intend")}
          </h1>
          <p className="py-6">{t("orange_zesty_flea_coax")}</p>
          <RecordNowCta ctaText={t("shy_level_bird_mix")} />
        </div>
      </div>
    </div>
  );
};

const itemsPerPage = 8;

enum SortColumnsEnum {
  CREATED_AT = "created_at",
  UPDATED_AT = "updated_at",
}

const isSessionExpectedToBeUpdated = (session: RecitalSessionType) =>
  // Non - final statuses will update soon
  ![RecitalSessionStatus.Uploaded, RecitalSessionStatus.Discarded].includes(
    session.status,
  ) ||
  // Sessions to delete which are not yet deleted would udpate soon
  (session.disavowed && session.status !== RecitalSessionStatus.Discarded);

const Sessions = () => {
  const { t } = useTranslation("recordings");
  useTrackPageView("sessions");

  // Sessions Table Data
  const [page, setPage] = useState(1);
  const sortState = useSortState<SortColumnsEnum>(
    SortColumnsEnum.CREATED_AT,
    SortOrder.DESC,
  );
  const { data, isError, isPending, isPlaceholderData, refetch, isFetching } =
    useQuery({
      ...getSessionsOptions(page, itemsPerPage, undefined, {
        sortColumns: [sortState.sortCol],
        sortOrders: [sortState.sortOrder],
      }),
      refetchInterval: (query) => {
        const data = query.state.data;
        const intervalPeriod = data?.data.some(isSessionExpectedToBeUpdated)
          ? 15000
          : 60000;

        return intervalPeriod;
      },
      refetchOnMount: "always",
    });

  const totalItems = data?.total_count || 0;
  const totalPages = Math.ceil(totalItems / itemsPerPage);

  // Session Preview State
  const sessionPreviewRef = useRef<HTMLDialogElement>(null);
  const [previewedSessionId, setPreviewedSessionId] = useState<string>("");
  useEffect(() => {
    if (previewedSessionId) {
      sessionPreviewRef.current?.showModal();
    }
    return () => {
      sessionPreviewRef.current?.close();
    };
  }, [previewedSessionId]);
  const onClose = useCallback(() => setPreviewedSessionId(""), []);

  // Sessions Delete Confirm State
  const [
    deleteConfirmRef,
    setToDeleteSessionId,
    onDelete,
    onCancel,
    deletionPending,
  ] = useSessionDelete();

  if (isPending) {
    return <WholePageLoading />;
  }

  if (isError) {
    return <div>{t("early_icy_beetle_pull")}</div>;
  }

  if (totalItems === 0) {
    return <NoRecordingsHero />;
  }

  return (
    <div className="mx-auto w-full max-w-6xl">
      <div className="mx-4 mb-4 flex items-center justify-between">
        <h1 className="text-2xl">
          {t("warm_green_trout_propel", { count: 0 })}
        </h1>
        <button className="btn btn-xs m-2 sm:btn-sm" onClick={() => refetch()}>
          {isFetching ? (
            <span className="loading loading-infinity loading-sm" />
          ) : (
            <RefreshCwIcon className="h-4 w-4" />
          )}
        </button>
      </div>
      <div dir="rtl" className="overflow-x-scroll">
        <table className="table table-auto">
          <thead>
            <tr>
              <SortCol
                label={t("agent_factual_toucan_stop")}
                colName={SortColumnsEnum.CREATED_AT}
                {...sortState}
              />
              <th>{t("lazy_sour_lamb_race")}</th>
              <th>{t("lost_fair_jay_cry")}</th>
              <th></th>
              <th>{t("cozy_fuzzy_canary_loop")}</th>
              <SortCol
                label={t("royal_short_scallop_feast")}
                colName={SortColumnsEnum.UPDATED_AT}
                {...sortState}
              />
              <th>{t("each_mad_chicken_slurp")}</th>
            </tr>
          </thead>
          <tbody>
            {data?.data.map((rs) => (
              <tr
                className={twJoin(
                  "hover:bg-base-200",
                  isPlaceholderData && "skeleton opacity-50",
                )}
                key={rs.id}
              >
                <td dir="ltr">{new Date(rs.created_at).toLocaleString()}</td>
                <td>
                  <StatusDisplay status={rs.status} disavowed={rs.disavowed} />
                </td>
                <td>
                  {secondsToHourMinuteSecondString(rs.duration || 0, false)}
                </td>
                <td>
                  <div className="flex min-w-24 items-center justify-center gap-2">
                    {rs.status == RecitalSessionStatus.Uploaded && (
                      <button
                        onClick={() => setPreviewedSessionId(rs.id)}
                        className="btn btn-outline btn-sm sm:btn-xs sm:gap-2"
                      >
                        <div className="hidden sm:block">
                          {t("suave_bad_moth_intend")}
                        </div>
                        <HeadphonesIcon className="h-4 w-4 sm:h-4 sm:w-4" />
                      </button>
                    )}
                    {!rs.disavowed && (
                      <button
                        onClick={() => setToDeleteSessionId(rs.id)}
                        className="btn btn-ghost btn-sm text-error sm:btn-xs sm:gap-2"
                      >
                        <TrashIcon className="h-4 w-4 sm:h-4 sm:w-4" />
                      </button>
                    )}
                  </div>
                </td>
                <td className="max-w-20 bg-inherit text-sm">
                  <span
                    dir="ltr"
                    className={twJoin(
                      "block justify-start overflow-hidden overflow-ellipsis bg-inherit contain-paint",
                      // Touch device expansion support
                      "nomouse:focus-within:inline-flex nomouse:focus-within:min-w-full nomouse:focus-within:border nomouse:focus-within:p-2",
                      // Mouse device expansion support
                      "hover:inline-flex hover:min-w-full hover:border hover:px-2",
                    )}
                    tabIndex={0}
                  >
                    {rs.id}
                  </span>
                </td>
                <td dir="ltr">{new Date(rs.updated_at).toLocaleString()}</td>
                <td>{rs.document?.title}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <TablePager
        key={totalPages}
        page={page}
        totalPages={totalPages}
        setPage={setPage}
      />
      <div className="sticky my-6 text-center">
        <RecordNowCta ctaText={t("few_least_fox_compose")} />
      </div>
      <SubTrackingSessionPreview
        id={previewedSessionId}
        ref={sessionPreviewRef}
        onClose={onClose}
      />
      <SessionDelete
        ref={deleteConfirmRef}
        progress={deletionPending}
        onDelete={onDelete}
        onCancel={onCancel}
      />
    </div>
  );
};

export default Sessions;
