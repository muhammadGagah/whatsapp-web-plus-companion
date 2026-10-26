using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

namespace CompanionRecording {
    [StructLayout(LayoutKind.Sequential, Pack = 2)]
    public struct WaveFormat {
        public ushort tag, channels;
        public uint rate, bytesPerSecond;
        public ushort align, bits, extra;
        public static WaveFormat Mono() {
            return new WaveFormat { tag = 1, channels = 1, rate = 48000,
                bytesPerSecond = 96000, align = 2, bits = 16 };
        }
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct Activation { public int type; public uint pid; public int mode; }
    [StructLayout(LayoutKind.Sequential)]
    public struct Blob { public int size; public IntPtr data; }
    [StructLayout(LayoutKind.Explicit)]
    public struct Variant {
        [FieldOffset(0)] public ushort type;
        [FieldOffset(8)] public Blob blob;
        [FieldOffset(8)] public IntPtr text;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct PropertyKey { public Guid format; public uint id; }

    [ComImport, Guid("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IAudioClient {
        void Initialize(int share, uint flags, long duration, long periodicity, ref WaveFormat format, IntPtr session);
        void GetBufferSize(out uint frames);
        void GetStreamLatency(out long latency);
        void GetCurrentPadding(out uint frames);
        [PreserveSig] int IsFormatSupported(int share, ref WaveFormat format, out IntPtr closest);
        void GetMixFormat(out IntPtr format);
        void GetDevicePeriod(out long normal, out long minimum);
        void Start(); void Stop(); void Reset(); void SetEventHandle(IntPtr handle);
        void GetService(ref Guid iid, [MarshalAs(UnmanagedType.IUnknown)] out object service);
    }
    [ComImport, Guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface ICapture {
        void GetBuffer(out IntPtr data, out uint frames, out uint flags, out ulong position, out ulong qpc);
        void ReleaseBuffer(uint frames); void GetNextPacketSize(out uint frames);
    }
    [ComImport, Guid("72A22D78-CDE4-431D-B8CC-843A71199B6D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IActivationOperation {
        void GetActivateResult(out int result, [MarshalAs(UnmanagedType.IUnknown)] out object instance);
    }
    [ComVisible(true), Guid("41D949AB-9862-444A-80F6-C261334DA5EB"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface ICompletion {
        [PreserveSig] int ActivateCompleted(IActivationOperation operation);
    }
    [ComVisible(true), Guid("94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IAgileObject { }
    [ComVisible(true), ClassInterface(ClassInterfaceType.None)]
    public sealed class Completion : ICompletion, IAgileObject {
        public readonly ManualResetEvent done = new ManualResetEvent(false);
        public IAudioClient client;
        public Exception error;
        public int ActivateCompleted(IActivationOperation operation) {
            try {
                int result; object instance;
                operation.GetActivateResult(out result, out instance);
                Marshal.ThrowExceptionForHR(result);
                client = (IAudioClient)instance;
            } catch (Exception e) { error = e; }
            finally { done.Set(); }
            return 0;
        }
    }
    [ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IDevices {
        void EnumAudioEndpoints(int flow, uint state, out IDeviceCollection collection);
        void GetDefaultAudioEndpoint(int flow, int role, out IDevice device);
        void GetDevice([MarshalAs(UnmanagedType.LPWStr)] string id, out IDevice device);
        void RegisterEndpointNotificationCallback(IntPtr callback);
        void UnregisterEndpointNotificationCallback(IntPtr callback);
    }
    [ComImport, Guid("0BD7A1BE-7A1A-44DB-8397-CC5392387B5E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IDeviceCollection {
        void GetCount(out uint count); void Item(uint index, out IDevice device);
    }
    [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IDevice {
        void Activate(ref Guid iid, uint context, IntPtr parameters, [MarshalAs(UnmanagedType.IUnknown)] out object instance);
        void OpenPropertyStore(int access, out IProperties properties);
        void GetId([MarshalAs(UnmanagedType.LPWStr)] out string id);
        void GetState(out uint state);
    }
    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IProperties {
        void GetCount(out uint count); void GetAt(uint index, out PropertyKey key);
        void GetValue(ref PropertyKey key, out Variant value);
        void SetValue(ref PropertyKey key, ref Variant value); void Commit();
    }
    public sealed class DeviceInfo { public string id; public string name; }

    public static class Native {
        [DllImport("Mmdevapi.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
        public static extern void ActivateAudioInterfaceAsync(string path, ref Guid iid, ref Variant parameters,
            ICompletion completion, out IActivationOperation operation);
        [DllImport("ole32.dll")] public static extern int PropVariantClear(ref Variant value);
        public static Guid clientId = new Guid("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2");
        public static IDevices Devices() {
            return (IDevices)Activator.CreateInstance(Type.GetTypeFromCLSID(
                new Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")));
        }
        public static DeviceInfo[] Inputs() {
            var result = new List<DeviceInfo>();
            var devices = Devices(); IDeviceCollection collection = null;
            try {
                devices.EnumAudioEndpoints(1, 1, out collection);
                uint count; collection.GetCount(out count);
                for (uint i = 0; i < count; i++) {
                    IDevice device; collection.Item(i, out device);
                    IProperties properties = null;
                    try {
                        string id; device.GetId(out id);
                        string name = null;
                        // A missing or unreadable friendly name must not hide the device or the others.
                        try {
                            device.OpenPropertyStore(0, out properties);
                            var key = new PropertyKey { format = new Guid("A45C254E-DF1C-4EFD-8020-67D146A850E0"), id = 14 };
                            Variant value; properties.GetValue(ref key, out value);
                            try { if (value.type == 31 && value.text != IntPtr.Zero) name = Marshal.PtrToStringUni(value.text); }
                            finally { PropVariantClear(ref value); }
                        } catch (COMException) { }
                        result.Add(new DeviceInfo { id = id, name = name });
                    } finally {
                        if (properties != null) Marshal.ReleaseComObject(properties);
                        Marshal.ReleaseComObject(device);
                    }
                }
            } finally {
                if (collection != null) Marshal.ReleaseComObject(collection);
                Marshal.ReleaseComObject(devices);
            }
            return result.ToArray();
        }
        public static IAudioClient Microphone(string id) {
            var devices = Devices(); IDevice device = null;
            try {
                devices.GetDevice(id, out device);
                object instance; device.Activate(ref clientId, 23, IntPtr.Zero, out instance);
                return (IAudioClient)instance;
            } finally {
                if (device != null) Marshal.ReleaseComObject(device);
                Marshal.ReleaseComObject(devices);
            }
        }
        public static IAudioClient Loopback(int pid) {
            var completion = new Completion();
            var activation = new Activation { type = 1, pid = checked((uint)pid), mode = 0 };
            IntPtr memory = Marshal.AllocHGlobal(Marshal.SizeOf(activation));
            IActivationOperation operation = null;
            // Keep activation memory alive until the callback finishes. On timeout the helper exits.
            Marshal.StructureToPtr(activation, memory, false);
            var parameters = new Variant { type = 65, blob = new Blob { size = Marshal.SizeOf(activation), data = memory } };
            ActivateAudioInterfaceAsync("VAD\\Process_Loopback", ref clientId, ref parameters, completion, out operation);
            if (!completion.done.WaitOne(10000)) throw new TimeoutException("activation");
            Marshal.FreeHGlobal(memory);
            Marshal.ReleaseComObject(operation);
            completion.done.Dispose();
            if (completion.error != null) throw completion.error;
            return completion.client;
        }
    }

    public sealed class Capture : IDisposable {
        IAudioClient client;
        ICapture capture;
        bool started;
        public Capture(IAudioClient audio, bool loopback) {
            client = audio;
            try {
                var format = WaveFormat.Mono();
                client.Initialize(0, 0x88000000U | (loopback ? 0x20000U : 0U), 2000000, 0, ref format, IntPtr.Zero);
                Guid iid = new Guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317");
                object service; client.GetService(ref iid, out service); capture = (ICapture)service;
            } catch { Dispose(); throw; }
        }
        public void Start() { client.Start(); started = true; }
        public void Drain(Wav writer, int channel, long epoch) {
            uint next; capture.GetNextPacketSize(out next);
            for (int packets = 0; next > 0; packets++) {
                if (packets >= 200) throw new IOException("capture backlog");
                IntPtr data; uint frames, flags; ulong position, qpc;
                capture.GetBuffer(out data, out frames, out flags, out position, out qpc);
                try {
                    if (frames > 48000 || (flags & 4) != 0) throw new IOException("audio timestamp");
                    var bytes = new byte[checked((int)frames * 2)];
                    if ((flags & 2) == 0) Marshal.Copy(data, bytes, 0, bytes.Length);
                    long frame = (long)Math.Round(((long)qpc - epoch) * 48000.0 / 10000000.0);
                    writer.Write(channel, frame, bytes);
                } finally { capture.ReleaseBuffer(frames); }
                capture.GetNextPacketSize(out next);
            }
        }
        public void Dispose() {
            if (client != null) {
                try { if (started) client.Stop(); }
                finally {
                    if (capture != null) Marshal.ReleaseComObject(capture);
                    Marshal.ReleaseComObject(client); client = null;
                }
            }
        }
    }

    // Both sources use WASAPI's QPC timestamps. Left is WhatsApp, right is microphone.
    // Only packet-sized buffers are allocated, regardless of the recording duration.
    public sealed class Wav : IDisposable {
        FileStream file;
        public const long MaxFrames = 48000L * 60 * 60 * 4;
        readonly long maxFrames;
        long lastFlush;
        // Full: audio reached the length limit and later audio is dropped, so the recorder stops and saves.
        public bool Full { get; private set; }
        public bool Empty { get; private set; }
        public Wav(string path) : this(path, MaxFrames) { }
        public Wav(string path, long limit) {
            maxFrames = limit; Empty = true;
            file = new FileStream(path, FileMode.CreateNew, FileAccess.ReadWrite, FileShare.Read);
            file.SetLength(44); Header();
        }
        public void Write(int channel, long frame, byte[] mono) {
            int skip = frame < 0 ? checked((int)Math.Min(-frame, mono.Length / 2)) : 0;
            frame = Math.Max(0, frame);
            int frames = mono.Length / 2 - skip;
            if (frame + frames > maxFrames) { frames = (int)Math.Max(0, maxFrames - frame); Full = true; }
            if (frames == 0) return;
            Empty = false;
            long offset = 44 + frame * 4;
            byte[] stereo = new byte[frames * 4];
            file.Position = offset;
            int read = 0, count;
            while (read < stereo.Length && (count = file.Read(stereo, read, stereo.Length - read)) > 0) read += count;
            for (int i = 0; i < frames; i++) {
                stereo[i * 4 + channel * 2] = mono[(i + skip) * 2];
                stereo[i * 4 + channel * 2 + 1] = mono[(i + skip) * 2 + 1];
            }
            file.Position = offset; file.Write(stereo, 0, stereo.Length);
            if (Environment.TickCount - lastFlush > 1000 || lastFlush == 0) {
                Header(); file.Flush(); lastFlush = Environment.TickCount;
            }
        }
        void Header() {
            file.Position = 0;
            var writer = new BinaryWriter(file, System.Text.Encoding.ASCII, true);
            writer.Write(System.Text.Encoding.ASCII.GetBytes("RIFF")); writer.Write((uint)(file.Length - 8));
            writer.Write(System.Text.Encoding.ASCII.GetBytes("WAVEfmt ")); writer.Write(16U);
            writer.Write((ushort)1); writer.Write((ushort)2); writer.Write(48000U); writer.Write(192000U);
            writer.Write((ushort)4); writer.Write((ushort)16);
            writer.Write(System.Text.Encoding.ASCII.GetBytes("data")); writer.Write((uint)(file.Length - 44));
            writer.Flush();
        }
        public void Dispose() { if (file != null) { try { Header(); } finally { file.Dispose(); file = null; } } }
    }

    public static class Recorder {
        public static bool StartSources(Func<bool> cancelled, Action first, Action second) {
            if (cancelled()) return false;
            first();
            if (cancelled()) return false;
            second();
            return !cancelled();
        }
        static void Cancelled() { Console.WriteLine("CANCELLED"); Console.Out.Flush(); }
        static void Report(string message) { Console.WriteLine(message); Console.Out.Flush(); }
        // Interval between auto-stop call checks. CallMonitor needs several consecutive absences.
        const int CallCheckMilliseconds = 5000;

        public static void Run(int pid, string packageRoot, string microphone, string path, int parentPid, int callWindow, int foreground) {
            using (var stop = new ManualResetEvent(false))
            using (var target = Process.GetProcessById(pid))
            using (var parent = Process.GetProcessById(parentPid)) {
                var reader = new Thread(() => {
                    try { Console.ReadLine(); } catch (IOException) { }
                    finally { try { stop.Set(); } catch (ObjectDisposedException) { } }
                });
                reader.IsBackground = true; reader.Start();
                string root = Path.GetFullPath(packageRoot).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
                if (!Path.GetFullPath(target.MainModule.FileName).StartsWith(root, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("target identity");
                // Open and retain the process handles, so PID reuse cannot redirect an active recording.
                IntPtr targetHandle = target.Handle, parentHandle = parent.Handle;
                Func<bool> cancelled = () => stop.WaitOne(0) || parent.HasExited || target.HasExited || !CallRecovery.DesktopAvailable();
                // Stop during preparation also fails the call checks. Report it as a cancellation.
                try { CallRecovery.Prepare(pid, root, callWindow, true, cancelled, foreground); }
                catch (CallUnavailableException) { if (stop.WaitOne(0)) { Cancelled(); return; } throw; }
                catch (FocusChangedException) { if (stop.WaitOne(0)) { Cancelled(); return; } throw; }
                string ending = null;
                using (var incoming = new Capture(Native.Loopback(pid), true))
                using (var local = new Capture(Native.Microphone(microphone), false)) {
                    if (cancelled()) { Cancelled(); return; }
                    try { CallState.Require(pid, root, callWindow); }
                    catch (CallUnavailableException) { if (stop.WaitOne(0)) { Cancelled(); return; } throw; }
                    if (cancelled()) { Cancelled(); return; }
                    long epoch = (long)(Stopwatch.GetTimestamp() * (10000000.0 / Stopwatch.Frequency));
                    if (!StartSources(cancelled, incoming.Start, local.Start)) { Cancelled(); return; }
                    // Create the file only once capture runs, so a cancelled start leaves nothing behind.
                    var output = new Wav(path);
                    bool kept = false;
                    try {
                        Report("STARTED");
                        var elapsed = Stopwatch.StartNew();
                        using (var monitor = new CallMonitor(pid, root, callWindow, CallCheckMilliseconds)) {
                            while (!stop.WaitOne(10) && !target.HasExited && !parent.HasExited) {
                                incoming.Drain(output, 0, epoch); local.Drain(output, 1, epoch);
                                if (output.Full || elapsed.Elapsed.TotalHours >= 4) { ending = "LIMIT"; break; }
                                if (monitor.Ended) { ending = "CALL_ENDED"; break; }
                            }
                        }
                        incoming.Drain(output, 0, epoch); local.Drain(output, 1, epoch);
                        kept = true;
                    } finally {
                        output.Dispose();
                        // A failed recording without any audio is not a partial recording.
                        if (!kept && output.Empty) { try { File.Delete(path); } catch (IOException) { } catch (UnauthorizedAccessException) { } }
                    }
                }
                if (ending != null) Report(ending);
                Report("SAVED");
            }
        }
    }
}
