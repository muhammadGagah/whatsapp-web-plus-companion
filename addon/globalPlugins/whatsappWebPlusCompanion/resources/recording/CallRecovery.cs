namespace CompanionRecording {
    using System;
    using System.Collections.Generic;
    using System.Diagnostics;
    using System.Runtime.InteropServices;
    using System.Text;
    using System.Threading;
    using System.Windows;
    using System.Windows.Automation;

    public static class CallRecovery {
        public static void Restore(int pid, string root, int window) {
            using (var stop = new ManualResetEvent(false)) {
                var reader = new Thread(() => {
                    try { Console.ReadLine(); } catch (System.IO.IOException) { }
                    finally { try { stop.Set(); } catch (ObjectDisposedException) { } }
                });
                reader.IsBackground = true; reader.Start();
                Prepare(pid, root, window, false, () => stop.WaitOne(0));
                Console.WriteLine("RESTORED"); Console.Out.Flush();
            }
        }
        [StructLayout(LayoutKind.Sequential)] struct Point { public int x, y; }
        [StructLayout(LayoutKind.Sequential)] struct Mouse { public int x, y; public uint data, flags, time; public UIntPtr extra; }
        [StructLayout(LayoutKind.Sequential)] struct Input { public uint type; public Mouse mouse; }
        [DllImport("user32.dll")] static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
        [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr window);
        [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(Point point);
        [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr window, uint flags);
        [DllImport("user32.dll")] static extern bool GetCursorPos(out Point point);
        [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
        [DllImport("user32.dll")] static extern short GetAsyncKeyState(int key);
        [DllImport("user32.dll")] static extern uint SendInput(uint count, Input[] input, int size);
        [DllImport("user32.dll")] static extern int GetSystemMetrics(int index);
        // MOVE | ABSOLUTE | VIRTUALDESK, combined with LEFTDOWN (2) or LEFTUP (4).
        const uint AbsoluteMove = 0x0001 | 0x8000 | 0x4000;
        // Carry the target in every event: injected input is processed later, so a button event
        // without coordinates could land wherever the cursor is by then.
        static Input[] ClickAt(Point point, params uint[] buttons) {
            int left = GetSystemMetrics(76), top = GetSystemMetrics(77);
            int width = Math.Max(2, GetSystemMetrics(78)), height = Math.Max(2, GetSystemMetrics(79));
            int x = (int)Math.Round((point.x - left) * 65535.0 / (width - 1));
            int y = (int)Math.Round((point.y - top) * 65535.0 / (height - 1));
            var events = new Input[buttons.Length];
            for (int i = 0; i < buttons.Length; i++) {
                events[i].mouse.x = x; events[i].mouse.y = y; events[i].mouse.flags = AbsoluteMove | buttons[i];
            }
            return events;
        }
        [DllImport("user32.dll")] static extern IntPtr OpenInputDesktop(uint flags, bool inherit, uint access);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern bool GetUserObjectInformation(IntPtr handle, int index, StringBuilder name, int length, out int needed);
        [DllImport("user32.dll")] static extern bool CloseDesktop(IntPtr desktop);

        public static bool DesktopAvailable() {
            IntPtr desktop = OpenInputDesktop(0, false, 1);
            if (desktop == IntPtr.Zero) return false;
            try { int needed; var name = new StringBuilder(256);
                return GetUserObjectInformation(desktop, 2, name, 512, out needed) && name.ToString() == "Default";
            } finally { CloseDesktop(desktop); }
        }
        static bool Released() {
            for (int key=1; key<256; key++) if ((GetAsyncKeyState(key) & 0x8000) != 0) return false;
            return true;
        }
        static int Host(AutomationElement element, int pid) {
            for (int i=0; element != null && i<18; i++, element=TreeWalker.RawViewWalker.GetParent(element)) {
                if (element.Current.ProcessId != pid) return 0;
                if (element.Current.ClassName == "InputSiteWindowClass") return element.Current.NativeWindowHandle;
            }
            return 0;
        }
        static List<AutomationElement> Scan(int pid, int window) {
            var root=AutomationElement.FromHandle(new IntPtr(window));
            if (root.Current.ProcessId != pid || root.Current.ClassName != "WinUIDesktopWin32WindowClass") throw new CallUnavailableException();
            var result=new List<AutomationElement>(); var stack=new Stack<Tuple<AutomationElement,int>>();
            stack.Push(Tuple.Create(root,0)); var timer=Stopwatch.StartNew(); var walker=TreeWalker.RawViewWalker;
            while (stack.Count>0) {
                if (timer.ElapsedMilliseconds>1200 || result.Count>=200) throw new CallUnavailableException();
                var entry=stack.Pop(); var element=entry.Item1;
                if (element.Current.ProcessId != pid) throw new CallUnavailableException();
                result.Add(element);
                if (element.Current.ClassName=="Microsoft.UI.Xaml.Controls.WebView2") throw new CallUnavailableException();
                var child=walker.GetFirstChild(element);
                if (child != null && entry.Item2>=18) throw new CallUnavailableException();
                while (child != null) {
                    if (result.Count+stack.Count>=200 || timer.ElapsedMilliseconds>1200) throw new CallUnavailableException();
                    stack.Push(Tuple.Create(child,entry.Item2+1)); child=walker.GetNextSibling(child);
                }
            }
            return result;
        }
        static bool Actionable(AutomationElement element) {
            var type=element.Current.ControlType;
            return type==ControlType.Button || type==ControlType.CheckBox || type==ControlType.Edit ||
                type==ControlType.Hyperlink || type==ControlType.MenuItem || type==ControlType.Slider ||
                type==ControlType.ComboBox || type==ControlType.RadioButton || type==ControlType.TabItem;
        }
        static AutomationElement Peer(List<AutomationElement> elements, int pid, out AutomationElement mic) {
            AutomationElement peer=null; mic=null;
            foreach (var element in elements) {
                var current=element.Current;
                if (current.AutomationId=="NewEndCallButton" || current.AutomationId=="NewMicMuteButton") throw new CallUnavailableException();
                if (current.FrameworkId!="XAML" || !current.IsEnabled) continue;
                if (current.ClassName=="ListViewItem" && current.ControlType==ControlType.ListItem && current.Name=="WhatsApp.PeerStreamVm" && !current.IsOffscreen) {
                    if (peer!=null) throw new CallUnavailableException(); peer=element;
                }
                if (current.AutomationId=="MicMuteButton" && current.ClassName=="CheckBox" && current.ControlType==ControlType.CheckBox) {
                    if (mic!=null) throw new CallUnavailableException(); mic=element;
                }
            }
            if (peer==null || mic==null || Host(peer,pid)==0 || Host(peer,pid)!=Host(mic,pid)) throw new CallUnavailableException();
            return peer;
        }
        static bool Hit(AutomationElement peer, int pid, int window, Point point) {
            if (GetAncestor(WindowFromPoint(point),2)!=new IntPtr(window)) return false;
            var hit=AutomationElement.FromPoint(new System.Windows.Point(point.x,point.y));
            // This provider returns the InputSite host, even inside its peer ListItem.
            if (hit.Current.ProcessId==pid && hit.Current.ClassName=="InputSiteWindowClass" && hit.Current.NativeWindowHandle==Host(peer,pid)) return true;
            for (int depth=0; hit!=null && depth<18; depth++,hit=TreeWalker.RawViewWalker.GetParent(hit)) {
                if (hit.Current.ProcessId!=pid) return false;
                if (Automation.Compare(hit,peer)) return true;
                if (Actionable(hit)) return false;
            }
            return false;
        }
        public static bool SafePoint(Rect rectangle, double x, double y) {
            return !rectangle.IsEmpty && rectangle.Width>2 && rectangle.Height>2 && rectangle.Contains(x,y) &&
                !double.IsNaN(x) && !double.IsNaN(y) && !double.IsInfinity(x) && !double.IsInfinity(y);
        }
        // Stop and a locked desktop stay "unavailable"; only a lost foreground is reported as a focus change.
        static void Invalid(Func<bool> cancelled) {
            if (cancelled() || !DesktopAvailable()) throw new CallUnavailableException();
            throw new FocusChangedException();
        }
        public static void Prepare(int pid, string root, int window, bool activate, Func<bool> cancelled, int expectedForeground = 0) {
            IntPtr oldDpi=SetThreadDpiAwarenessContext(new IntPtr(-4));
            if (oldDpi==IntPtr.Zero) throw new CallUnavailableException();
            try {
                if (cancelled() || !DesktopAvailable()) throw new CallUnavailableException();
                var state=CallState.Probe(pid,root,"");
                if (state.window!=window || (state.state!="connected" && state.state!="compact")) throw new CallUnavailableException();
                if (activate && (expectedForeground==0 || GetForegroundWindow()!=new IntPtr(expectedForeground))) throw new FocusChangedException();
                if (activate && GetForegroundWindow()!=new IntPtr(window)) {
                    if (!SetForegroundWindow(new IntPtr(window))) throw new FocusChangedException();
                }
                Func<bool> valid=()=> !cancelled() && DesktopAvailable() && GetForegroundWindow()==new IntPtr(window);
                if (!valid()) Invalid(cancelled);
                if (state.state=="connected") { CallState.Require(pid,root,window); return; }
                var release=Stopwatch.StartNew();
                while (!Released() && release.ElapsedMilliseconds<1500) { if (!valid()) Invalid(cancelled); Thread.Sleep(25); }
                if (!valid()) Invalid(cancelled);
                if (!Released()) throw new CallUnavailableException();
                AutomationElement mic; var peer=Peer(Scan(pid,window),pid,out mic);
                var focus=AutomationElement.FocusedElement;
                if (!activate && (focus==null || !Automation.Compare(focus,mic))) throw new CallUnavailableException();
                var rectangle=peer.Current.BoundingRectangle;
                var point=new Point { x=(int)(rectangle.Left+rectangle.Width/2), y=(int)(rectangle.Top+rectangle.Height/2) };
                if (!SafePoint(rectangle,point.x,point.y) || !Hit(peer,pid,window,point)) throw new CallUnavailableException();
                Point original;
                if (!GetCursorPos(out original)) throw new CallUnavailableException();
                try {
                    if (!SetCursorPos(point.x,point.y)) throw new CallUnavailableException();
                    AutomationElement freshMic; var elements=Scan(pid,window); var freshPeer=Peer(elements,pid,out freshMic);
                    if (!Automation.Compare(peer,freshPeer) || freshPeer.Current.BoundingRectangle!=rectangle || !Hit(freshPeer,pid,window,point)) throw new CallUnavailableException();
                    foreach (var element in elements) if (Actionable(element) && element.Current.BoundingRectangle.Contains(point.x,point.y)) throw new CallUnavailableException();
                    Point current;
                    if (!valid()) Invalid(cancelled);
                    if (!Released() || (!activate && !Automation.Compare(AutomationElement.FocusedElement,focus)) ||
                        !GetCursorPos(out current) || current.x!=point.x || current.y!=point.y) throw new CallUnavailableException();
                    var events=ClickAt(point,2,4);
                    if (SendInput(2,events,Marshal.SizeOf(typeof(Input)))!=2) {
                        SendInput(1,ClickAt(point,4),Marshal.SizeOf(typeof(Input)));
                        throw new CallUnavailableException();
                    }
                    // Let Windows process the click before the cursor returns to where the user left it.
                    Thread.Sleep(80);
                } finally {
                    Point current;
                    if (GetCursorPos(out current) && current.x==point.x && current.y==point.y) SetCursorPos(original.x,original.y);
                }
                var wait=Stopwatch.StartNew();
                while (wait.ElapsedMilliseconds<2000) {
                    if (!valid()) Invalid(cancelled);
                    state=CallState.Probe(pid,root,"");
                    if (state.window==window && state.state=="connected") return;
                    Thread.Sleep(100);
                }
                throw new CallUnavailableException();
            } finally { SetThreadDpiAwarenessContext(oldDpi); }
        }
    }
}
