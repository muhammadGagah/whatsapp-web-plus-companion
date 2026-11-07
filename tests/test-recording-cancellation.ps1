$ErrorActionPreference = 'Stop'
$source = Get-Content -LiteralPath (Join-Path $PSScriptRoot '../addon/globalPlugins/whatsappWebPlusCompanion/resources/recording/Recorder.cs') -Raw
$run = $source.Substring($source.IndexOf('    public static class Recorder {'))
$stubs = @'
using System; using System.IO; using System.Threading; using System.Diagnostics;
namespace CompanionRecording {
public sealed class GateReader:TextReader {
    public static ManualResetEvent gate=new ManualResetEvent(false);
    public override string ReadLine(){gate.WaitOne(); return "stop";}
}
public sealed class CallUnavailableException:Exception {}
public sealed class FocusChangedException:Exception {}
public static class CallRecovery {
    public static Func<bool> cancelled;
    public static bool failAfterStop;
    public static bool DesktopAvailable(){return true;}
    public static void Prepare(int p,string r,int w,bool a,Func<bool> c,int f){
        cancelled=c;
        if (!failAfterStop) return;
        // The real call view checks fail once Stop arrives while preparation is still running.
        GateReader.gate.Set();
        if (!SpinWait.SpinUntil(() => c(), 3000)) throw new Exception("Stop not received");
        throw new CallUnavailableException();
    }
}
public static class CallState {
    public static void Require(int p,string r,int w){
        GateReader.gate.Set();
        if (!SpinWait.SpinUntil(() => CallRecovery.cancelled(), 3000)) throw new Exception("Stop not received");
    }
}
public sealed class CallMonitor:IDisposable {
    public CallMonitor(int p,string r,int w,int i){}
    public bool Ended { get { return false; } }
    public void Dispose(){}
}
public static class Native {
    public static object Loopback(int p){return null;}
    public static object Microphone(string m){return null;}
}
public class Capture:IDisposable {
    public static int starts;
    public Capture(object a,bool b){}
    public void Start(){starts++;}
    public void Drain(Wav w,int c,long e){}
    public void Dispose(){}
}
public class Wav:IDisposable {
    public static int created;
    public Wav(string p){created++;}
    public bool Full { get { return false; } }
    public bool Empty { get { return true; } }
    public void Dispose(){}
}
'@
Add-Type -TypeDefinition ($stubs + $run)
[Console]::SetIn([CompanionRecording.GateReader]::new())
$taskProcess = [Diagnostics.Process]::GetCurrentProcess()
$originalOut = [Console]::Out
foreach ($failAfterStop in @($false, $true)) {
    [CompanionRecording.CallRecovery]::failAfterStop = $failAfterStop
    $output = [IO.StringWriter]::new()
    [Console]::SetOut($output)
    try {
        [CompanionRecording.Recorder]::Run($taskProcess.Id, (Split-Path $taskProcess.MainModule.FileName), 'mock', 'mock', $taskProcess.Id, 1, 1)
    } finally { [Console]::SetOut($originalOut) }
    if ($output.ToString().Trim() -ne 'CANCELLED') {
        throw "Stop during preparation was not reported as cancelled (failAfterStop=$failAfterStop)"
    }
    if ([CompanionRecording.Capture]::starts -ne 0 -or [CompanionRecording.Wav]::created -ne 0) {
        throw 'Cancellation during the final call check started capture or created output'
    }
}
Write-Output 'Native cancellation regression passed.'
