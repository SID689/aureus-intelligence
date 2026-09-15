import { LoadingRegion, SkeletonPageHeader, SkeletonSheet, SkeletonStatColumns, SkeletonTable } from "@/components/ui/Skeleton";

/** Shown by Next while a dashboard route's server work completes. */
export default function DashboardLoading() {
  return (
    <LoadingRegion label="Loading" className="space-y-6">
      <SkeletonPageHeader />
      <SkeletonSheet title={false}><SkeletonStatColumns columns={3} /></SkeletonSheet>
      <SkeletonSheet><SkeletonTable rows={5} /></SkeletonSheet>
    </LoadingRegion>
  );
}
