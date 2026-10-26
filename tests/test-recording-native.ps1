param([switch]$Loopback)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '../addon/globalPlugins/whatsappWebPlusCompanion/resources/recording/Recorder.cs'
$code = Get-Content -LiteralPath $source -Raw
$code += Get-Content -LiteralPath (Join-Path (Split-Path $source) 'CallState.cs') -Raw
$code += Get-Content -LiteralPath (Join-Path (Split-Path $source) 'CallRecovery.cs') -Raw
$code += @'
namespace CompanionRecording {
    public static class NativeTest {
        public static void Run(bool loopback) {
            int starts = 0; bool cancelled = true;
            if (Recorder.StartSources(() => cancelled, () => starts++, () => starts++) || starts != 0)
                throw new Exception("Cancelled capture started");
            cancelled = false;
            if (Recorder.StartSources(() => cancelled, () => { starts++; cancelled = true; }, () => starts++) || starts != 1)
                throw new Exception("Second capture started after cancellation");
            cancelled = false; starts = 0;
            if (!Recorder.StartSources(() => cancelled, () => starts++, () => starts++) || starts != 2)
                throw new Exception("Capture did not start");
            foreach (string duration in new string[] { "00:00", "02\u223611", "1:02:11", "120:00" })
                if (!CallState.Duration(duration)) throw new Exception("Duration rejected");
            foreach (string status in new string[] { "Calling", "Ringing", "Connecting", "02:99", "ended 02:11" })
                if (CallState.Duration(status)) throw new Exception("Non-duration accepted");
            string path = Path.Combine(Path.GetTempPath(), "wwp-wav-test-" + Guid.NewGuid() + ".wav");
            try {
                using (var wav = new Wav(path)) {
                    wav.Write(0, 0, new byte[] { 1, 2, 3, 4 });
                    wav.Write(1, 1, new byte[] { 5, 6 });
                    wav.Write(0, 3, new byte[] { 7, 8 });
                    wav.Write(1, -1, new byte[] { 9, 10, 11, 12 });
                }
                byte[] data = File.ReadAllBytes(path);
                byte[] expected = { 1, 2, 11, 12, 3, 4, 5, 6, 0, 0, 0, 0, 7, 8, 0, 0 };
                if (data.Length != 60 || BitConverter.ToUInt32(data, 4) != 52 ||
                    BitConverter.ToUInt32(data, 40) != 16) throw new Exception("WAV size");
                for (int i = 0; i < expected.Length; i++)
                    if (data[44 + i] != expected[i]) throw new Exception("WAV channel alignment");
                bool refused = false;
                try { using (var wav = new Wav(path)) { } } catch (IOException) { refused = true; }
                if (!refused) throw new Exception("Existing recording overwritten");
                string limited = path + ".limit.wav";
                try {
                    using (var wav = new Wav(limited, 4)) {
                        if (!wav.Empty || wav.Full) throw new Exception("New WAV state");
                        wav.Write(0, 0, new byte[] { 1, 2, 3, 4, 5, 6 });
                        if (wav.Empty || wav.Full) throw new Exception("WAV below limit");
                        wav.Write(0, 3, new byte[] { 7, 8, 9, 10, 11, 12 });
                        if (!wav.Full) throw new Exception("WAV limit not reported");
                        wav.Write(1, 5, new byte[] { 13, 14 });
                    }
                    if (new FileInfo(limited).Length != 44 + 4 * 4) throw new Exception("WAV limit exceeded");
                } finally { if (File.Exists(limited)) File.Delete(limited); }
                var tracker = new CallEndTracker();
                foreach (bool? state in new bool?[] { false, false, null, false, false, true, false, false })
                    if (tracker.Observe(state)) throw new Exception("Call end without consecutive absences");
                if (!tracker.Observe(false)) throw new Exception("Confirmed call end ignored");
                using (var unknown = new CallMonitor(5, () => null))
                using (var absent = new CallMonitor(5, () => false))
                using (var failing = new CallMonitor(5, () => { throw new InvalidOperationException(); })) {
                    if (!SpinWait.SpinUntil(() => absent.Ended, 3000)) throw new Exception("Ended call not detected");
                    Thread.Sleep(100);
                    if (unknown.Ended || failing.Ended) throw new Exception("Uncertain call state stopped recording");
                }
                if (loopback) {
                    // This test captures only its own silent helper process, never the microphone or desktop.
                    using (var capture = new Capture(Native.Loopback(Process.GetCurrentProcess().Id), true)) {
                        capture.Start();
                        string silent = path + ".silent.wav";
                        try {
                            using (var wav = new Wav(silent)) {
                                long epoch = (long)(Stopwatch.GetTimestamp() * (10000000.0 / Stopwatch.Frequency));
                                Thread.Sleep(100);
                                capture.Drain(wav, 0, epoch);
                            }
                        } finally { if (File.Exists(silent)) File.Delete(silent); }
                    }
                }
            } finally { if (File.Exists(path)) File.Delete(path); }
        }
    }
}
'@
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName WindowsBase
Add-Type -TypeDefinition $code -ReferencedAssemblies @('System.dll', 'System.Core.dll', [System.Windows.Point].Assembly.Location,
    [System.Windows.Automation.AutomationElement].Assembly.Location,
    [System.Windows.Automation.ControlType].Assembly.Location)
[CompanionRecording.NativeTest]::Run($Loopback.IsPresent)
Write-Output 'Native recorder checks passed.'

& powershell.exe -NoProfile -NonInteractive -Mta -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "test-recording-cancellation.ps1")
if ($LASTEXITCODE -ne 0) { throw "Native cancellation regression failed" }
