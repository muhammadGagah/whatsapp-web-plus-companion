namespace CompanionRecording {
    using System;
    using System.Collections.Generic;
    using System.Diagnostics;
    using System.IO;
    using System.Runtime.InteropServices;
    using System.Text.RegularExpressions;
    using System.Threading;
    using System.Windows.Automation;

    public sealed class CallUnavailableException : Exception { }
    // The call is fine, but WhatsApp's call window was not (or no longer) in the foreground.
    public sealed class FocusChangedException : Exception { }
    public sealed class CallResult {
        public string channel;
        public string state = "unknown";
        public int pid;
        public int window;
    }
    public static class CallState {
        delegate bool EnumWindow(IntPtr window, IntPtr data);
        [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindow callback, IntPtr data);
        [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window, out uint pid);
        [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr window);
        [DllImport("user32.dll")] static extern bool IsIconic(IntPtr window);
        [DllImport("user32.dll")] static extern bool IsWindow(IntPtr window);
        sealed class Evidence { public int end, mic, timers, peer, compactMic, participants; }

        public static bool Duration(string value) {
            return Regex.IsMatch(value ?? "", @"\A(?:[0-9]{1,4}[:\u2236])?[0-9]{1,4}[:\u2236][0-5][0-9]\z");
        }
        internal static string InspectWindow(int pid, int window) {
            var root = AutomationElement.FromHandle(new IntPtr(window));
            if (root.Current.ProcessId != pid || root.Current.ClassName != "WinUIDesktopWin32WindowClass") return "unavailable";
            var walker = TreeWalker.RawViewWalker;
            var stack = new Stack<Tuple<AutomationElement, int, int>>();
            var evidence = new Dictionary<int, Evidence>();
            stack.Push(Tuple.Create(root, 0, 0));
            var clock = Stopwatch.StartNew(); int visited = 0;
            while (stack.Count > 0) {
                if (++visited > 400 || clock.ElapsedMilliseconds > 1200) throw new CallUnavailableException();
                var entry = stack.Pop(); var element = entry.Item1; int depth = entry.Item2, host = entry.Item3;
                var current = element.Current;
                if (current.ProcessId != pid) continue;
                if (current.ClassName == "InputSiteWindowClass") host = current.NativeWindowHandle;
                if (host != 0 && current.FrameworkId == "XAML" && current.IsEnabled) {
                    if (!evidence.ContainsKey(host)) evidence[host] = new Evidence();
                    var item = evidence[host];
                    if (current.ControlType == ControlType.CheckBox && current.ClassName == "CheckBox" && current.AutomationId == "MicMuteButton") item.compactMic++;
                    if (!current.IsOffscreen) {
                    if (current.ControlType == ControlType.ListItem && current.ClassName == "ListViewItem" && current.Name == "WhatsApp.PeerStreamVm") item.peer++;
                    if (current.ControlType == ControlType.List && current.AutomationId == "ParticipantList") item.participants++;
                    if (current.ControlType == ControlType.Button && current.ClassName == "Button") {
                        if (current.AutomationId == "NewEndCallButton") item.end++;
                        if (current.AutomationId == "NewMicMuteButton") item.mic++;
                    }
                    if (current.ControlType == ControlType.Text && current.ClassName == "TextBlock" &&
                        current.AutomationId == "CallStatusText" && Duration(current.Name)) item.timers++;
                    }
                }
                // The call controls are native. Never inspect chat contents inside the WebView.
                if (current.ClassName == "Microsoft.UI.Xaml.Controls.WebView2") continue;
                var child = walker.GetFirstChild(element);
                if (child != null && depth >= 18) throw new CallUnavailableException();
                while (child != null) {
                    if (stack.Count + visited >= 400 || clock.ElapsedMilliseconds > 1200) throw new CallUnavailableException();
                    stack.Push(Tuple.Create(child, depth + 1, host));
                    child = walker.GetNextSibling(child);
                }
            }
            int matches = 0; string state = "unavailable";
            foreach (var item in evidence.Values) {
                if (item.end == 1 && item.mic == 1 && item.timers > 0) { matches++; state = "connected"; }
                else if (item.end == 0 && item.mic == 0 && item.peer == 1 && item.compactMic == 1 && item.participants == 1) { matches++; state = "compact"; }
            }
            return matches == 1 ? state : "unavailable";
        }
        public static CallResult Probe(int pid, string root, string channel) {
            var result = new CallResult { channel = channel, pid = pid };
            try {
                using (var process = Process.GetProcessById(pid)) {
                    string prefix = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
                    if (!Path.GetFullPath(process.MainModule.FileName).StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) return result;
                    var windows = new List<int>();
                    if (!EnumWindows((window, data) => {
                        uint owner; GetWindowThreadProcessId(window, out owner);
                        if (owner == pid && IsWindowVisible(window)) windows.Add(window.ToInt32());
                        return true;
                    }, IntPtr.Zero) || windows.Count > 16) return result;
                    int found = 0;
                    foreach (int window in windows) {
                        string state = InspectWindow(pid, window);
                        if (state == "connected" || state == "compact") { result.window = window; result.state = state; found++; }
                    }
                    if (process.HasExited) return result;
                    if (found != 1) result.state = found == 0 ? "unavailable" : "unknown";
                    if (found != 1) result.window = 0;
                }
            } catch { result.state = "unknown"; result.window = 0; }
            return result;
        }
        static readonly string[] CallMarkers = {
            "NewEndCallButton", "NewMicMuteButton", "MicMuteButton", "CallStatusText", "ParticipantList" };
        // Auto-stop evidence only. Unlike Probe, offscreen and disabled controls count, so a minimized,
        // compact, reconnecting or covered call window still means the call is present. Any incomplete
        // scan or error returns null, so uncertainty can never stop a recording.
        public static bool? Present(int pid, string root, int callWindow) {
            try {
                using (var process = Process.GetProcessById(pid)) {
                    string prefix = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
                    if (!Path.GetFullPath(process.MainModule.FileName).StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) return null;
                    var windows = new List<IntPtr>();
                    if (!EnumWindows((window, data) => {
                        uint owner; GetWindowThreadProcessId(window, out owner);
                        if (owner == pid && IsWindowVisible(window)) windows.Add(window);
                        return true;
                    }, IntPtr.Zero) || windows.Count > 16) return null;
                    var clock = Stopwatch.StartNew();
                    foreach (var window in windows) if (HasCallControls(pid, window, clock)) return true;
                    if (process.HasExited) return null;
                    // A minimized call window may not expose its controls. That is uncertainty, not an ended call.
                    // Only the recorded call window counts; a minimized main window must not block auto-stop.
                    var call = new IntPtr(callWindow);
                    if (callWindow != 0 && IsWindow(call) && IsWindowVisible(call) && IsIconic(call)) return null;
                    return false;
                }
            } catch { return null; }
        }
        static bool HasCallControls(int pid, IntPtr window, Stopwatch clock) {
            var root = AutomationElement.FromHandle(window);
            if (root.Current.ProcessId != pid) return false;
            var walker = TreeWalker.RawViewWalker;
            var stack = new Stack<Tuple<AutomationElement, int>>();
            stack.Push(Tuple.Create(root, 0)); int visited = 0;
            while (stack.Count > 0) {
                if (++visited > 400 || clock.ElapsedMilliseconds > 3000) throw new CallUnavailableException();
                var entry = stack.Pop(); var current = entry.Item1.Current;
                if (current.ProcessId != pid) continue;
                if (Array.IndexOf(CallMarkers, current.AutomationId) >= 0 ||
                    (current.ClassName == "ListViewItem" && current.Name == "WhatsApp.PeerStreamVm")) return true;
                // The call controls are native. Never inspect chat contents inside the WebView.
                if (current.ClassName == "Microsoft.UI.Xaml.Controls.WebView2") continue;
                var child = walker.GetFirstChild(entry.Item1);
                if (child != null && entry.Item2 >= 18) throw new CallUnavailableException();
                while (child != null) {
                    if (stack.Count + visited >= 400) throw new CallUnavailableException();
                    stack.Push(Tuple.Create(child, entry.Item2 + 1));
                    child = walker.GetNextSibling(child);
                }
            }
            return false;
        }
        public static void Require(int pid, string root, int window) {
            var state = Probe(pid, root, "");
            if (state.state != "connected" || state.window != window) throw new CallUnavailableException();
        }
    }
    // An ended call needs consecutive complete scans without any call control. Unknown resets the count.
    public sealed class CallEndTracker {
        public const int Required = 3;
        int absent;
        public bool Observe(bool? present) {
            absent = present == false ? absent + 1 : 0;
            return absent >= Required;
        }
    }
    // Checks on its own thread, so slow UIA providers never delay audio draining.
    public sealed class CallMonitor : IDisposable {
        readonly ManualResetEvent finished = new ManualResetEvent(false);
        volatile bool ended;
        public bool Ended { get { return ended; } }
        public CallMonitor(int pid, string root, int callWindow, int interval)
            : this(interval, () => CallState.Present(pid, root, callWindow)) { }
        public CallMonitor(int interval, Func<bool?> present) {
            var tracker = new CallEndTracker();
            var thread = new Thread(() => {
                while (!finished.WaitOne(interval)) {
                    bool? state;
                    try { state = present(); } catch { state = null; }
                    if (tracker.Observe(state)) { ended = true; return; }
                }
            });
            thread.IsBackground = true; thread.Start();
        }
        // Never waits for a scan in progress. The thread ends at its next interval or with the helper.
        public void Dispose() { finished.Set(); }
    }
}
