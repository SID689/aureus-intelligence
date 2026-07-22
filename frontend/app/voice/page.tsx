import VoiceInterface from "@/components/VoiceInterface";

const USER_ID = "00000000-0000-0000-0000-000000000001";

export default function VoicePage() {
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Voice Interface</h1>
        <p className="text-aureus-muted text-sm mt-1">
          Speak naturally with your AI financial analyst. Context is remembered across your session.
        </p>
      </div>
      <VoiceInterface userId={USER_ID} tier="elite" />
    </div>
  );
}
