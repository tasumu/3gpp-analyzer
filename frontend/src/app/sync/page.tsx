import { FTPBrowser } from "@/components/sync/FTPBrowser";

export default function SyncPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">FTP Browser</h1>
        <p className="mt-1 text-sm text-gray-500">
          Browse the 3GPP FTP server and sync document metadata from selected directories.
        </p>
      </div>

      <FTPBrowser />
    </div>
  );
}
