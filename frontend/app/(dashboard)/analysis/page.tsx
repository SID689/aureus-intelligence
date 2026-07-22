import AnalysisPanel from "@/components/AnalysisPanel";
export default function AnalysisPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-white">Deep Analysis</h1>
        <p className="text-aureus-muted text-sm mt-0.5">
          Fundamental · Technical · Quantitative ensemble scoring.
        </p>
      </div>
      <AnalysisPanel />
    </div>
  );
}
