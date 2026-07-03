using System;
using System.Collections.Generic;
using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

namespace GtaCopilot.Mod
{
    /// <summary>
    /// Phase 2 state stream sender. Owned by Claude Code; Hermes does not edit
    /// this file or add C# threading anywhere else in the mod.
    ///
    /// Threading contract: the script thread only calls EnqueueLine, Status,
    /// DroppedLines, and Dispose — none of them block on network I/O. A single
    /// background thread owns the TCP connection to the brain process and
    /// drains a bounded queue of pre-serialized JSON lines. This class must
    /// never call GTA/SHVDN APIs: the sender thread touches strings and
    /// sockets only, so all natives stay on the script thread.
    ///
    /// Delivery is lossy by design. While the brain is down, lines are
    /// dropped (bounded queue, drop-oldest) and reconnect attempts are
    /// throttled; the 5 s heartbeat emission doubles as the retry ticker.
    /// </summary>
    public sealed class StateStreamClient : IDisposable
    {
        public const int BrainPort = 48651;

        private const int MaxQueuedLines = 256;
        private const int ConnectRetryIntervalMilliseconds = 2000;
        private const int SendTimeoutMilliseconds = 2000;
        private const int StopJoinTimeoutMilliseconds = 1500;

        private static readonly Encoding Utf8NoBom = new UTF8Encoding(false);

        private readonly object queueLock = new object();
        private readonly Queue<string> pendingLines = new Queue<string>();
        private readonly Thread senderThread;

        private volatile bool stopRequested;
        private volatile string status;

        // Written and read on the script thread only (inside EnqueueLine).
        private int droppedLines;

        public StateStreamClient()
        {
            status = "waiting for brain on 127.0.0.1:" +
                BrainPort.ToString(CultureInfo.InvariantCulture);
            senderThread = new Thread(SenderLoop)
            {
                IsBackground = true,
                Name = "GtaCopilot.StateStream"
            };
            senderThread.Start();
        }

        /// <summary>Last connection status; safe to read from the script thread.</summary>
        public string Status
        {
            get { return status; }
        }

        /// <summary>Lines discarded because the queue was full. Script thread only.</summary>
        public int DroppedLines
        {
            get { return droppedLines; }
        }

        /// <summary>
        /// Called from the script thread with a fully serialized JSON line.
        /// Never blocks on the network; drops the oldest line when full.
        /// </summary>
        public void EnqueueLine(string line)
        {
            if (string.IsNullOrEmpty(line))
            {
                return;
            }

            lock (queueLock)
            {
                if (stopRequested)
                {
                    return;
                }

                while (pendingLines.Count >= MaxQueuedLines)
                {
                    pendingLines.Dequeue();
                    droppedLines++;
                }

                pendingLines.Enqueue(line);
                Monitor.Pulse(queueLock);
            }
        }

        public void Dispose()
        {
            lock (queueLock)
            {
                stopRequested = true;
                Monitor.PulseAll(queueLock);
            }

            // Best effort: the thread is IsBackground, so a stuck join cannot
            // keep the process alive; never abort it.
            senderThread.Join(StopJoinTimeoutMilliseconds);
        }

        private void SenderLoop()
        {
            TcpClient client = null;
            NetworkStream stream = null;
            int lastConnectAttemptTick = Environment.TickCount - ConnectRetryIntervalMilliseconds;

            while (true)
            {
                string line = WaitForNextLine();
                if (line == null)
                {
                    break;
                }

                if (stream == null)
                {
                    int now = Environment.TickCount;
                    if (unchecked(now - lastConnectAttemptTick) < ConnectRetryIntervalMilliseconds)
                    {
                        // Still backing off; this line is intentionally dropped.
                        continue;
                    }

                    lastConnectAttemptTick = now;
                    try
                    {
                        client = new TcpClient
                        {
                            NoDelay = true,
                            SendTimeout = SendTimeoutMilliseconds
                        };
                        client.Connect(IPAddress.Loopback, BrainPort);
                        stream = client.GetStream();
                        status = "connected to brain on 127.0.0.1:" +
                            BrainPort.ToString(CultureInfo.InvariantCulture);
                    }
                    catch (Exception ex)
                    {
                        CloseQuietly(ref client, ref stream);
                        status = "waiting for brain (" + ex.Message + ")";
                        continue;
                    }
                }

                try
                {
                    byte[] payload = Utf8NoBom.GetBytes(line + "\n");
                    stream.Write(payload, 0, payload.Length);
                }
                catch (Exception ex)
                {
                    CloseQuietly(ref client, ref stream);
                    status = "disconnected (" + ex.Message + ")";
                }
            }

            CloseQuietly(ref client, ref stream);
        }

        private string WaitForNextLine()
        {
            lock (queueLock)
            {
                while (pendingLines.Count == 0)
                {
                    if (stopRequested)
                    {
                        return null;
                    }

                    Monitor.Wait(queueLock);
                }

                if (stopRequested)
                {
                    return null;
                }

                return pendingLines.Dequeue();
            }
        }

        private static void CloseQuietly(ref TcpClient client, ref NetworkStream stream)
        {
            if (stream != null)
            {
                try
                {
                    stream.Dispose();
                }
                catch
                {
                    // Already broken; nothing useful to do.
                }

                stream = null;
            }

            if (client != null)
            {
                try
                {
                    client.Close();
                }
                catch
                {
                    // Already broken; nothing useful to do.
                }

                client = null;
            }
        }
    }
}
